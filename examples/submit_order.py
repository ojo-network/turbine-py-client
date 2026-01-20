"""
Example: Submitting orders to the orderbook.

This example shows how to:
- Create a fully authenticated client
- Create and submit orders
- Get and manage open orders
- Cancel orders
"""

import os
import time

from dotenv import load_dotenv

from turbine_client import TurbineClient, OrderArgs, Side, Outcome
from turbine_client.exceptions import TurbineApiError

# Load environment variables
load_dotenv()

# Get credentials from environment
private_key = os.environ.get("TURBINE_PRIVATE_KEY")
api_key_id = os.environ.get("TURBINE_API_KEY_ID")
api_private_key = os.environ.get("TURBINE_API_PRIVATE_KEY")

if not all([private_key, api_key_id, api_private_key]):
    print("Error: Set the following environment variables:")
    print("  TURBINE_PRIVATE_KEY - Your wallet private key")
    print("  TURBINE_API_KEY_ID - Your Turbine API key ID")
    print("  TURBINE_API_PRIVATE_KEY - Your Turbine API private key (Ed25519)")
    exit(1)

# Create a fully authenticated client
client = TurbineClient(
    host="https://api.turbinefi.com",
    chain_id=137,  # Polygon mainnet
    private_key=private_key,
    api_key_id=api_key_id,
    api_private_key=api_private_key,
)

print(f"Wallet address: {client.address}")
print(f"Can sign orders: {client.can_sign}")
print(f"Has bearer auth: {client.has_auth}")

# Get markets and pick one
markets = client.get_markets()
if not markets:
    print("No markets available")
    exit(1)

market = markets[0]
print(f"\nTrading on: {market.question}")
print(f"Market ID: {market.id}")

# Create an order
order_args = OrderArgs(
    market_id=market.id,
    side=Side.BUY,
    outcome=Outcome.YES,
    price=100000,  # 10% - very low price, unlikely to fill
    size=1000000,  # 1 share
    expiration=int(time.time()) + 300,  # 5 minutes
)

signed_order = client.create_order(order_args)
print(f"\nCreated order: {signed_order.order_hash}")

# Submit the order
try:
    result = client.post_order(signed_order)
    print(f"Order submitted!")
    print(f"  Order hash: {result.get('orderHash')}")
    print(f"  Status: {result.get('status')}")
except TurbineApiError as e:
    print(f"Failed to submit order: {e}")

# Get our open orders
print("\n=== Open Orders ===")
try:
    orders = client.get_orders(trader=client.address)
    for order in orders:
        price_pct = order.price / 10000
        shares = order.size / 1_000_000
        filled = order.filled_size / 1_000_000
        side = "BUY" if order.side == 0 else "SELL"
        outcome = "YES" if order.outcome == 0 else "NO"
        print(f"  {order.order_hash[:10]}... {side} {shares:.2f} {outcome} @ {price_pct:.2f}%")
        print(f"    Filled: {filled:.2f} / {shares:.2f}")
        print(f"    Status: {order.status}")
except TurbineApiError as e:
    print(f"Failed to get orders: {e}")

# Cancel the order we just created
print(f"\n=== Canceling Order ===")
try:
    cancel_result = client.cancel_order(
        order_hash=signed_order.order_hash,
        market_id=market.id,
        side=Side.BUY,
    )
    print(f"Order canceled: {cancel_result}")
except TurbineApiError as e:
    print(f"Failed to cancel order: {e}")

# Clean up
client.close()
print("\nDone!")
