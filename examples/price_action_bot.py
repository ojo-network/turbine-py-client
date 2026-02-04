"""
Turbine Market Maker Bot - Price Action Trader
Generated for Turbine

Algorithm: Fetches real-time BTC price from Pyth Network (same oracle Turbine uses)
           and compares it to the market's strike price to make trading decisions.
           - If BTC is above strike → buy YES (bet it stays above)
           - If BTC is below strike → buy NO (bet it stays below)
           - Confidence scales with distance from strike price
"""

import asyncio
import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
import httpx

from turbine_client import TurbineClient, Outcome, Side, QuickMarket
from turbine_client.exceptions import TurbineApiError

# Load environment variables
load_dotenv()

# ============================================================
# CONFIGURATION - Adjust these parameters for your strategy
# ============================================================
# Claim-only mode: Set CLAIM_ONLY_MODE=true in .env to disable trading
CLAIM_ONLY_MODE = os.environ.get("CLAIM_ONLY_MODE", "false").lower() == "true"
# Chain ID: Set CHAIN_ID in .env (default: 137 for Polygon mainnet)
CHAIN_ID = int(os.environ.get("CHAIN_ID", "137"))
ORDER_SIZE = 1_000_000  # 1 share (6 decimals)
MAX_POSITION = 5_000_000  # Maximum position size (5 shares)
PRICE_POLL_SECONDS = 10  # How often to check BTC price

# Price Action parameters
PRICE_THRESHOLD_BPS = 10  # 0.1% threshold before taking action
MIN_CONFIDENCE = 0.6  # Minimum confidence to place a trade
MAX_CONFIDENCE = 0.9  # Cap confidence at 90%

# Pyth Network Hermes API - same price source Turbine uses
PYTH_HERMES_URL = "https://hermes.pyth.network/v2/updates/price/latest"
PYTH_BTC_FEED_ID = "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43"


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
        host="https://api.turbinefi.com",
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


