"""
Example: Monitoring positions.

This example shows how to:
- Get all positions for a user
- Calculate P&L
- Display position summary
"""

import os

from dotenv import load_dotenv

from turbine_client import TurbineClient
from turbine_client.utils import format_price, format_usdc

# Load environment variables
load_dotenv()

# Get credentials
api_key_id = os.environ.get("TURBINE_API_KEY_ID")
api_private_key = os.environ.get("TURBINE_API_PRIVATE_KEY")
wallet_address = os.environ.get("TURBINE_WALLET_ADDRESS")

if not all([api_key_id, api_private_key, wallet_address]):
    print("Error: Set environment variables:")
    print("  TURBINE_API_KEY_ID")
    print("  TURBINE_API_PRIVATE_KEY")
    print("  TURBINE_WALLET_ADDRESS - Address to monitor")
    exit(1)

# Create client (no private key needed for read-only)
client = TurbineClient(
    host="https://api.turbinefi.com",
    chain_id=137,
    api_key_id=api_key_id,
    api_private_key=api_private_key,
)

print(f"Monitoring positions for: {wallet_address}")
print("=" * 60)

# Get all positions
positions = client.get_user_positions(wallet_address)

if not positions:
    print("No positions found")
    client.close()
    exit(0)

# Display each position
total_invested = 0
total_current_value = 0

for pos in positions:
    # Get market details
    market = client.get_market(pos.market_id)

    print(f"\n{market.question}")
    print("-" * 50)

    # Calculate current value
    stats = client.get_stats(pos.market_id)
    yes_price = stats.last_price
    no_price = 1_000_000 - yes_price

    yes_value = (pos.yes_shares * yes_price) // 1_000_000
    no_value = (pos.no_shares * no_price) // 1_000_000
    current_value = yes_value + no_value

    # Calculate P&L
    pnl = current_value - pos.invested
    pnl_pct = (pnl / pos.invested * 100) if pos.invested > 0 else 0

    print(f"  YES shares: {pos.yes_shares / 1_000_000:.2f}")
    print(f"  NO shares:  {pos.no_shares / 1_000_000:.2f}")
    print(f"  Invested:   {format_usdc(pos.invested)}")
    print(f"  Current:    {format_usdc(current_value)}")
    print(f"  P&L:        {format_usdc(pnl)} ({pnl_pct:+.1f}%)")
    print(f"  Last price: {format_price(stats.last_price)}")

    if market.resolved:
        outcome = "YES" if market.winning_outcome == 0 else "NO"
        print(f"  RESOLVED:   {outcome} won!")

    total_invested += pos.invested
    total_current_value += current_value

# Summary
print("\n" + "=" * 60)
print("PORTFOLIO SUMMARY")
print("=" * 60)
print(f"Total invested:  {format_usdc(total_invested)}")
print(f"Current value:   {format_usdc(total_current_value)}")
total_pnl = total_current_value - total_invested
total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
print(f"Total P&L:       {format_usdc(total_pnl)} ({total_pnl_pct:+.1f}%)")
print(f"Positions:       {len(positions)}")

# Get user activity
activity = client.get_user_activity(wallet_address)
print(f"\nTotal trades:    {activity.total_trades}")
print(f"Total volume:    {format_usdc(activity.total_volume)}")
print(f"Markets traded:  {activity.markets_traded}")

client.close()
