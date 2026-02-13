"""
Turbine Market Maker Bot

Probability-based market maker for BTC, ETH, and SOL 15-minute prediction
markets. Fetches real-time prices from Pyth Network to compute YES/NO target
probabilities, then quotes multi-level bid/ask ladders with geometric size
distribution. USDC is approved gaslessly via a one-time max permit per
settlement contract.

Algorithm: Fetches real-time prices from Pyth Network (same oracle Turbine
           uses) and compares them to each market's strike price.
           - YES target = 0.50 + (price_deviation% * sensitivity)
           - Sensitivity increases toward expiration (time decay)
           - Spread tightens toward expiration (minimum 0.5%)
           - Multi-level geometric distribution concentrates liquidity at best price
           - Requotes only when target shifts >2% (rebalance threshold)

Features:
- Multi-asset: trades BTC, ETH, and SOL simultaneously (configurable via --assets)
- Probability-based dynamic pricing from Pyth prices
- Multi-level quoting with geometric size distribution (default 6 levels)
- Time-decay sensitivity and spread tightening toward expiration
- Cancel-then-place order refresh to avoid self-trade issues
- Allocation-based budgeting per asset (total USDC split across 4 sides x N levels)
- Auto-approves USDC gaslessly when entering a new market
- Automatic market transition when 15-minute markets rotate
- Automatic claiming of winnings from resolved markets

Usage:
    TURBINE_PRIVATE_KEY=0x... python examples/market_maker.py

    # Custom parameters
    TURBINE_PRIVATE_KEY=0x... python examples/market_maker.py \\
        --allocation 50 \\
        --spread 0.02 \\
        --levels 6 \\
        --sensitivity 0.10

    # Trade only BTC and ETH
    TURBINE_PRIVATE_KEY=0x... python examples/market_maker.py \\
        --assets BTC,ETH
"""

import argparse
import asyncio
import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
import httpx

from turbine_client import TurbineClient, TurbineWSClient, Outcome, Side, QuickMarket
from turbine_client.exceptions import TurbineApiError, WebSocketError

# Load environment variables
load_dotenv()

# ============================================================
# CONFIGURATION - Adjust these parameters for your strategy
# ============================================================
# Claim-only mode: Set CLAIM_ONLY_MODE=true in .env to disable trading
CLAIM_ONLY_MODE = os.environ.get("CLAIM_ONLY_MODE", "false").lower() == "true"
# Chain ID: Set CHAIN_ID in .env (default: 84532 for Base Sepolia)
CHAIN_ID = int(os.environ.get("CHAIN_ID", "84532"))
# API Host: Set TURBINE_HOST in .env (default: localhost for testing)
TURBINE_HOST = os.environ.get("TURBINE_HOST", "http://localhost:8080")

# Default trading parameters (in USDC terms)
DEFAULT_ALLOCATION_USDC = 50.0  # $50 total allocation per asset split across all sides/levels

# Quick market pricing parameters (matching Go MM defaults)
DEFAULT_SPREAD = 0.02  # 2% spread around target probability
DEFAULT_BASE_PROBABILITY = 0.50  # Starting YES probability
DEFAULT_PRICE_SENSITIVITY = 1.5  # Probability shift per 1% price move
DEFAULT_MAX_PROBABILITY = 0.95   # Cap for extreme moves
DEFAULT_TIME_DECAY_FACTOR = 1.5  # Sensitivity multiplier at expiration
DEFAULT_NUM_LEVELS = 6  # Orders per side
DEFAULT_GEOMETRIC_LAMBDA = 1.5  # Geometric distribution parameter
MIN_SPREAD = 0.005  # 0.5% minimum spread at expiration
SPREAD_TIGHTENING = 0.75  # How much spread tightens (0.75 = to 25% of base)

# Rebalance thresholds (matching Go MM)
REBALANCE_THRESHOLD = 0.02  # 2% probability change triggers requote
MIN_REBALANCE_INTERVAL = 5  # Minimum seconds between rebalances
REFRESH_INTERVAL = 10  # Seconds between price checks

# Pyth Network Hermes API - same price source Turbine uses
PYTH_HERMES_URL = "https://hermes.pyth.network/v2/updates/price/latest"

# Pyth feed IDs per asset
PYTH_FEED_IDS = {
    "BTC": "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
    "ETH": "0xff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace",
    "SOL": "0xef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d",
}

# Supported assets
SUPPORTED_ASSETS = list(PYTH_FEED_IDS.keys())


