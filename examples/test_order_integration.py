"""
Integration test for order signing with dynamic settlement address.

This example demonstrates that the client automatically fetches the
market's settlement address when creating orders.

Run locally with environment variables:
    INTEGRATION_WALLET_PRIVATE_KEY=... \
    INTEGRATION_API_KEY_ID=... \
    INTEGRATION_API_PRIVATE_KEY=... \
    python examples/test_order_integration.py
"""

import os
import sys

from turbine_client import TurbineClient
from turbine_client.types import Outcome

# Get credentials from environment variables
WALLET_PRIVATE_KEY = os.environ.get("INTEGRATION_WALLET_PRIVATE_KEY")
API_KEY_ID = os.environ.get("INTEGRATION_API_KEY_ID")
API_PRIVATE_KEY = os.environ.get("INTEGRATION_API_PRIVATE_KEY")

if not all([WALLET_PRIVATE_KEY, API_KEY_ID, API_PRIVATE_KEY]):
    print("ERROR: Missing required environment variables:")
    print("  INTEGRATION_WALLET_PRIVATE_KEY")
    print("  INTEGRATION_API_KEY_ID")
    print("  INTEGRATION_API_PRIVATE_KEY")
    sys.exit(1)

# Create authenticated client
client = TurbineClient(
    host="https://api.turbinefi.com",
    chain_id=137,  # Polygon mainnet
    private_key=WALLET_PRIVATE_KEY,
    api_key_id=API_KEY_ID,
    api_private_key=API_PRIVATE_KEY,
)

print(f"Wallet address: {client.address}")
print()

# Get a market to test with
markets = client.get_markets()
if not markets:
    print("No markets available")
    client.close()
    exit(1)

market = markets[0]
print(f"=== Testing with market: {market.question} ===")
print(f"Market ID: {market.id}")
print(f"Settlement Address: {market.settlement_address}")
print()

# Create an order - pass the settlement address from the market
print("Creating order with market's settlement address...")
order = client.create_limit_buy(
    market_id=market.id,
    outcome=Outcome.YES,
    price=10000,  # 1% (very low price, won't fill)
    size=100000,  # 0.1 shares
    settlement_address=market.settlement_address,
)

print(f"Order created successfully!")
print(f"  Market ID: {order.market_id}")
print(f"  Side: {'BUY' if order.side == 0 else 'SELL'}")
print(f"  Outcome: {'YES' if order.outcome == 0 else 'NO'}")
print(f"  Price: {order.price / 10000:.2f}%")
print(f"  Size: {order.size / 1_000_000:.6f} shares")
print(f"  Nonce: {order.nonce}")
print(f"  Order Hash: {order.order_hash}")
print(f"  Signature: {order.signature[:20]}...")
print()

# Debug: print what we're sending
import json
print("Payload being sent:")
print(json.dumps(order.to_dict(), indent=2))
print()

# Try to post the order
print("Submitting order to API...")
try:
    result = client.post_order(order)
    print(f"Order submitted successfully!")
    print(f"  Result: {result}")
except Exception as e:
    print(f"Order submission failed: {e}")

client.close()
print("\nDone!")
