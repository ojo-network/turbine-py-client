"""
Example: WebSocket streaming for real-time data.

This example shows how to:
- Connect to the WebSocket server
- Subscribe to orderbook updates
- Subscribe to trade updates
- Subscribe to quick market updates
"""

import asyncio

from turbine_client import TurbineClient, TurbineWSClient
from turbine_client.exceptions import WebSocketError


async def main():
    # First, get a market ID using the REST API
    client = TurbineClient(
        host="https://api.turbinefi.com",
        chain_id=137,
    )

    markets = client.get_markets()
    client.close()

    if not markets:
        print("No markets available")
        return

    market = markets[0]
    print(f"Streaming data for: {market.question}")
    print(f"Market ID: {market.id}")
    print()

    # Create WebSocket client
    ws = TurbineWSClient(host="https://api.turbinefi.com")

    try:
        async with ws.connect() as stream:
            # Subscribe to orderbook updates
            await stream.subscribe_orderbook(market.id)
            print("Subscribed to orderbook updates")

            # Subscribe to trade updates
            await stream.subscribe_trades(market.id)
            print("Subscribed to trade updates")

            # Subscribe to quick markets (BTC)
            await stream.subscribe_quick_markets("BTC")
            print("Subscribed to BTC quick market updates")
            print()

            print("Waiting for messages (Ctrl+C to stop)...")
            print("-" * 50)

            # Process incoming messages
            async for message in stream:
                if message.type == "orderbook":
                    if hasattr(message, "orderbook") and message.orderbook:
                        ob = message.orderbook
                        best_bid = ob.bids[0].price / 10000 if ob.bids else 0
                        best_ask = ob.asks[0].price / 10000 if ob.asks else 0
                        spread = best_ask - best_bid
                        print(f"[ORDERBOOK] Bid: {best_bid:.2f}% | Ask: {best_ask:.2f}% | Spread: {spread:.2f}%")

                elif message.type == "trade":
                    if hasattr(message, "trade") and message.trade:
                        trade = message.trade
                        price_pct = trade.price / 10000
                        shares = trade.size / 1_000_000
                        side = "BUY" if trade.side == 0 else "SELL"
                        outcome = "YES" if trade.outcome == 0 else "NO"
                        print(f"[TRADE] {side} {shares:.2f} {outcome} @ {price_pct:.2f}%")

                elif message.type == "quick_market":
                    if hasattr(message, "quick_market") and message.quick_market:
                        qm = message.quick_market
                        price = qm.start_price / 1e8
                        status = "RESOLVED" if qm.resolved else "ACTIVE"
                        print(f"[QUICK MARKET] {qm.asset} Strike: ${price:,.2f} | {status}")

                else:
                    # Other message types
                    print(f"[{message.type.upper()}] {message.data}")

    except WebSocketError as e:
        print(f"WebSocket error: {e}")
    except KeyboardInterrupt:
        print("\nDisconnected")


if __name__ == "__main__":
    asyncio.run(main())