def get_or_create_api_credentials(env_path: Path = None):
    """Get existing credentials or register new ones and save to .env."""
    if env_path is None:
        env_path = Path(__file__).parent / ".env"

    api_key_id = os.environ.get("TURBINE_API_KEY_ID")
    api_private_key = os.environ.get("TURBINE_API_PRIVATE_KEY")

    if api_key_id and api_private_key:
        print("Using existing API credentials")
        return api_key_id, api_private_key

    private_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if not private_key:
        raise ValueError("Set TURBINE_PRIVATE_KEY in your .env file")

    print("Registering new API credentials...")
    credentials = TurbineClient.request_api_credentials(
        host=TURBINE_HOST,
        private_key=private_key,
    )

    api_key_id = credentials["api_key_id"]
    api_private_key = credentials["api_private_key"]

    # Auto-save to .env
    _save_credentials_to_env(env_path, api_key_id, api_private_key)
    os.environ["TURBINE_API_KEY_ID"] = api_key_id
    os.environ["TURBINE_API_PRIVATE_KEY"] = api_private_key

    print(f"API credentials saved to {env_path}")
    return api_key_id, api_private_key


def _save_credentials_to_env(env_path: Path, api_key_id: str, api_private_key: str):
    """Save API credentials to .env file."""
    env_path = Path(env_path)

    if env_path.exists():
        content = env_path.read_text()
        # Update or append each credential
        if "TURBINE_API_KEY_ID=" in content:
            content = re.sub(r'^TURBINE_API_KEY_ID=.*$', f'TURBINE_API_KEY_ID={api_key_id}', content, flags=re.MULTILINE)
        else:
            content = content.rstrip() + f"\nTURBINE_API_KEY_ID={api_key_id}"
        if "TURBINE_API_PRIVATE_KEY=" in content:
            content = re.sub(r'^TURBINE_API_PRIVATE_KEY=.*$', f'TURBINE_API_PRIVATE_KEY={api_private_key}', content, flags=re.MULTILINE)
        else:
            content = content.rstrip() + f"\nTURBINE_API_PRIVATE_KEY={api_private_key}"
        env_path.write_text(content + "\n")
    else:
        content = f"# Turbine Bot Config\nTURBINE_PRIVATE_KEY={os.environ.get('TURBINE_PRIVATE_KEY', '')}\nTURBINE_API_KEY_ID={api_key_id}\nTURBINE_API_PRIVATE_KEY={api_private_key}\n"
        env_path.write_text(content)


class AssetState:
    """Per-asset market making state."""

    def __init__(self, asset: str):
        self.asset = asset
        self.market_id: str | None = None
        self.settlement_address: str | None = None
        self.contract_address: str | None = None
        self.strike_price: int = 0  # In 1e6 units
        self.market_start_time: int = 0
        self.market_end_time: int = 0

        # Dynamic pricing state
        self.yes_target: float = DEFAULT_BASE_PROBABILITY
        self.current_spread: float = DEFAULT_SPREAD
        self.yes_target_at_rebalance: float = DEFAULT_BASE_PROBABILITY
        self.last_rebalance_time: int = 0

        # Order tracking
        self.active_orders: dict[str, str] = {}  # order_hash -> side

        # Track markets we've traded in for claiming winnings
        self.traded_markets: dict[str, str] = {}  # market_id -> contract_address


