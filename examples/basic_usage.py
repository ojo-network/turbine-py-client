"""
Basic usage example for Turbine Python client.

This example shows how to:
- Create a client for read-only access
- Fetch market data
- Get orderbook
- Get recent trades
"""

from turbine_client import TurbineClient

# Create a public client (no auth required for read-only operations)
client = TurbineClient(
    host="https://api.turbinefi.com",
    chain_id=137,  # Polygon mainnet
)

# Check API health
health = client.get_health()
print(f"API Status: {health}")

# Get all markets
print("\n=== Markets ===")
markets = client.get_markets()
for market in markets[:5]:  # Show first 5
    print(f"- {market.question}")
    print(f"  ID: {market.id}")
    print(f"  Category: {market.category}")
    print(f"  Resolved: {market.resolved}")
    print()

# Get orderbook for a specific market (if any markets exist)
if markets:
    market_id = markets[0].id
    print(f"\n=== Orderbook for {markets[0].question} ===")

    orderbook = client.get_orderbook(market_id)
    print(f"Last update: {orderbook.last_update}")

    print("\nBids (buyers):")
    for bid in orderbook.bids[:5]:
        price_pct = bid.price / 10000  # Convert to percentage
        shares = bid.size / 1_000_000
        print(f"  {price_pct:.2f}% - {shares:.2f} shares")

    print("\nAsks (sellers):")
    for ask in orderbook.asks[:5]:
        price_pct = ask.price / 10000
        shares = ask.size / 1_000_000
        print(f"  {price_pct:.2f}% - {shares:.2f} shares")

    # Get recent trades
    print(f"\n=== Recent Trades ===")
    trades = client.get_trades(market_id, limit=5)
    for trade in trades:
        price_pct = trade.price / 10000
        shares = trade.size / 1_000_000
        side = "BUY" if trade.side == 0 else "SELL"
        outcome = "YES" if trade.outcome == 0 else "NO"
        print(f"  {side} {shares:.2f} {outcome} @ {price_pct:.2f}%")

# Clean up
client.close()
print("\nDone!")
