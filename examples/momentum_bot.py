"""
Momentum bot — trades BTC quick markets using price trend.

Watches BTC price over a short window. If momentum is positive, buys YES.
If negative, buys NO. Uses the convenience buy() method for simplicity.

Usage:
    TURBINE_PRIVATE_KEY=0x... python examples/momentum_bot.py
"""

import time
from collections import deque
from turbine_client import TurbineClient

# --- Config ---
LOOKBACK = 6           # price samples to track
POLL_SECS = 10         # seconds between samples
THRESHOLD_BPS = 15     # minimum move in basis points to trigger trade
ORDER_PRICE = 0.55     # price per share (55 cents)
ORDER_SIZE = 2.0       # shares per trade

client = TurbineClient.from_env()
print(f"Momentum bot | wallet: {client.address}")

prices: deque[float] = deque(maxlen=LOOKBACK)
current_market_id: str | None = None

while True:
    try:
        # Track market rotations
        qm = client.get_quick_market("BTC")
        if qm.market_id != current_market_id:
            current_market_id = qm.market_id
            prices.clear()
            print(f"\n{'='*50}")
            print(f"New market: strike ${qm.start_price / 1e6:,.2f}")
            print(f"{'='*50}")

        # Sample price
        btc = client.get_quick_market_price("BTC").price
        prices.append(btc)

        if len(prices) < 3:
            print(f"BTC ${btc:,.2f} — collecting samples ({len(prices)}/{LOOKBACK})")
            time.sleep(POLL_SECS)
            continue

        # Calculate momentum (simple: newest vs oldest in window)
        momentum_bps = (prices[-1] - prices[0]) / prices[0] * 10_000
        direction = "↑" if momentum_bps > 0 else "↓"
        print(f"BTC ${btc:,.2f} | momentum: {direction} {abs(momentum_bps):.1f} bps", end="")

        if abs(momentum_bps) >= THRESHOLD_BPS:
            outcome = "yes" if momentum_bps > 0 else "no"
            try:
                result = client.buy(
                    market_id=qm.market_id,
                    outcome=outcome,
                    price=ORDER_PRICE,
                    size=ORDER_SIZE,
                )
                print(f" → bought {outcome.upper()}")
            except Exception as e:
                print(f" → failed: {e}")
        else:
            print(" → hold")

    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"Error: {e}")

    time.sleep(POLL_SECS)

client.close()
print("\nStopped.")
