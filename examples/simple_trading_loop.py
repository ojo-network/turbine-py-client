"""
Simple trading loop — buy YES when BTC is above strike, NO when below.

Requires a .env file with TURBINE_PRIVATE_KEY (API keys auto-generated).

Usage:
    cp .env.example .env          # fill in TURBINE_PRIVATE_KEY
    pip install turbine-py-client
    python examples/simple_trading_loop.py
"""

import time
from turbine_client import TurbineClient

# Load credentials from .env (auto-registers API keys if missing)
client = TurbineClient.from_env()
print(f"Wallet: {client.address}")

while True:
    # Get current market and BTC price
    qm = client.get_quick_market("BTC")
    price = client.get_quick_market_price("BTC")

    strike = qm.start_price / 1e6
    btc = price.price
    diff_pct = (btc - strike) / strike * 100

    print(f"\nBTC ${btc:,.2f} vs strike ${strike:,.2f} ({diff_pct:+.2f}%)")

    # Only trade if price moved meaningfully (>0.1% from strike)
    if abs(diff_pct) > 0.1:
        outcome = "yes" if btc > strike else "no"
        try:
            result = client.buy(
                market_id=qm.market_id,
                outcome=outcome,
                price=0.60,    # 60 cents per share
                size=1.0,      # 1 share ($0.60 USDC risk)
            )
            print(f"  → Bought {outcome.upper()} | order: {result['orderHash'][:16]}...")
        except Exception as e:
            print(f"  → Order failed: {e}")
    else:
        print("  → Too close to strike, holding")

    time.sleep(30)