class MarketMaker:
    """Probability-based market maker for BTC, ETH, and SOL 15-minute prediction markets.

    Computes YES/NO target probabilities from live prices vs strike per asset,
    then quotes multi-level bid/ask ladders with geometric size distribution.
    Sensitivity increases and spread tightens toward expiration. USDC is
    approved gaslessly via one-time max EIP-2612 permit through the relayer.
    """

    def __init__(
        self,
        client: TurbineClient,
        assets: list[str],
        allocation_usdc: float = DEFAULT_ALLOCATION_USDC,
        spread: float = DEFAULT_SPREAD,
        num_levels: int = DEFAULT_NUM_LEVELS,
        sensitivity: float = DEFAULT_PRICE_SENSITIVITY,
    ):
        self.client = client
        self.assets = assets
        self.allocation_usdc = allocation_usdc
        self.base_spread = spread
        self.num_levels = num_levels
        self.price_sensitivity = sensitivity
        self.running = True

        # Per-asset state
        self.asset_states: dict[str, AssetState] = {
            asset: AssetState(asset) for asset in assets
        }

        # Track approved settlement contracts (shared across assets)
        self.approved_settlements: dict[str, int] = {}

        # Async HTTP client for non-blocking price fetches
        self._http_client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Pyth price fetching
    # ------------------------------------------------------------------

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        return self._http_client

    async def close(self) -> None:
        """Close the async HTTP client."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def get_current_prices(self) -> dict[str, float]:
        """Fetch current prices for all active assets from Pyth Network in one request."""
        try:
            http_client = await self._get_http_client()
            feed_ids = [PYTH_FEED_IDS[asset] for asset in self.assets]
            response = await http_client.get(
                PYTH_HERMES_URL,
                params=[("ids[]", fid) for fid in feed_ids],
            )
            response.raise_for_status()
            data = response.json()

            prices: dict[str, float] = {}
            if not data.get("parsed"):
                return prices

            # Map feed IDs back to assets
            feed_to_asset = {PYTH_FEED_IDS[asset]: asset for asset in self.assets}

            for parsed in data["parsed"]:
                feed_id = "0x" + parsed["id"]
                asset = feed_to_asset.get(feed_id)
                if asset:
                    price_data = parsed["price"]
                    price_int = int(price_data["price"])
                    expo = price_data["expo"]
                    prices[asset] = price_int * (10 ** expo)

            return prices

        except Exception as e:
            print(f"Failed to fetch prices from Pyth: {e}")
            return {}

    # ------------------------------------------------------------------
    # Dynamic probability pricing (matching Go MM)
    # ------------------------------------------------------------------

    def calculate_target_prices_with_time(
        self, state: AssetState, current_price: float
    ) -> tuple[float, float]:
        """Calculate YES target probability and dynamic spread for an asset.

        Uses the same formula as the Go MM's calculateTargetPricesWithTime:
        - Time factor: elapsed / total duration (0.0 at start, 1.0 at expiration)
        - Effective sensitivity: base * (1 + timeFactor * TimeDecayFactor)
        - YES target: BaseProbability +/- adjustment
        - Spread tightens: base * (1 - timeFactor * 0.75), min 0.5%

        Returns:
            (yes_target, spread) as floats (e.g., 0.65 = 65%, 0.02 = 2%)
        """
        strike_usd = state.strike_price / 1e6
        if strike_usd <= 0 or current_price <= 0:
            return DEFAULT_BASE_PROBABILITY, self.base_spread

        # Time factor (0.0 at start, 1.0 at expiration)
        now = int(time.time())
        total_duration = state.market_end_time - state.market_start_time
        if total_duration <= 0:
            time_factor = 0.0
        else:
            elapsed = now - state.market_start_time
            time_factor = max(0.0, min(1.0, elapsed / total_duration))

        # Price deviation as percentage
        deviation_pct = ((current_price - strike_usd) / strike_usd) * 100

        # Effective sensitivity (increases toward expiration)
        effective_sensitivity = self.price_sensitivity * (1.0 + time_factor * DEFAULT_TIME_DECAY_FACTOR)

        # Probability adjustment
        max_adjustment = DEFAULT_MAX_PROBABILITY - DEFAULT_BASE_PROBABILITY
        adjustment = min(max_adjustment, abs(deviation_pct) * effective_sensitivity)

        # YES target probability
        if current_price > strike_usd:
            yes_target = min(DEFAULT_MAX_PROBABILITY, DEFAULT_BASE_PROBABILITY + adjustment)
        elif current_price < strike_usd:
            yes_target = max(1.0 - DEFAULT_MAX_PROBABILITY, DEFAULT_BASE_PROBABILITY - adjustment)
        else:
            yes_target = DEFAULT_BASE_PROBABILITY

        # Spread tightens toward expiration
        spread = self.base_spread * (1.0 - time_factor * SPREAD_TIGHTENING)
        spread = max(MIN_SPREAD, spread)

        return yes_target, spread

    # ------------------------------------------------------------------
    # Multi-level geometric distribution (matching Go MM)
    # ------------------------------------------------------------------

    def calculate_geometric_weights(self, n: int, side: str) -> list[float]:
        """Calculate geometric size distribution weights.

        Uses lambda^i for BUY (concentrate at best/highest price) and
        lambda^(n-1-i) for SELL (concentrate at best/lowest price).
        Weights are normalized to sum to 1.

        Args:
            n: Number of levels
            side: "BUY" or "SELL"

        Returns:
            Normalized weights list (sums to 1.0)
        """
        lam = DEFAULT_GEOMETRIC_LAMBDA
        weights = []
        for i in range(n):
            if side == "BUY":
                # Concentrate at higher indices (best bid = highest price)
                w = lam ** i
            else:
                # Concentrate at lower indices (best ask = lowest price)
                w = lam ** (n - 1 - i)
            weights.append(w)

        total = sum(weights)
        if total <= 0:
            return [1.0 / n] * n
        return [w / total for w in weights]

    def generate_level_prices(
        self, min_price: float, max_price: float, n: int
    ) -> list[int]:
        """Generate evenly spaced prices from min to max.

        Args:
            min_price: Lowest price as float (e.g., 0.45)
            max_price: Highest price as float (e.g., 0.55)
            n: Number of levels

        Returns:
            List of prices in 6-decimal integer format, clamped to [10000, 990000]
        """
        if n <= 1:
            mid = (min_price + max_price) / 2
            return [max(10000, min(990000, int(mid * 1_000_000)))]

        step = (max_price - min_price) / (n - 1)
        prices = []
        for i in range(n):
            p = min_price + i * step
            p_int = max(10000, min(990000, int(p * 1_000_000)))
            prices.append(p_int)
        return prices

    # ------------------------------------------------------------------
    # USDC helpers
    # ------------------------------------------------------------------

    def calculate_shares_from_usdc(self, usdc_amount: float, price: int) -> int:
        """Calculate shares from USDC amount at given price.

        Args:
            usdc_amount: Amount of USDC to spend (e.g., 10.0 for $10)
            price: Price per share in 6 decimals (e.g., 500000 = 50%)

        Returns:
            Number of shares in 6 decimals
        """
        if price <= 0:
            return 0
        return int((usdc_amount * 1_000_000 * 1_000_000) / price)

    # Half of max uint256 — threshold for "already has max approval"
    MAX_APPROVAL_THRESHOLD = (2**256 - 1) // 2

    def ensure_settlement_approved(self, settlement_address: str) -> None:
        """Ensure USDC is approved for the settlement contract.

        Uses a gasless max permit via the relayer. No native gas required.
        """
        # Check if already approved in this session
        if settlement_address in self.approved_settlements:
            return

        # Check on-chain allowance
        current_allowance = self.client.get_usdc_allowance(spender=settlement_address)

        if current_allowance >= self.MAX_APPROVAL_THRESHOLD:
            print(f"  Existing USDC max approval found")
            self.approved_settlements[settlement_address] = current_allowance
            return

        # Need to approve via gasless max permit
        print(f"\n{'='*50}")
        print(f"GASLESS USDC APPROVAL (one-time max permit)")
        print(f"{'='*50}")
        print(f"Settlement: {settlement_address}")

        try:
            result = self.client.approve_usdc_for_settlement(settlement_address)
            tx_hash = result.get("tx_hash", "unknown")
            print(f"Relayer TX: {tx_hash}")
            print("Waiting for confirmation...")

            # Wait for confirmation
            from web3 import Web3
            rpc_urls = {
                137: "https://polygon-rpc.com",
                43114: "https://api.avax.network/ext/bc/C/rpc",
                84532: "https://sepolia.base.org",
            }
            rpc_url = rpc_urls.get(self.client.chain_id)
            w3 = Web3(Web3.HTTPProvider(rpc_url))

            for _ in range(30):
                try:
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    if receipt:
                        if receipt["status"] == 1:
                            print(f"Max USDC approval confirmed (gasless)")
                            self.approved_settlements[settlement_address] = 2**256 - 1
                        else:
                            print(f"Transaction failed!")
                        break
                except Exception:
                    pass
                time.sleep(1)
            else:
                print(f"Transaction pending (may still confirm)")
                self.approved_settlements[settlement_address] = 2**256 - 1

        except Exception as e:
            print(f"Gasless approval failed: {e}")
            raise

        print(f"{'='*50}\n")

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    async def cancel_all_orders(self) -> None:
        """Cancel all open orders by querying the API."""
        try:
            open_orders = self.client.get_orders(
                trader=self.client.address, status="open"
            )
        except Exception as e:
            print(f"Failed to fetch open orders: {e}")
            return

        if not open_orders:
            return

        print(f"Cancelling {len(open_orders)} open orders...")
        cancelled = 0
        for order in open_orders:
            try:
                self.client.cancel_order(
                    order.order_hash,
                    market_id=order.market_id,
                    side=Side(order.side),
                )
                cancelled += 1
            except TurbineApiError as e:
                if "404" not in str(e):
                    print(f"  Failed to cancel {order.order_hash[:10]}...: {e}")
        print(f"  Cancelled {cancelled}/{len(open_orders)} orders")
        for state in self.asset_states.values():
            state.active_orders.clear()

    async def cancel_asset_orders(self, state: AssetState) -> None:
        """Cancel all open orders for a specific asset's market."""
        if not state.market_id:
            return
        try:
            open_orders = self.client.get_orders(
                trader=self.client.address,
                market_id=state.market_id,
                status="open",
            )
        except Exception:
            return

        for order in open_orders:
            try:
                self.client.cancel_order(
                    order.order_hash,
                    market_id=order.market_id,
                    side=Side(order.side),
                )
            except TurbineApiError:
                pass
        state.active_orders.clear()

    async def place_multi_level_quotes(self, state: AssetState) -> dict[str, str]:
        """Place multi-level bid and ask orders on both YES and NO outcomes for an asset.

        YES side: Bids below yes_target, asks above yes_target.
        NO side: Bids below no_target (1 - yes_target), asks above no_target.

        Returns:
            Dict of order_hash -> side for newly placed orders.
        """
        new_orders: dict[str, str] = {}

        n = self.num_levels
        half_spread = state.current_spread / 2
        no_target = 1.0 - state.yes_target
        expiration = int(time.time()) + 300  # 5 minute expiration

        # Generate geometric weights
        buy_weights = self.calculate_geometric_weights(n, "BUY")
        sell_weights = self.calculate_geometric_weights(n, "SELL")

        # Split allocation: 2 outcomes x 2 sides = 4 buckets
        usdc_per_side = self.allocation_usdc / 4

        print(
            f"[{state.asset}] Quoting {n} levels x 2 outcomes: "
            f"YES {state.yes_target:.1%} / NO {no_target:.1%} | "
            f"Spread {state.current_spread:.1%} | "
            f"${usdc_per_side:.2f}/side"
        )

        for outcome, target in [(Outcome.YES, state.yes_target), (Outcome.NO, no_target)]:
            outcome_name = "YES" if outcome == Outcome.YES else "NO"

            # Derive bid/ask ranges for this outcome
            bid_max = target - half_spread  # Best bid
            bid_min = max(0.01, bid_max - state.current_spread)
            ask_min = target + half_spread  # Best ask
            ask_max = min(0.99, ask_min + state.current_spread)

            # Clamp
            bid_min = max(0.01, bid_min)
            bid_max = max(bid_min + 0.01, min(0.99, bid_max))
            ask_min = max(0.01, ask_min)
            ask_max = max(ask_min + 0.01, min(0.99, ask_max))

            bid_prices = self.generate_level_prices(bid_min, bid_max, n)
            ask_prices = self.generate_level_prices(ask_min, ask_max, n)

            # Place bid levels (BUY outcome)
            for i in range(n):
                usdc_for_level = usdc_per_side * buy_weights[i]
                if usdc_for_level < 0.01:
                    continue
                price = bid_prices[i]
                shares = self.calculate_shares_from_usdc(usdc_for_level, price)
                if shares <= 0:
                    continue
                try:
                    order = self.client.create_limit_buy(
                        market_id=state.market_id,
                        outcome=outcome,
                        price=price,
                        size=shares,
                        expiration=expiration,
                        settlement_address=state.settlement_address,
                    )
                    self.client.post_order(order)
                    new_orders[order.order_hash] = f"BUY_{outcome_name}"
                except TurbineApiError as e:
                    print(f"  [{state.asset}] Failed {outcome_name} bid L{i}: {e}")

            # Place ask levels (SELL outcome)
            for i in range(n):
                usdc_for_level = usdc_per_side * sell_weights[i]
                if usdc_for_level < 0.01:
                    continue
                price = ask_prices[i]
                shares = self.calculate_shares_from_usdc(usdc_for_level, price)
                if shares <= 0:
                    continue
                try:
                    order = self.client.create_limit_sell(
                        market_id=state.market_id,
                        outcome=outcome,
                        price=price,
                        size=shares,
                        expiration=expiration,
                        settlement_address=state.settlement_address,
                    )
                    self.client.post_order(order)
                    new_orders[order.order_hash] = f"SELL_{outcome_name}"
                except TurbineApiError as e:
                    print(f"  [{state.asset}] Failed {outcome_name} ask L{i}: {e}")

        if new_orders:
            yes_orders = sum(1 for s in new_orders.values() if "YES" in s)
            no_orders = sum(1 for s in new_orders.values() if "NO" in s)
            print(f"  [{state.asset}] Placed {yes_orders} YES + {no_orders} NO orders ({len(new_orders)} total)")

        return new_orders

    async def update_quotes(self, state: AssetState) -> None:
        """Cancel all open orders for an asset's market, then place new ones."""
        await self.cancel_asset_orders(state)

        new_orders = await self.place_multi_level_quotes(state)
        state.active_orders.update(new_orders)

    # ------------------------------------------------------------------
    # Market lifecycle
    # ------------------------------------------------------------------

    async def get_active_market(self, asset: str) -> tuple[str, int, int, int] | None:
        """Get the currently active quick market for an asset.

        Returns:
            (market_id, start_time, end_time, start_price) or None
        """
        response = self.client._http.get(f"/api/v1/quick-markets/{asset}")
        quick_market_data = response.get("quickMarket")
        if not quick_market_data:
            return None
        quick_market = QuickMarket.from_dict(quick_market_data)
        return (
            quick_market.market_id,
            quick_market.start_time,
            quick_market.end_time,
            quick_market.start_price,
        )

    async def switch_to_new_market(
        self, state: AssetState, new_market_id: str, start_time: int = 0, end_time: int = 0, start_price: int = 0
    ) -> None:
        """Switch an asset to a new market and ensure gasless USDC approval."""
        old_market_id = state.market_id

        # Track old market for claiming winnings
        if old_market_id and state.contract_address:
            state.traded_markets[old_market_id] = state.contract_address

        if old_market_id:
            print(f"\n{'='*50}")
            print(f"[{state.asset}] MARKET TRANSITION")
            print(f"Old: {old_market_id[:8]}... | New: {new_market_id[:8]}...")
            print(f"{'='*50}\n")
            # Orders on expired markets are auto-removed by the API — just clear tracking
            state.active_orders.clear()

        # Update market state
        state.market_id = new_market_id
        state.strike_price = start_price
        state.market_start_time = start_time
        state.market_end_time = end_time
        state.active_orders = {}

        # Reset dynamic pricing state
        state.yes_target = DEFAULT_BASE_PROBABILITY
        state.current_spread = self.base_spread
        state.yes_target_at_rebalance = DEFAULT_BASE_PROBABILITY
        state.last_rebalance_time = 0

        # Fetch settlement and contract addresses
        try:
            markets = self.client.get_markets()
            for market in markets:
                if market.id == new_market_id:
                    state.settlement_address = market.settlement_address
                    try:
                        stats = self.client.get_market(new_market_id)
                        state.contract_address = stats.contract_address
                    except Exception:
                        pass
                    break
        except Exception as e:
            print(f"[{state.asset}] Warning: Could not fetch market addresses: {e}")

        # Ensure gasless USDC approval for this settlement contract
        if state.settlement_address:
            self.ensure_settlement_approved(state.settlement_address)

        strike_usd = start_price / 1e6 if start_price else 0
        per_side = self.allocation_usdc / 4
        print(f"[{state.asset}] Trading market: {new_market_id[:8]}... | Strike: ${strike_usd:,.2f} | ${self.allocation_usdc:.2f} allocation (${per_side:.2f}/side)")

    async def monitor_market_transitions(self) -> None:
        """Background task that polls for new markets across all assets."""
        POLL_INTERVAL = 5

        while self.running:
            try:
                for asset in self.assets:
                    state = self.asset_states[asset]

                    try:
                        market_info = await self.get_active_market(asset)
                    except Exception as e:
                        print(f"[{asset}] Market monitor error: {e}")
                        continue

                    if not market_info:
                        continue

                    new_market_id, start_time, end_time, start_price = market_info

                    if new_market_id != state.market_id:
                        await self.switch_to_new_market(
                            state, new_market_id, start_time, end_time, start_price
                        )
                    else:
                        # Update end_time in case it changed
                        state.market_end_time = end_time

            except Exception as e:
                print(f"Market monitor error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    async def claim_resolved_markets(self) -> None:
        """Background task to claim winnings from resolved markets across all assets."""
        retry_delay = 120

        while self.running:
            try:
                # Collect all traded markets across all assets
                all_traded: list[tuple[str, str, AssetState]] = []
                for state in self.asset_states.values():
                    for market_id, contract_address in list(state.traded_markets.items()):
                        all_traded.append((market_id, contract_address, state))

                if not all_traded:
                    await asyncio.sleep(retry_delay)
                    continue

                for market_id, contract_address, state in all_traded:
                    try:
                        resolution = self.client.get_resolution(market_id)
                        if not (resolution and resolution.resolved):
                            continue
                    except Exception:
                        continue

                    try:
                        result = self.client.claim_winnings(contract_address)
                        tx_hash = result.get("txHash", result.get("tx_hash", "unknown"))
                        print(f"[{state.asset}] 💰 Claimed winnings from {market_id[:8]}... TX: {tx_hash}")
                        del state.traded_markets[market_id]
                    except ValueError as e:
                        if "no winning tokens" in str(e).lower():
                            del state.traded_markets[market_id]
                    except Exception as e:
                        print(f"[{state.asset}] Claim error: {e}")

                    await asyncio.sleep(15)

            except Exception as e:
                print(f"Claim monitor error: {e}")

            await asyncio.sleep(retry_delay)

    # ------------------------------------------------------------------
    # Main trading loop
    # ------------------------------------------------------------------

    async def market_making_loop(self) -> None:
        """Price-driven market making loop with WebSocket for trade/book events.

        Primary quoting is probability-based from Pyth prices per asset.
        WebSocket provides trade notifications for all active markets.
        Requotes only when YES target shifts by >REBALANCE_THRESHOLD per asset.
        """
        if CLAIM_ONLY_MODE:
            print("CLAIM ONLY MODE - Trading disabled")
            while self.running:
                await asyncio.sleep(60)
            return

        while self.running:
            # Wait until at least one asset has an active market
            active_assets = [a for a in self.assets if self.asset_states[a].market_id]
            if not active_assets:
                await asyncio.sleep(1)
                continue

            ws = TurbineWSClient(host=TURBINE_HOST)

            try:
                async with ws.connect() as stream:
                    # Subscribe to all active asset markets
                    subscribed_markets: dict[str, str] = {}  # market_id -> asset
                    for asset in active_assets:
                        state = self.asset_states[asset]
                        await stream.subscribe(state.market_id)
                        subscribed_markets[state.market_id] = asset
                        print(f"[{asset}] Subscribed to orderbook updates for {state.market_id[:10]}...")

                    last_price_check = 0

                    # Initial price fetch and quote placement
                    prices = await self.get_current_prices()
                    for asset in active_assets:
                        state = self.asset_states[asset]
                        current_price = prices.get(asset, 0.0)
                        if current_price > 0:
                            state.yes_target, state.current_spread = self.calculate_target_prices_with_time(state, current_price)
                            state.yes_target_at_rebalance = state.yes_target
                            state.last_rebalance_time = int(time.time())

                        new_orders = await self.place_multi_level_quotes(state)
                        state.active_orders.update(new_orders)

                    last_price_check = time.time()

                    while self.running:
                        try:
                            messages = await asyncio.wait_for(
                                stream.recv(), timeout=REFRESH_INTERVAL
                            )
                        except asyncio.TimeoutError:
                            messages = []
                        except WebSocketError:
                            break  # Connection closed — reconnect

                        # Check if any asset's market changed — resubscribe as needed
                        needs_reconnect = False
                        for asset in self.assets:
                            state = self.asset_states[asset]
                            if not state.market_id:
                                continue

                            if state.market_id not in subscribed_markets:
                                # New market for this asset — need to subscribe
                                # Find and unsubscribe old market for this asset
                                old_market_ids = [mid for mid, a in subscribed_markets.items() if a == asset]
                                for old_mid in old_market_ids:
                                    await stream.unsubscribe(old_mid)
                                    del subscribed_markets[old_mid]

                                await stream.subscribe(state.market_id)
                                subscribed_markets[state.market_id] = asset
                                print(f"[{asset}] Subscribed to new market {state.market_id[:10]}...")

                                # Fetch price and place initial quotes on new market
                                prices = await self.get_current_prices()
                                current_price = prices.get(asset, 0.0)
                                if current_price > 0:
                                    state.yes_target, state.current_spread = self.calculate_target_prices_with_time(state, current_price)
                                    state.yes_target_at_rebalance = state.yes_target
                                    state.last_rebalance_time = int(time.time())

                                new_orders = await self.place_multi_level_quotes(state)
                                state.active_orders.update(new_orders)

                        # Process received messages
                        for message in messages:
                            if message.type == "trade":
                                if hasattr(message, "trade") and message.trade:
                                    trade = message.trade
                                    # Find which asset this trade belongs to
                                    trade_asset = None
                                    for asset in self.assets:
                                        s = self.asset_states[asset]
                                        if s.market_id and hasattr(trade, 'market_id') and trade.market_id == s.market_id:
                                            trade_asset = asset
                                            break
                                    if not trade_asset:
                                        # Try to match via subscribed_markets
                                        for mid, a in subscribed_markets.items():
                                            trade_asset = a
                                            break

                                    price_pct = trade.price / 10000
                                    shares = trade.size / 1_000_000
                                    outcome_str = "YES" if trade.outcome == 0 else "NO"
                                    is_ours = trade.buyer.lower() == self.client.address.lower()
                                    prefix = f"  [{trade_asset or '?'}] -> Our fill" if is_ours else f"[{trade_asset or '?'}] Trade"
                                    print(f"{prefix}: {shares:.2f} {outcome_str} @ {price_pct:.2f}%")

                        # Periodic price check and rebalance evaluation
                        now = time.time()
                        if now - last_price_check >= REFRESH_INTERVAL:
                            last_price_check = now

                            prices = await self.get_current_prices()

                            for asset in self.assets:
                                state = self.asset_states[asset]
                                if not state.market_id:
                                    continue

                                current_price = prices.get(asset, 0.0)
                                if current_price <= 0:
                                    continue

                                new_yes_target, new_spread = self.calculate_target_prices_with_time(state, current_price)
                                state.yes_target = new_yes_target
                                state.current_spread = new_spread

                                # Check rebalance threshold
                                target_diff = abs(new_yes_target - state.yes_target_at_rebalance)
                                time_since_rebalance = int(now) - state.last_rebalance_time

                                if (target_diff > REBALANCE_THRESHOLD
                                        and time_since_rebalance >= MIN_REBALANCE_INTERVAL):
                                    strike_usd = state.strike_price / 1e6
                                    dev_pct = ((current_price - strike_usd) / strike_usd) * 100 if strike_usd > 0 else 0
                                    print(
                                        f"[{asset}] Rebalance: ${current_price:,.2f} ({dev_pct:+.2f}% from ${strike_usd:,.2f}) | "
                                        f"YES {state.yes_target_at_rebalance:.1%} -> {new_yes_target:.1%} "
                                        f"(delta {target_diff:.1%}) | Spread {new_spread:.1%}"
                                    )
                                    await self.update_quotes(state)
                                    state.yes_target_at_rebalance = new_yes_target
                                    state.last_rebalance_time = int(now)

            except WebSocketError as e:
                print(f"WebSocket error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Market making error: {e}")
                await asyncio.sleep(5)

    async def run(self) -> None:
        """Main entry point — starts all background tasks."""
        monitor_task = asyncio.create_task(self.monitor_market_transitions())
        claim_task = asyncio.create_task(self.claim_resolved_markets())
        trading_task = asyncio.create_task(self.market_making_loop())

        try:
            # Initialize all asset markets
            for asset in self.assets:
                try:
                    market_info = await self.get_active_market(asset)
                    if market_info:
                        market_id, start_time, end_time, start_price = market_info
                        await self.switch_to_new_market(
                            self.asset_states[asset], market_id, start_time, end_time, start_price
                        )
                    else:
                        print(f"[{asset}] Waiting for market...")
                except Exception as e:
                    print(f"[{asset}] Failed to get initial market: {e}")

            while self.running:
                await asyncio.sleep(1)

        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            self.running = False
            monitor_task.cancel()
            claim_task.cancel()
            trading_task.cancel()
            await asyncio.gather(monitor_task, claim_task, trading_task, return_exceptions=True)
            await self.close()


async def main():
    parser = argparse.ArgumentParser(
        description="Turbine market maker for BTC, ETH, and SOL 15-minute prediction markets"
    )
    parser.add_argument(
        "-a", "--allocation",
        type=float,
        default=DEFAULT_ALLOCATION_USDC,
        help=f"Total USDC allocation per asset per market, split across all sides and levels (default: ${DEFAULT_ALLOCATION_USDC})"
    )
    parser.add_argument(
        "--spread",
        type=float,
        default=DEFAULT_SPREAD,
        help=f"Base spread as decimal (default: {DEFAULT_SPREAD} = {DEFAULT_SPREAD * 100:.0f}%%)"
    )
    parser.add_argument(
        "--levels",
        type=int,
        default=DEFAULT_NUM_LEVELS,
        help=f"Number of price levels per side (default: {DEFAULT_NUM_LEVELS})"
    )
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=DEFAULT_PRICE_SENSITIVITY,
        help=f"Probability shift per 1%% price move (default: {DEFAULT_PRICE_SENSITIVITY})"
    )
    parser.add_argument(
        "--assets",
        type=str,
        default=",".join(SUPPORTED_ASSETS),
        help=f"Comma-separated list of assets to trade (default: {','.join(SUPPORTED_ASSETS)})"
    )
    args = parser.parse_args()

    # Parse and validate assets
    assets = [a.strip().upper() for a in args.assets.split(",")]
    for asset in assets:
        if asset not in PYTH_FEED_IDS:
            print(f"Error: Unsupported asset '{asset}'. Supported: {', '.join(SUPPORTED_ASSETS)}")
            return

    private_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if not private_key:
        print("Error: Set TURBINE_PRIVATE_KEY in your .env file")
        return

    api_key_id, api_private_key = get_or_create_api_credentials()

    client = TurbineClient(
        host=TURBINE_HOST,
        chain_id=CHAIN_ID,
        private_key=private_key,
        api_key_id=api_key_id,
        api_private_key=api_private_key,
    )

    print(f"\n{'='*60}")
    print(f"TURBINE MARKET MAKER")
    print(f"{'='*60}")
    print(f"Wallet: {client.address}")
    print(f"Chain: {CHAIN_ID}")
    print(f"Assets: {', '.join(assets)}")
    per_side = args.allocation / 4
    print(f"Allocation: ${args.allocation:.2f} USDC per asset (${per_side:.2f}/side x 4 sides, {args.levels} levels each)")
    print(f"Spread: {args.spread * 100:.1f}% (tightens to {MIN_SPREAD * 100:.1f}% at expiry)")
    print(f"Sensitivity: {args.sensitivity} per 1% move (x{1 + DEFAULT_TIME_DECAY_FACTOR:.0f} at expiry)")
    print(f"Rebalance: >{REBALANCE_THRESHOLD * 100:.0f}% target shift, min {MIN_REBALANCE_INTERVAL}s apart")
    print(f"Lambda: {DEFAULT_GEOMETRIC_LAMBDA} (geometric distribution)")
    print(f"USDC approval: gasless (one-time max permit per settlement)")
    try:
        usdc_balance = client.get_usdc_balance()
        balance_display = usdc_balance / 1_000_000
        print(f"USDC balance: ${balance_display:.2f}")
        min_needed = args.allocation * len(assets)
        if balance_display < min_needed:
            print(f"⚠️  Warning: Balance (${balance_display:.2f}) may be low for {len(assets)} assets x ${args.allocation:.2f}")
            print(f"   Fund your wallet: {client.address}")
    except Exception as e:
        print(f"USDC balance: unknown ({e})")
    print(f"{'='*60}\n")

    bot = MarketMaker(
        client,
        assets=assets,
        allocation_usdc=args.allocation,
        spread=args.spread,
        num_levels=args.levels,
        sensitivity=args.sensitivity,
    )

    try:
        await bot.run()
    except KeyboardInterrupt:
        pass
    finally:
        print("\nShutting down...")
        bot.running = False
        await bot.cancel_all_orders()
        await bot.close()
        client.close()
        print("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
