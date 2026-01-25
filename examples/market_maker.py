"""
Example: Simple market making bot.

This example shows how to:
- Subscribe to real-time orderbook updates
- Maintain quotes around the mid price
- Manage order lifecycle

WARNING: This is a simplified example for educational purposes.
Real market making requires careful risk management.
"""

import asyncio
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

from turbine_client import TurbineClient, TurbineWSClient, OrderArgs, Side, Outcome
from turbine_client.exceptions import TurbineApiError, WebSocketError

# Load environment variables
load_dotenv()


def get_or_create_api_credentials(env_path: Path = None) -> tuple[str, str]:
    """Get existing API credentials or register new ones and save to .env."""
    if env_path is None:
        env_path = Path(__file__).parent / ".env"

    api_key_id = os.environ.get("TURBINE_API_KEY_ID")
    api_private_key = os.environ.get("TURBINE_API_PRIVATE_KEY")

    if api_key_id and api_private_key:
        print("Using existing API credentials")
        return api_key_id, api_private_key

    # Need to register new credentials
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

    # Auto-save to .env file
    _save_credentials_to_env(env_path, api_key_id, api_private_key)

    # Update current environment so we can use them immediately
    os.environ["TURBINE_API_KEY_ID"] = api_key_id
    os.environ["TURBINE_API_PRIVATE_KEY"] = api_private_key

    print(f"API credentials saved to {env_path}")
    return api_key_id, api_private_key


def _save_credentials_to_env(env_path: Path, api_key_id: str, api_private_key: str):
    """Save API credentials to .env file."""
    env_path = Path(env_path)

    if env_path.exists():
        content = env_path.read_text()
        # Update existing values or append if not present
        if "TURBINE_API_KEY_ID=" in content:
            content = re.sub(
                r'^TURBINE_API_KEY_ID=.*$',
                f'TURBINE_API_KEY_ID={api_key_id}',
                content,
                flags=re.MULTILINE
            )
        else:
            content += f"\nTURBINE_API_KEY_ID={api_key_id}"

        if "TURBINE_API_PRIVATE_KEY=" in content:
            content = re.sub(
                r'^TURBINE_API_PRIVATE_KEY=.*$',
                f'TURBINE_API_PRIVATE_KEY={api_private_key}',
                content,
                flags=re.MULTILINE
            )
        else:
            content += f"\nTURBINE_API_PRIVATE_KEY={api_private_key}"

        env_path.write_text(content)
    else:
        # Create new .env file with all credentials
        content = f"""# Turbine Trading Bot Configuration
TURBINE_PRIVATE_KEY={os.environ.get('TURBINE_PRIVATE_KEY', '')}
TURBINE_API_KEY_ID={api_key_id}
TURBINE_API_PRIVATE_KEY={api_private_key}
"""
        env_path.write_text(content)

# Configuration
SPREAD_BPS = 200  # 2% spread (100 bps = 1%)
ORDER_SIZE = 1000000  # 1 share
QUOTE_REFRESH_SECONDS = 30
DEFAULT_MID = 500000  # 50% if no orderbook


