"""
Integration test for order signing with self-service API credential registration.

This example demonstrates:
1. Requesting API credentials using wallet signature (self-service)
2. Creating and signing orders
3. Submitting orders to the API

Run locally with environment variable:
    INTEGRATION_WALLET_PRIVATE_KEY=... python examples/test_order_integration.py
"""

import os
import sys

from turbine_client import TurbineClient
from turbine_client.types import Outcome, Side

HOST = "https://api.turbinefi.com"
CHAIN_ID = 137  # Polygon mainnet

# Get wallet private key from environment
WALLET_PRIVATE_KEY = os.environ.get("INTEGRATION_WALLET_PRIVATE_KEY")

if not WALLET_PRIVATE_KEY:
    print("ERROR: Missing required environment variable:")
    print("  INTEGRATION_WALLET_PRIVATE_KEY")
    sys.exit(1)

print("=" * 60)
print("STEP 1: Request API credentials (self-service)")
print("=" * 60)

credentials = TurbineClient.request_api_credentials(
    host=HOST,
    private_key=WALLET_PRIVATE_KEY,
)
print("API credentials obtained!")
print(f"  API Key ID: {credentials['api_key_id']}")
print(f"  API Private Key: {credentials['api_private_key'][:32]}...")
API_KEY_ID = credentials["api_key_id"]
API_PRIVATE_KEY = credentials["api_private_key"]

print()

print("=" * 60)
print("STEP 2: Create authenticated client")
print("=" * 60)

client = TurbineClient(
    host=HOST,
    chain_id=CHAIN_ID,
    private_key=WALLET_PRIVATE_KEY,
    api_key_id=API_KEY_ID,
    api_private_key=API_PRIVATE_KEY,
)

print(f"Wallet address: {client.address}")
print()

print("=" * 60)
print("STEP 3: Get market and create order")
print("=" * 60)

# Get a market to test with
markets = client.get_markets()
if not markets:
    print("No markets available")
    client.close()
    sys.exit(1)

market = markets[0]
print(f"Testing with market: {market.question}")
print(f"  Market ID: {market.id}")
print(f"  Settlement Address: {market.settlement_address}")
print()

# Create an order
print("Creating limit buy order...")
order = client.create_limit_buy(
    market_id=market.id,
    outcome=Outcome.YES,
    price=10000,  # 1% (very low price, won't fill)
    size=100000,  # 0.1 shares
    settlement_address=market.settlement_address,
)

print(f"Order created!")
print(f"  Side: {'BUY' if order.side == 0 else 'SELL'}")
print(f"  Outcome: {'YES' if order.outcome == 0 else 'NO'}")
print(f"  Price: {order.price / 10000:.2f}%")
print(f"  Size: {order.size / 1_000_000:.6f} shares")
print(f"  Order Hash: {order.order_hash}")
print()

print("=" * 60)
print("STEP 4: Submit order to API")
print("=" * 60)

print("Submitting order...")
try:
    result = client.post_order(order)
    print(f"Order submitted successfully!")
    print(f"  Status: {result.get('status')}")
    print(f"  Order Hash: {result.get('orderHash')}")
    print(f"  Matches: {result.get('matches', 0)}")
    order_hash = result.get("orderHash", order.order_hash)
except Exception as e:
    print(f"Order submission failed: {e}")
    client.close()
    sys.exit(1)

print()

print("=" * 60)
print("STEP 5: Cancel order")
print("=" * 60)

print(f"Cancelling order {order_hash[:20]}...")
try:
    cancel_result = client.cancel_order(
        order_hash=order_hash,
        market_id=market.id,
        side=Side.BUY,
    )
    print(f"Order cancelled: {cancel_result}")
except Exception as e:
    print(f"Cancel failed (may already be filled): {e}")

print()

client.close()
print("=" * 60)
print("Integration test complete!")
print("=" * 60)
