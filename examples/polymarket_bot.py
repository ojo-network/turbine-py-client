"""
Turbine Polymarket Trading Bot

Trades on Polymarket prediction markets through Turbine's API proxy.
Browses markets, identifies opportunities (high volume, prices near extremes),
places orders, and tracks positions.

All traffic goes through Turbine — never directly to Polymarket.

Usage:
    # Set credentials in .env:
    #   TURBINE_HOST=https://api.turbine.markets
    #   POLYMARKET_KEY=...
    #   POLYMARKET_SECRET=...
    #   POLYMARKET_PASSPHRASE=...
    #   POLYMARKET_PRIVATE_KEY=0x...   (for client-side order signing)
    #   CHAIN_ID=137

    python examples/polymarket_bot.py
"""

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from turbine_client.polymarket import PolymarketClient
from turbine_client.exceptions import TurbineApiError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("polymarket_bot")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent / ".env")

TURBINE_HOST = os.environ.get("TURBINE_HOST", "http://localhost:8080")
POLYMARKET_KEY = os.environ.get("POLYMARKET_KEY", "")
POLYMARKET_SECRET = os.environ.get("POLYMARKET_SECRET", "")
POLYMARKET_PASSPHRASE = os.environ.get("POLYMARKET_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY = os.environ.get("POLYMARKET_PRIVATE_KEY", "")
CHAIN_ID = int(os.environ.get("CHAIN_ID", "137"))

# Trading parameters
ORDER_SIZE = os.environ.get("ORDER_SIZE", "10")  # shares per order
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "30"))  # seconds
MIN_PRICE = 0.05   # ignore markets with best price below 5%
MAX_PRICE = 0.95   # ignore markets with best price above 95%


class PolymarketBot:
    """Simple Polymarket trading bot.

    Strategy:
    - Scan markets for high-volume opportunities
    - Look for mispricings near extremes (< 10% or > 90%)
    - Place limit orders with a small edge
    - Track and log positions periodically
    """

    def __init__(self, client: PolymarketClient, address: str) -> None:
        self.client = client
        self.address = address
        self.running = True
        self.tracked_orders: list[str] = []

    # ------------------------------------------------------------------
    # Market scanning
    # ------------------------------------------------------------------

    async def scan_markets(self) -> list[dict]:
        """Fetch markets and return those with interesting prices."""
        try:
            data = self.client.get_markets()
        except TurbineApiError as e:
            log.error("Failed to fetch markets: %s", e)
            return []

        markets = data if isinstance(data, list) else data.get("markets", [])
        interesting: list[dict] = []

        for market in markets:
            tokens = market.get("tokens", [])
            for token in tokens:
                price = float(token.get("price", 0.5))
                if price <= MIN_PRICE or price >= MAX_PRICE:
                    interesting.append(
                        {
                            "market": market,
                            "token": token,
                            "price": price,
                        }
                    )

        if interesting:
            log.info("Found %d interesting tokens across markets", len(interesting))
        else:
            log.info("No tokens near price extremes found this cycle")

        return interesting

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    async def place_orders(self, opportunities: list[dict]) -> None:
        """Place limit orders on the most interesting opportunities."""
        for opp in opportunities[:3]:  # cap at 3 orders per cycle
            token = opp["token"]
            token_id = token.get("token_id", token.get("id", ""))
            price = opp["price"]
            question = opp["market"].get("question", "?")

            # Strategy: buy low, sell high
            if price <= MIN_PRICE + 0.05:
                side = "BUY"
                limit_price = f"{price + 0.01:.2f}"
            elif price >= MAX_PRICE - 0.05:
                side = "SELL"
                limit_price = f"{price - 0.01:.2f}"
            else:
                continue

            log.info(
                "Placing %s order: %s @ %s (market: %s)",
                side,
                ORDER_SIZE,
                limit_price,
                question[:60],
            )

            try:
                result = self.client.create_order(
                    token_id=token_id,
                    side=side,
                    price=limit_price,
                    size=ORDER_SIZE,
                    order_type="GTC",
                )
                order_id = result.get("orderId", result.get("id", "unknown"))
                log.info("Order placed: %s", order_id)
                self.tracked_orders.append(order_id)
            except TurbineApiError as e:
                log.error("Order failed: %s", e)

    # ------------------------------------------------------------------
    # Position tracking
    # ------------------------------------------------------------------

    async def log_positions(self) -> None:
        """Log current positions."""
        try:
            positions = self.client.get_positions(self.address)
            if not positions:
                log.info("No open positions")
                return
            pos_list = positions if isinstance(positions, list) else [positions]
            for pos in pos_list:
                log.info("Position: %s", pos)
        except TurbineApiError as e:
            log.warning("Could not fetch positions: %s", e)

    async def log_open_orders(self) -> None:
        """Log open orders."""
        try:
            orders = self.client.get_open_orders()
            order_list = orders if isinstance(orders, list) else orders.get("orders", [])
            log.info("Open orders: %d", len(order_list))
        except TurbineApiError as e:
            log.warning("Could not fetch open orders: %s", e)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Main trading loop."""
        log.info("Starting Polymarket bot — polling every %ds", POLL_INTERVAL)

        while self.running:
            try:
                opportunities = await self.scan_markets()
                if opportunities:
                    await self.place_orders(opportunities)

                await self.log_positions()
                await self.log_open_orders()

            except Exception:
                log.exception("Unexpected error in trading loop")

            # Wait for next cycle
            for _ in range(POLL_INTERVAL):
                if not self.running:
                    break
                await asyncio.sleep(1)

    def stop(self) -> None:
        """Signal the bot to stop."""
        log.info("Shutdown requested")
        self.running = False


async def main() -> None:
    # Validate config
    if not POLYMARKET_KEY or not POLYMARKET_SECRET or not POLYMARKET_PASSPHRASE:
        log.error(
            "Missing Polymarket credentials. Set POLYMARKET_KEY, "
            "POLYMARKET_SECRET, POLYMARKET_PASSPHRASE in .env"
        )
        sys.exit(1)

    # Derive address from private key (if available)
    address = os.environ.get("POLYMARKET_ADDRESS", "")
    if not address and POLYMARKET_PRIVATE_KEY:
        try:
            from eth_account import Account

            address = Account.from_key(POLYMARKET_PRIVATE_KEY).address
        except ImportError:
            log.warning("eth_account not installed; set POLYMARKET_ADDRESS in .env")
        except Exception as e:
            log.warning("Could not derive address from private key: %s", e)

    client = PolymarketClient(
        host=TURBINE_HOST,
        polymarket_key=POLYMARKET_KEY,
        polymarket_secret=POLYMARKET_SECRET,
        polymarket_passphrase=POLYMARKET_PASSPHRASE,
        private_key=POLYMARKET_PRIVATE_KEY or None,
        chain_id=CHAIN_ID,
    )

    bot = PolymarketBot(client, address)

    # Graceful shutdown on SIGINT / SIGTERM
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, bot.stop)

    log.info("=" * 50)
    log.info("TURBINE POLYMARKET BOT")
    log.info("=" * 50)
    log.info("Host:    %s", TURBINE_HOST)
    log.info("Chain:   %s", CHAIN_ID)
    log.info("Address: %s", address or "(unknown)")
    log.info("=" * 50)

    try:
        await bot.run()
    finally:
        client.close()
        log.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