class PriceActionBot:
    """Price action trader that follows BTC price vs strike price."""

    def __init__(self, client: TurbineClient):
        self.client = client
        self.market_id: str | None = None
        self.settlement_address: str | None = None
        self.contract_address: str | None = None
        self.strike_price: int = 0  # BTC price when market created (6 decimals)
        self.current_position = 0
        self.active_orders: dict[str, str] = {}  # order_hash -> side
        self.running = True
        # Track markets we've traded in for claiming winnings
        self.traded_markets: dict[str, str] = {}  # market_id -> contract_address
        # Track processed trades to avoid double-counting
        self.processed_trade_ids: set[int] = set()
        # Track pending order TXs to prevent placing new orders while orders are settling
        self.pending_order_txs: set[str] = set()
        # Async HTTP client for non-blocking price fetches
        self._http_client: httpx.AsyncClient | None = None
        # Stop trading when market is about to expire
        self.market_expiring = False

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        return self._http_client

    async def close(self) -> None:
        """Close the async HTTP client."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def cleanup_pending_orders(self) -> None:
        """Check pending orders and remove any that have settled or failed."""
        try:
            pending_trades = self.client.get_pending_trades()
            pending_txs = {t.tx_hash for t in pending_trades
                          if t.market_id == self.market_id
                          and t.buyer_address.lower() == self.client.address.lower()}

            # Remove any TXs that are no longer pending
            resolved_txs = self.pending_order_txs - pending_txs
            if resolved_txs:
                print(f"  {len(resolved_txs)} order(s) settled")
                self.pending_order_txs -= resolved_txs

                # Check if they filled by looking at recent trades
                trades = self.client.get_trades(market_id=self.market_id, limit=20)
                # No time filter needed - processed_trade_ids prevents double-counting
                my_recent_trades = [t for t in trades
                                   if t.buyer.lower() == self.client.address.lower()
                                   and t.id not in self.processed_trade_ids]

                for trade in my_recent_trades:
                    self.processed_trade_ids.add(trade.id)
                    # Track position from filled trades (outcome: 0=YES, 1=NO)
                    if trade.outcome == 0:
                        self.current_position += trade.size
                        print(f"  Filled: {trade.size / 1_000_000:.2f} YES shares")
                    else:
                        self.current_position -= trade.size
                        print(f"  Filled: {trade.size / 1_000_000:.2f} NO shares")

        except Exception as e:
            print(f"  Warning: Could not cleanup pending orders: {e}")

    async def sync_position(self) -> None:
        """Sync position by checking user positions for current market."""
        if not self.market_id:
            return

        try:
            # Get all user positions
            positions = self.client.get_user_positions(
                address=self.client.address,
                chain_id=self.client.chain_id
            )

            # Find position for this market
            for position in positions:
                if position.market_id == self.market_id:
                    # Net position (positive = long YES, negative = long NO)
                    self.current_position = position.yes_shares - position.no_shares

                    if self.current_position != 0:
                        shares = abs(self.current_position) / 1_000_000
                        side = "YES" if self.current_position > 0 else "NO"
                        print(f"Position synced: {shares:.1f} {side} shares")
                    else:
                        print("Position synced: No existing positions")
                    return

            # No position found for this market
            self.current_position = 0
            print("Position synced: No existing positions")

        except Exception as e:
            print(f"Failed to sync position: {e}")
            # Default to 0 on error
            self.current_position = 0

    async def verify_position(self) -> None:
        """Verify position from API and correct if internal tracking is wrong."""
        if not self.market_id:
            return

        try:
            positions = self.client.get_user_positions(
                address=self.client.address,
                chain_id=self.client.chain_id
            )

            for position in positions:
                if position.market_id == self.market_id:
                    actual_position = position.yes_shares - position.no_shares

                    # Check if internal tracking is off
                    if actual_position != self.current_position:
                        old_shares = abs(self.current_position) / 1_000_000
                        new_shares = abs(actual_position) / 1_000_000
                        print(f"  ⚠ Position corrected: {old_shares:.1f} → {new_shares:.1f} shares (verified from API)")
                        self.current_position = actual_position
                    return

            # No position found
            if self.current_position != 0:
                print(f"  ⚠ Position corrected: {abs(self.current_position) / 1_000_000:.1f} → 0 shares")
                self.current_position = 0

        except Exception as e:
            print(f"  Warning: Could not verify position: {e}")

    async def get_current_btc_price(self) -> float:
        """Fetch current BTC price from Pyth Network (same source as Turbine)."""
        try:
            http_client = await self._get_http_client()
            response = await http_client.get(
                PYTH_HERMES_URL,
                params={"ids[]": PYTH_BTC_FEED_ID},
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("parsed"):
                print("No price data from Pyth")
                return 0.0

            price_data = data["parsed"][0]["price"]
            price_int = int(price_data["price"])
            expo = price_data["expo"]  # Usually -8 for BTC

            # Convert Pyth price to USD: price * 10^expo
            return price_int * (10 ** expo)

        except Exception as e:
            print(f"Failed to fetch BTC price from Pyth: {e}")
            return 0.0

    async def calculate_signal(self) -> tuple[str, float]:
        """
        Calculate trading signal based on current price vs strike price.

        Returns:
            (action, confidence) where action is "BUY_YES", "BUY_NO", or "HOLD"
        """
        current_price = await self.get_current_btc_price()
        if current_price <= 0:
            return "HOLD", 0.0

        # Convert strike price from 6 decimals to USD
        strike_usd = self.strike_price / 1e6

        # Calculate percentage difference
        price_diff_pct = ((current_price - strike_usd) / strike_usd) * 100

        # Threshold check (0.5% = 50 bps)
        threshold_pct = PRICE_THRESHOLD_BPS / 100

        if abs(price_diff_pct) < threshold_pct:
            # Price too close to strike, hold
            return "HOLD", 0.0

        # Calculate confidence based on distance from strike
        # Further from strike = higher confidence (capped)
        raw_confidence = min(abs(price_diff_pct) / 2, MAX_CONFIDENCE)
        confidence = max(raw_confidence, MIN_CONFIDENCE) if abs(price_diff_pct) >= threshold_pct else 0.0

        if price_diff_pct > 0:
            # BTC is above strike → bet YES (will end above)
            print(f"BTC ${current_price:,.2f} is {price_diff_pct:+.2f}% above strike ${strike_usd:,.2f}")
            return "BUY_YES", confidence
        else:
            # BTC is below strike → bet NO (will end below)
            print(f"BTC ${current_price:,.2f} is {price_diff_pct:+.2f}% below strike ${strike_usd:,.2f}")
            return "BUY_NO", confidence

    async def execute_signal(self, action: str, confidence: float) -> None:
        """Execute the trading signal."""
        if action == "HOLD" or confidence < MIN_CONFIDENCE:
            return

        # Check if we have any pending orders being tracked
        if self.pending_order_txs:
            print(f"⏳ Waiting for {len(self.pending_order_txs)} pending order(s) to settle...")
            return

        # Don't place new orders when market is about to expire
        if self.market_expiring:
            print("⏰ Market expiring soon - not placing new orders")
            return

        # Check position limits
        if abs(self.current_position) >= MAX_POSITION:
            print("Position limit reached")
            return

        # Determine outcome and get the correct orderbook
        if action == "BUY_YES":
            outcome = Outcome.YES
        else:
            outcome = Outcome.NO

        # Get orderbook for the specific outcome
        try:
            orderbook = self.client.get_orderbook(self.market_id, outcome=outcome)
        except Exception as e:
            print(f"Failed to get orderbook: {e}")
            return

        if not orderbook.asks:
            print(f"No asks available for {outcome.name}")
            return

        # Pay slightly above best ask to ensure fill
        price = min(orderbook.asks[0].price + 5000, 999000)

        try:
            order = self.client.create_limit_buy(
                market_id=self.market_id,
                outcome=outcome,
                price=price,
                size=ORDER_SIZE,
                expiration=int(time.time()) + 300,
                settlement_address=self.settlement_address,
            )

            # Sign USDC permit for gasless execution
            buyer_cost = (ORDER_SIZE * price) // 1_000_000
            total_fee = ORDER_SIZE // 100  # 1% fee
            permit_amount = ((buyer_cost + total_fee) * 120) // 100  # 20% margin
            permit = self.client.sign_usdc_permit(
                value=permit_amount,
                settlement_address=self.settlement_address,
            )
            order.permit_signature = permit

            result = self.client.post_order(order)
            outcome_str = "YES" if outcome == Outcome.YES else "NO"

            # Check if order was accepted
            if result and isinstance(result, dict):
                status = result.get("status", "unknown")
                order_hash = result.get("orderHash", order.order_hash)

                print(f"→ Order submitted: {outcome_str} @ {price / 10000:.1f}% (initial status: {status})")

                # Wait briefly for order to be processed
                await asyncio.sleep(2)

                # Check for failed trades (match by market + buyer + size)
                try:
                    failed_trades = self.client.get_failed_trades()
                    my_failed = [t for t in failed_trades
                                 if t.market_id == self.market_id
                                 and t.buyer_address.lower() == self.client.address.lower()
                                 and t.fill_size == ORDER_SIZE]

                    if my_failed:
                        # Take most recent
                        failed = my_failed[0]
                        print(f"✗ Order FAILED")
                        print(f"  Reason: {failed.reason}")
                        print(f"  TX: {failed.tx_hash[:16]}...")
                        return
                except Exception as e:
                    print(f"  Warning: Could not check failed trades: {e}")

                # Check for pending trades
                try:
                    pending_trades = self.client.get_pending_trades()
                    my_pending = [t for t in pending_trades
                                  if t.market_id == self.market_id
                                  and t.buyer_address.lower() == self.client.address.lower()
                                  and t.fill_size == ORDER_SIZE]

                    if my_pending:
                        pending = my_pending[0]
                        print(f"⏳ Order still PENDING on-chain")
                        print(f"  TX: {pending.tx_hash[:16]}...")
                        print(f"  Not tracking position until settled")
                        # Track this TX so we don't place more orders
                        self.pending_order_txs.add(pending.tx_hash)
                        return
                except Exception as e:
                    print(f"  Warning: Could not check pending trades: {e}")

                # Check if order was immediately filled (look at recent trades)
                try:
                    trades = self.client.get_trades(market_id=self.market_id, limit=20)
                    # Look for trades from the last 10 seconds that we haven't processed yet
                    recent_threshold = time.time() - 10
                    my_trades = [t for t in trades
                                 if t.buyer.lower() == self.client.address.lower()
                                 and t.timestamp > recent_threshold
                                 and t.id not in self.processed_trade_ids]

                    if my_trades:
                        trade = my_trades[0]
                        print(f"✓ Order FILLED (immediate match)")
                        print(f"  Size: {trade.size / 1_000_000:.2f} shares")
                        print(f"  Price: {trade.price / 10000:.1f}%")

                        # Mark trade as processed
                        self.processed_trade_ids.add(trade.id)

                        # Track position
                        self.current_position += ORDER_SIZE if outcome == Outcome.YES else -ORDER_SIZE
                        return
                except Exception as e:
                    print(f"  Warning: Could not check trades: {e}")

                # Check if order is still open on orderbook
                try:
                    my_orders = self.client.get_orders(
                        trader=self.client.address,
                        market_id=self.market_id,
                    )
                    matching = [o for o in my_orders if o.order_hash == order_hash]

                    if matching:
                        print(f"✓ Order OPEN on orderbook")
                        print(f"  Order hash: {order_hash[:16]}...")
                        # Track as active order (position updated when filled, not here)
                        self.active_orders[order_hash] = action
                    else:
                        # Not in failed, not in pending, not in trades, not open - likely rejected
                        print(f"⚠ Order not found anywhere - may have been rejected")
                except Exception as e:
                    print(f"  Warning: Could not check open orders: {e}")

                # Verify actual position from API after order attempt
                await self.verify_position()

            else:
                print(f"⚠ Unexpected order response: {result}")

        except TurbineApiError as e:
            print(f"✗ Order failed: {e}")
        except Exception as e:
            print(f"✗ Unexpected error placing order: {e}")

    async def price_action_loop(self) -> None:
        """Main loop that monitors price and executes trades."""
        if CLAIM_ONLY_MODE:
            print("CLAIM ONLY MODE - Trading disabled, only claiming winnings")
            # Don't trade, just keep the task alive
            while self.running:
                await asyncio.sleep(60)
            return

        while self.running and self.market_id:
            try:
                # Check for settled pending orders first
                if self.pending_order_txs:
                    await self.cleanup_pending_orders()

                action, confidence = await self.calculate_signal()
                if action != "HOLD":
                    await self.execute_signal(action, confidence)
                else:
                    # Still log current price vs strike
                    current_price = await self.get_current_btc_price()
                    strike_usd = self.strike_price / 1e6
                    if current_price > 0:
                        diff_pct = ((current_price - strike_usd) / strike_usd) * 100
                        print(f"BTC ${current_price:,.2f} ({diff_pct:+.2f}% from strike ${strike_usd:,.2f}) - HOLDING")

                await asyncio.sleep(PRICE_POLL_SECONDS)
            except Exception as e:
                print(f"Price action error: {e}")
                await asyncio.sleep(PRICE_POLL_SECONDS)

    async def get_active_market(self) -> tuple[str, int, int] | None:
        """
        Get the currently active BTC quick market.
        Returns (market_id, end_time, start_price) tuple, or None if no active market.
        """
        response = self.client._http.get("/api/v1/quick-markets/BTC")
        quick_market_data = response.get("quickMarket")
        if not quick_market_data:
            return None
        quick_market = QuickMarket.from_dict(quick_market_data)
        return quick_market.market_id, quick_market.end_time, quick_market.start_price

    async def cancel_all_orders(self) -> None:
        """Cancel all active orders before switching markets."""
        if not self.active_orders or not self.market_id:
            return

        print(f"Cancelling {len(self.active_orders)} orders on market {self.market_id[:8]}...")
        for order_hash in list(self.active_orders.keys()):
            try:
                self.client.cancel_order(order_hash, market_id=self.market_id)
                del self.active_orders[order_hash]
            except TurbineApiError as e:
                print(f"Failed to cancel order {order_hash[:8]}...: {e}")

    async def switch_to_new_market(self, new_market_id: str, start_price: int = 0) -> None:
        """
        Switch liquidity and trading to a new market.
        Called when a new BTC 15-minute market becomes active.

        Args:
            new_market_id: The new market ID to switch to.
            start_price: The BTC price when market was created (6 decimals).
        """
        old_market_id = self.market_id

        # Track old market for claiming winnings later
        if old_market_id and self.contract_address:
            self.traded_markets[old_market_id] = self.contract_address
            print(f"✓ Tracking market {old_market_id[:16]}... for winnings claim")

        if old_market_id:
            print(f"\n{'='*50}")
            print(f"MARKET TRANSITION DETECTED")
            print(f"Old market: {old_market_id[:8]}...")
            print(f"New market: {new_market_id[:8]}...")
            print(f"{'='*50}\n")

            # Cancel all orders on the old market
            await self.cancel_all_orders()

        # Update to new market
        self.market_id = new_market_id
        self.strike_price = start_price
        self.active_orders = {}
        self.processed_trade_ids.clear()  # Clear trade history for new market
        self.pending_order_txs.clear()  # Clear pending orders for new market
        self.market_expiring = False  # Reset expiring flag for new market

        # Fetch settlement and contract addresses
        try:
            # get_markets returns list of Market objects with settlement_address
            markets = self.client.get_markets()
            for market in markets:
                if market.id == new_market_id:
                    self.settlement_address = market.settlement_address
                    # Get contract address from market stats
                    try:
                        stats = self.client.get_market(new_market_id)
                        self.contract_address = stats.contract_address
                        print(f"Settlement: {self.settlement_address[:16]}...")
                        print(f"Contract: {self.contract_address[:16]}...")
                    except Exception as e:
                        print(f"Warning: Could not fetch contract address: {e}")
                    break
        except Exception as e:
            print(f"Warning: Could not fetch market addresses: {e}")

        strike_usd = start_price / 1e6 if start_price else 0
        print(f"Now trading on market: {new_market_id[:8]}...")
        if strike_usd > 0:
            print(f"Strike price: ${strike_usd:,.2f}")

        # Sync position from on-chain data
        await self.sync_position()

    async def monitor_market_transitions(self) -> None:
        """
        Background task that polls for new markets and triggers transitions.
        Runs continuously while the bot is active.
        """
        POLL_INTERVAL = 5  # Check every 5 seconds

        while self.running:
            try:
                market_info = await self.get_active_market()

                # If no market available, wait for next poll
                if not market_info:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                new_market_id, end_time, start_price = market_info

                # Check if market has changed
                if new_market_id != self.market_id:
                    await self.switch_to_new_market(new_market_id, start_price)

                # Log time remaining and stop trading when market is about to expire
                time_remaining = end_time - int(time.time())
                if time_remaining <= 60 and time_remaining > 0:
                    if not self.market_expiring:
                        print(f"⏰ Market expires in {time_remaining}s - stopping new trades")
                        self.market_expiring = True
                elif time_remaining > 60:
                    self.market_expiring = False

            except Exception as e:
                print(f"Market monitor error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    async def discover_unclaimed_markets(self) -> None:
        """Discover markets with unclaimed winnings from previous sessions."""
        try:
            print("Scanning for unclaimed winnings from past markets...")

            # Get all user positions across all markets
            all_positions = self.client.get_user_positions(
                address=self.client.address,
                chain_id=self.client.chain_id
            )

            # Group positions by market and check if they have winning shares
            markets_with_positions = {}
            for position in all_positions:
                # Check if has any shares (YES or NO)
                if position.yes_shares > 0 or position.no_shares > 0:
                    market_id = position.market_id

                    if market_id not in markets_with_positions:
                        # Try to get market details and resolution
                        try:
                            # Get resolution to see which side won
                            resolution = self.client.get_resolution(market_id)

                            # Check if user has winning shares
                            has_winning_shares = False
                            if resolution and resolution.resolved:
                                if resolution.outcome == 0 and position.yes_shares > 0:  # YES won
                                    has_winning_shares = True
                                elif resolution.outcome == 1 and position.no_shares > 0:  # NO won
                                    has_winning_shares = True

                            if has_winning_shares:
                                # Get contract address
                                market = self.client.get_market(market_id)
                                if market.contract_address:
                                    markets_with_positions[market_id] = market.contract_address

                        except Exception as e:
                            # Market API failed - skip this market
                            pass

            # Add discovered markets to tracking
            for market_id, contract_address in markets_with_positions.items():
                if market_id not in self.traded_markets:
                    self.traded_markets[market_id] = contract_address
                    print(f"Added market {market_id[:16]}... to claim tracking")

            if markets_with_positions:
                print(f"Found {len(markets_with_positions)} market(s) with positions to check for winnings")
            else:
                print("No positions found with shares to claim")

        except Exception as e:
            print(f"Failed to discover unclaimed markets: {e}")

    async def claim_resolved_markets(self) -> None:
        """Background task to claim winnings from resolved markets using batch claiming."""
        # First run: discover markets from previous sessions
        await self.discover_unclaimed_markets()

        # Track retry delay for rate limiting
        retry_delay = 120  # Check every 2 minutes

        while self.running:
            try:
                if not self.traded_markets:
                    await asyncio.sleep(retry_delay)
                    continue

                # Filter to only resolved markets using API (no RPC!)
                market_items = list(self.traded_markets.items())
                resolved_markets = []

                print(f"\n💰 Checking {len(market_items)} market(s) for resolution status...")

                for market_id, contract_address in market_items:
                    try:
                        resolution = self.client.get_resolution(market_id)
                        if resolution and resolution.resolved:
                            resolved_markets.append((market_id, contract_address))
                            outcome_name = "YES" if resolution.outcome == 0 else "NO"
                            print(f"   ✓ {market_id[:8]}... is resolved (outcome: {outcome_name})")
                        else:
                            print(f"   ⏳ {market_id[:8]}... not resolved yet")
                    except Exception as e:
                        # Market might not have resolution endpoint yet
                        print(f"   ? {market_id[:8]}... resolution check failed: {e}")

                # Claim from resolved markets ONE AT A TIME to avoid rate limits
                if resolved_markets:
                    print(f"\n💰 Claiming from {len(resolved_markets)} resolved market(s) (one at a time)...")

                    for i, (market_id, contract_address) in enumerate(resolved_markets, 1):
                        print(f"   [{i}/{len(resolved_markets)}] Claiming from {market_id[:8]}...")

                        try:
                            result = self.client.claim_winnings(contract_address)
                            tx_hash = result.get("txHash", result.get("tx_hash", "unknown"))
                            print(f"   ✓ Claim successful! TX: {tx_hash}")

                            # Remove this market from tracking
                            del self.traded_markets[market_id]

                        except ValueError as e:
                            error_msg = str(e).lower()
                            if "no markets with winning tokens" in error_msg or "no winning tokens" in error_msg:
                                print(f"   No winning tokens (already claimed)")
                                # Remove from tracking since there's nothing to claim
                                del self.traded_markets[market_id]
                            else:
                                print(f"   Claim error: {e}")
                        except Exception as e:
                            error_str = str(e)
                            if "rate limit" in error_str.lower() or "too many requests" in error_str.lower():
                                print(f"   ⏳ Rate limited - will retry this market next cycle")
                                break  # Stop processing more markets
                            else:
                                print(f"   Error: {e}")

                        # Delay between markets to avoid rate limits (only if more to process)
                        if i < len(resolved_markets):
                            print(f"   Waiting 15s before next claim...")
                            await asyncio.sleep(15)

                else:
                    print("No resolved markets ready to claim yet")

            except Exception as e:
                print(f"Claim monitor error: {e}")

            await asyncio.sleep(retry_delay)

    async def run(self) -> None:
        """
        Main trading loop with automatic market switching and winnings claiming.
        """
        # Start background tasks
        monitor_task = asyncio.create_task(self.monitor_market_transitions())
        claim_task = asyncio.create_task(self.claim_resolved_markets())
        price_task = asyncio.create_task(self.price_action_loop())

        try:
            # Ensure we have a current market
            if not self.market_id:
                market_info = await self.get_active_market()
                if market_info:
                    market_id, _, start_price = market_info
                    await self.switch_to_new_market(market_id, start_price)
                else:
                    print("Waiting for a BTC market to become active...")

            # Keep running while tasks execute
            while self.running:
                await asyncio.sleep(1)

        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            self.running = False
            monitor_task.cancel()
            claim_task.cancel()
            price_task.cancel()

            # Wait for tasks to cancel
            await asyncio.gather(monitor_task, claim_task, price_task, return_exceptions=True)

            await self.cancel_all_orders()
            await self.close()  # Close async HTTP client


async def main():
    # Get credentials
    private_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if not private_key:
        print("Error: Set TURBINE_PRIVATE_KEY in your .env file")
        return

    api_key_id, api_private_key = get_or_create_api_credentials()

    # Create client
    client = TurbineClient(
        host="https://api.turbinefi.com",
        chain_id=CHAIN_ID,
        private_key=private_key,
        api_key_id=api_key_id,
        api_private_key=api_private_key,
    )

    print(f"Bot wallet address: {client.address}")
    print()

    # Get the initial active BTC 15-minute market
    print("Checking for active BTC market...")
    response = client._http.get("/api/v1/quick-markets/BTC")
    quick_market_data = response.get("quickMarket")

    if not quick_market_data:
        print("⚠️  No active BTC market right now.")
        print("The bot will wait for a new market to start and then begin trading.")
        print("Monitor task will check for new markets every 5 seconds.")
        print()

        # Create bot with no initial market
        bot = PriceActionBot(client)

        # Run background tasks (monitor will detect when market starts)
        try:
            await bot.run()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        finally:
            client.close()
        return

    quick_market = QuickMarket.from_dict(quick_market_data)
    print(f"Initial market: BTC @ ${quick_market.start_price / 1e6:,.2f}")
    print(f"Market expires at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(quick_market.end_time))}")
    print()

    # Note gasless features
    if CLAIM_ONLY_MODE:
        print("🔒 CLAIM ONLY MODE ENABLED - Trading disabled")
        print("✓ Automatic winnings claim enabled for resolved markets")
        print("✓ Monitoring markets for transitions")
    else:
        print("✓ Orders will include USDC permit signatures for gasless trading")
        print("✓ Automatic winnings claim enabled for resolved markets")
        print("✓ Automatic market switching when new BTC markets start")
    print()

    # Run the bot
    bot = PriceActionBot(client)

    try:
        # Initialize with the current market
        await bot.switch_to_new_market(quick_market.market_id, quick_market.start_price)

        # Run the main trading loop (starts background tasks internally)
        await bot.run()
    except KeyboardInterrupt:
        pass
    finally:
        print("\nShutting down...")
        bot.running = False
        await bot.cancel_all_orders()
        client.close()
        print("Bot stopped cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