class SimpleMarketMaker:
    """A simple market maker that quotes around the mid price."""

    def __init__(
        self,
        client: TurbineClient,
        market_id: str,
        spread_bps: int = SPREAD_BPS,
        order_size: int = ORDER_SIZE,
    ):
        self.client = client
        self.market_id = market_id
        self.spread_bps = spread_bps
        self.order_size = order_size

        self.current_mid = DEFAULT_MID
        self.active_orders: dict[str, str] = {}  # hash -> side

    def calculate_quotes(self) -> tuple[int, int]:
        """Calculate bid and ask prices from mid."""
        half_spread = (self.current_mid * self.spread_bps) // 20000
        bid = max(1, self.current_mid - half_spread)
        ask = min(999999, self.current_mid + half_spread)
        return bid, ask

    async def cancel_all_orders(self) -> None:
        """Cancel all active orders."""
        for order_hash in list(self.active_orders.keys()):
            try:
                self.client.cancel_order(order_hash)
                print(f"Canceled order: {order_hash[:10]}...")
                del self.active_orders[order_hash]
            except TurbineApiError as e:
                print(f"Failed to cancel {order_hash[:10]}...: {e}")

    async def place_quotes(self) -> None:
        """Place new bid and ask orders."""
        bid_price, ask_price = self.calculate_quotes()

        bid_pct = bid_price / 10000
        ask_pct = ask_price / 10000
        print(f"Placing quotes: Bid {bid_pct:.2f}% / Ask {ask_pct:.2f}%")

        # Place bid
        try:
            bid_order = self.client.create_limit_buy(
                market_id=self.market_id,
                outcome=Outcome.YES,
                price=bid_price,
                size=self.order_size,
                expiration=int(time.time()) + QUOTE_REFRESH_SECONDS + 60,
            )
            result = self.client.post_order(bid_order)
            self.active_orders[bid_order.order_hash] = "BUY"
            print(f"  Bid placed: {bid_order.order_hash[:10]}...")
        except TurbineApiError as e:
            print(f"  Failed to place bid: {e}")

        # Place ask
        try:
            ask_order = self.client.create_limit_sell(
                market_id=self.market_id,
                outcome=Outcome.YES,
                price=ask_price,
                size=self.order_size,
                expiration=int(time.time()) + QUOTE_REFRESH_SECONDS + 60,
            )
            result = self.client.post_order(ask_order)
            self.active_orders[ask_order.order_hash] = "SELL"
            print(f"  Ask placed: {ask_order.order_hash[:10]}...")
        except TurbineApiError as e:
            print(f"  Failed to place ask: {e}")

    async def update_quotes(self) -> None:
        """Cancel existing orders and place new ones."""
        await self.cancel_all_orders()
        await self.place_quotes()

    def update_mid_from_orderbook(self, orderbook) -> None:
        """Update mid price from orderbook snapshot."""
        if orderbook.bids and orderbook.asks:
            best_bid = orderbook.bids[0].price
            best_ask = orderbook.asks[0].price
            self.current_mid = (best_bid + best_ask) // 2
        elif orderbook.bids:
            self.current_mid = orderbook.bids[0].price
        elif orderbook.asks:
            self.current_mid = orderbook.asks[0].price
        else:
            self.current_mid = DEFAULT_MID

    async def run(self, ws_host: str) -> None:
        """Run the market maker."""
        ws = TurbineWSClient(host=ws_host)

        print(f"Starting market maker for {self.market_id[:10]}...")
        print(f"Spread: {self.spread_bps / 100:.1f}%")
        print(f"Order size: {self.order_size / 1_000_000:.2f} shares")
        print()

        try:
            async with ws.connect() as stream:
                # Subscribe to orderbook
                await stream.subscribe_orderbook(self.market_id)
                print("Subscribed to orderbook updates")

                # Initial quote placement
                await self.place_quotes()

                last_refresh = time.time()

                async for message in stream:
                    if message.type == "orderbook":
                        # Update mid price
                        if hasattr(message, "orderbook") and message.orderbook:
                            self.update_mid_from_orderbook(message.orderbook)
                            mid_pct = self.current_mid / 10000
                            print(f"Orderbook update - Mid: {mid_pct:.2f}%")

                    elif message.type == "trade":
                        if hasattr(message, "trade") and message.trade:
                            trade = message.trade
                            price_pct = trade.price / 10000
                            shares = trade.size / 1_000_000
                            print(f"Trade: {shares:.2f} @ {price_pct:.2f}%")

                    # Refresh quotes periodically
                    if time.time() - last_refresh > QUOTE_REFRESH_SECONDS:
                        await self.update_quotes()
                        last_refresh = time.time()

        except WebSocketError as e:
            print(f"WebSocket error: {e}")
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            await self.cancel_all_orders()


async def main():
    # Get credentials
    private_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if not private_key:
        print("Error: Set TURBINE_PRIVATE_KEY in your .env file")
        return

    # Get or create API credentials (auto-saves to .env)
    try:
        api_key_id, api_private_key = get_or_create_api_credentials()
    except TurbineApiError as e:
        print(f"Error getting API credentials: {e}")
        return

    # Create client
    host = "https://api.turbinefi.com"
    client = TurbineClient(
        host=host,
        chain_id=137,
        private_key=private_key,
        api_key_id=api_key_id,
        api_private_key=api_private_key,
    )

    print(f"Market Maker Address: {client.address}")

    # Get a market
    markets = client.get_markets()
    if not markets:
        print("No markets available")
        return

    market = markets[0]
    print(f"Selected market: {market.question}")

    # Run market maker
    mm = SimpleMarketMaker(client, market.id)
    await mm.run(host)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
