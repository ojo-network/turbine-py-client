"""
Fetch market data — no credentials needed.

Shows how to read orderbooks, prices, and trades using only public endpoints.
"""

from turbine_client import TurbineClient

client = TurbineClient()  # defaults to Polygon mainnet

# --- Current BTC quick market ---
qm = client.get_quick_market("BTC")
print(f"Market: {qm.asset} | Strike: ${qm.start_price / 1e6:,.2f}")
print(f"  Market ID: {qm.market_id}")
print(f"  Expires:   epoch {qm.end_time}")

# --- Live BTC price (Pyth oracle) ---
price = client.get_quick_market_price("BTC")
print(f"\nBTC price: ${price.price:,.2f}")

# --- Orderbook snapshot ---
book = client.get_orderbook(qm.market_id)
print(f"\nOrderbook ({len(book.bids)} bids, {len(book.asks)} asks)")
for level in book.bids[:3]:
    print(f"  BID  {level.price / 1e4:5.1f}%  ×  {level.size / 1e6:.2f} shares")
for level in book.asks[:3]:
    print(f"  ASK  {level.price / 1e4:5.1f}%  ×  {level.size / 1e6:.2f} shares")

# --- Recent trades ---
trades = client.get_trades(qm.market_id, limit=5)
print(f"\nLast {len(trades)} trades:")
for t in trades:
    outcome = "YES" if t.outcome == 0 else "NO"
    print(f"  {outcome}  {t.price / 1e4:.1f}%  ×  {t.size / 1e6:.2f} shares")

client.close()
