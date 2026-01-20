"""
Example: Creating and signing orders.

This example shows how to:
- Create a client with signing capability
- Create signed orders for submission
- Use helper functions for price/size conversion
"""

import os
import time

from dotenv import load_dotenv

from turbine_client import TurbineClient, OrderArgs, Side, Outcome
from turbine_client.order_builder.helpers import (
    decimal_to_price,
    shares_to_size,
    calculate_cost,
    calculate_profit,
)

# Load environment variables
load_dotenv()

# Get private key from environment
private_key = os.environ.get("TURBINE_PRIVATE_KEY")
if not private_key:
    print("Error: Set TURBINE_PRIVATE_KEY environment variable")
    print("Example: export TURBINE_PRIVATE_KEY=0x...")
    exit(1)

# Create a client with signing capability
client = TurbineClient(
    host="https://api.turbinefi.com",
    chain_id=137,  # Polygon mainnet
    private_key=private_key,
)

print(f"Wallet address: {client.address}")
print(f"Can sign orders: {client.can_sign}")

# Example market ID (replace with real one)
market_id = "0x" + "12" * 32  # Example market ID

# Method 1: Using OrderArgs directly
print("\n=== Method 1: Using OrderArgs ===")

order_args = OrderArgs(
    market_id=market_id,
    side=Side.BUY,
    outcome=Outcome.YES,
    price=500000,  # 50% (scaled by 1e6)
    size=1000000,  # 1 share (6 decimals)
    expiration=int(time.time()) + 3600,  # 1 hour from now
)

signed_order = client.create_order(order_args)
print(f"Order hash: {signed_order.order_hash}")
print(f"Signature: {signed_order.signature[:20]}...")

# Method 2: Using convenience methods
print("\n=== Method 2: Using convenience methods ===")

buy_order = client.create_limit_buy(
    market_id=market_id,
    outcome=Outcome.YES,
    price=decimal_to_price(0.45),  # 45%
    size=shares_to_size(2.5),  # 2.5 shares
    expiration=int(time.time()) + 7200,  # 2 hours
)

print(f"Buy order created:")
print(f"  Price: {buy_order.price / 10000:.2f}%")
print(f"  Size: {buy_order.size / 1_000_000:.2f} shares")
print(f"  Expiration: {buy_order.expiration}")

# Calculate costs
cost = calculate_cost(buy_order.price, buy_order.size)
profit = calculate_profit(buy_order.price, buy_order.size)
print(f"  Cost: ${cost / 1_000_000:.2f} USDC")
print(f"  Potential profit: ${profit / 1_000_000:.2f} USDC")

# Create a sell order
sell_order = client.create_limit_sell(
    market_id=market_id,
    outcome=Outcome.YES,
    price=decimal_to_price(0.55),  # 55%
    size=shares_to_size(2.5),  # 2.5 shares
)

print(f"\nSell order created:")
print(f"  Price: {sell_order.price / 10000:.2f}%")
print(f"  Size: {sell_order.size / 1_000_000:.2f} shares")

# Show the order dict (what gets sent to API)
print("\n=== Order API Format ===")
import json
print(json.dumps(signed_order.to_dict(), indent=2))

# Clean up
client.close()
print("\nDone!")
