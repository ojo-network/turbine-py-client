---
name: market-maker
description: Create a market maker bot for Turbine's BTC 15-minute prediction markets. Use when building trading bots for Turbine.
disable-model-invocation: true
argument-hint: "[algorithm-type]"
---

# Turbine Market Maker Bot Generator

You are helping a programmer create a market maker bot for Turbine's Bitcoin 15-minute prediction markets.

## Step 1: Environment Setup Check

First, check if the user has the required setup:

1. Check if `turbine_client` is importable by looking at the project structure
2. Check if `.env` file exists with the required credentials
3. If `.env` doesn't exist, guide them through creating it

## Step 2: Private Key Setup

Ask the user if they already have an Ethereum wallet private key configured. If not, guide them:

```
To trade on Turbine, you need an Ethereum wallet private key.

IMPORTANT SECURITY NOTES:
- NEVER share your private key with anyone
- Use a dedicated trading wallet with limited funds
- Store your private key securely

To get your private key:
1. If using MetaMask: Settings > Security & Privacy > Export Private Key
2. If using a new wallet: Create one at https://metamask.io

Add to your .env file:
TURBINE_PRIVATE_KEY=0x...your_private_key_here...
```

## Step 3: API Key Auto-Registration

The bot should automatically register for API credentials on first run. Show the user this pattern:

```python
import os
from turbine_client import TurbineClient

def get_or_create_api_credentials():
    """Get existing credentials or register new ones."""
    api_key_id = os.environ.get("TURBINE_API_KEY_ID")
    api_private_key = os.environ.get("TURBINE_API_PRIVATE_KEY")

    if api_key_id and api_private_key:
        print("Using existing API credentials")
        return api_key_id, api_private_key

    # Register new credentials
    private_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if not private_key:
        raise ValueError("TURBINE_PRIVATE_KEY not set in environment")

    print("Registering new API credentials...")
    credentials = TurbineClient.request_api_credentials(
        host="https://api.turbinefi.com",
        private_key=private_key,
    )

    api_key_id = credentials["api_key_id"]
    api_private_key = credentials["api_private_key"]

    print(f"API Key ID: {api_key_id}")
    print(f"API Private Key: {api_private_key}")
    print("\nSAVE THESE TO YOUR .env FILE:")
    print(f"TURBINE_API_KEY_ID={api_key_id}")
    print(f"TURBINE_API_PRIVATE_KEY={api_private_key}")

    return api_key_id, api_private_key
```

## Step 4: Algorithm Selection

Present the user with these trading algorithm options for prediction markets:

**Option 1: Simple Spread Market Maker (Recommended for beginners)**
- Places bid and ask orders around the mid-price with a fixed spread
- Best for: Learning the basics, stable markets
- Risk: Medium - can accumulate inventory in trending markets

**Option 2: Inventory-Aware Market Maker**
- Adjusts quotes based on current position to reduce inventory risk
- Skews prices to encourage trades that reduce position
- Best for: Balanced exposure, risk management
- Risk: Lower - actively manages inventory

**Option 3: Momentum-Following Trader**
- Detects price direction from recent trades
- Buys when momentum is up, sells when momentum is down
- Best for: Trending markets, breakouts
- Risk: Higher - can be wrong on reversals

**Option 4: Mean Reversion Trader**
- Fades large moves expecting price to revert
- Buys after dips, sells after spikes
- Best for: Range-bound markets, overreactions
- Risk: Higher - can fight strong trends

**Option 5: Probability-Weighted Trader**
- Uses distance from 50% as a signal
- Bets on extremes reverting toward uncertainty
- Best for: Markets with overconfident pricing
- Risk: Medium - based on market efficiency assumptions

## Step 5: Generate the Bot Code

Based on the user's algorithm choice, generate a complete bot file. The bot should:

1. Load credentials from environment variables
2. Auto-register API keys if needed
3. Connect to the BTC 15-minute quick market
4. Implement the chosen algorithm
5. Include proper error handling
6. Cancel orders on shutdown
7. Handle market expiration gracefully

Use this template structure for all bots:

```python
"""
Turbine Market Maker Bot - {ALGORITHM_NAME}
Generated for Turbine

Algorithm: {ALGORITHM_DESCRIPTION}
"""

import asyncio
import os
import time
from dotenv import load_dotenv

from turbine_client import TurbineClient, TurbineWSClient, Outcome, Side
from turbine_client.exceptions import TurbineApiError, WebSocketError

# Load environment variables
load_dotenv()

# ============================================================
# CONFIGURATION - Adjust these parameters for your strategy
# ============================================================
ORDER_SIZE = 1_000_000  # 1 share (6 decimals)
MAX_POSITION = 5_000_000  # Maximum position size (5 shares)
QUOTE_REFRESH_SECONDS = 30  # How often to refresh quotes
# Algorithm-specific parameters added here...

def get_or_create_api_credentials():
    """Get existing credentials or register new ones."""
    api_key_id = os.environ.get("TURBINE_API_KEY_ID")
    api_private_key = os.environ.get("TURBINE_API_PRIVATE_KEY")

    if api_key_id and api_private_key:
        return api_key_id, api_private_key

    private_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if not private_key:
        raise ValueError("Set TURBINE_PRIVATE_KEY in your .env file")

    print("Registering new API credentials...")
    credentials = TurbineClient.request_api_credentials(
        host="https://api.turbinefi.com",
        private_key=private_key,
    )

    print(f"\nSAVE THESE TO YOUR .env FILE:")
    print(f"TURBINE_API_KEY_ID={credentials['api_key_id']}")
    print(f"TURBINE_API_PRIVATE_KEY={credentials['api_private_key']}")

    return credentials["api_key_id"], credentials["api_private_key"]


class MarketMakerBot:
    """Market maker bot implementation."""

    def __init__(self, client: TurbineClient):
        self.client = client
        self.market_id = None
        self.current_position = 0
        self.active_orders = {}
        # Algorithm state...

    # ... Algorithm implementation ...


async def main():
    # Get credentials
    private_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if not private_key:
        print("Error: Set TURBINE_PRIVATE_KEY in your .env file")
        return

    api_key_id, api_private_key = get_or_create_api_credentials()

    # Create client
    client = TurbineClient(
        host="https://api.turbinefi.com",
        chain_id=137,  # Polygon mainnet
        private_key=private_key,
        api_key_id=api_key_id,
        api_private_key=api_private_key,
    )

    print(f"Bot wallet address: {client.address}")

    # Get the active BTC 15-minute market
    quick_market = client.get_quick_market("BTC")
    print(f"Trading on: BTC @ ${quick_market.start_price / 1e8:,.2f}")

    # Run the bot
    bot = MarketMakerBot(client)
    try:
        await bot.run("https://api.turbinefi.com")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
```

## Step 6: Create the .env Template

Create a `.env.example` file showing required variables:

```
# Turbine Trading Bot Configuration

# Required: Your Ethereum wallet private key
# Get this from MetaMask or your wallet provider
TURBINE_PRIVATE_KEY=0x...

# Auto-generated on first run - save these after registration!
TURBINE_API_KEY_ID=
TURBINE_API_PRIVATE_KEY=
```

## Step 7: Explain How to Run

Tell the user:
```
To run your bot:

1. Copy .env.example to .env and add your private key:
   cp .env.example .env

2. Install dependencies:
   pip install turbine-py-client python-dotenv

3. Run the bot:
   python your_bot_file.py

4. On first run, the bot will register API credentials.
   SAVE the credentials it prints to your .env file!

5. The bot will automatically connect to the current BTC 15-minute market
   and start trading based on your chosen algorithm.
```

## Algorithm Implementation Details

When generating bots, use these implementations:

### Simple Spread Market Maker
```python
SPREAD_BPS = 200  # 2% total spread (1% each side)

def calculate_quotes(self, mid_price):
    """Calculate bid/ask around mid price."""
    half_spread = (mid_price * SPREAD_BPS) // 20000
    bid = max(1, mid_price - half_spread)
    ask = min(999999, mid_price + half_spread)
    return bid, ask
```

### Inventory-Aware Market Maker
```python
SPREAD_BPS = 200
SKEW_FACTOR = 50  # BPS skew per share of inventory

def calculate_quotes(self, mid_price):
    """Skew quotes based on inventory."""
    half_spread = (mid_price * SPREAD_BPS) // 20000

    # Skew to reduce inventory
    inventory_shares = self.current_position / 1_000_000
    skew = int(inventory_shares * SKEW_FACTOR)

    bid = max(1, mid_price - half_spread - skew)
    ask = min(999999, mid_price + half_spread - skew)
    return bid, ask
```

### Momentum Following
```python
MOMENTUM_WINDOW = 10  # Number of trades to consider
MOMENTUM_THRESHOLD = 0.6  # 60% same direction = trend

def detect_momentum(self, recent_trades):
    """Detect market momentum from recent trades."""
    if len(recent_trades) < MOMENTUM_WINDOW:
        return None

    buys = sum(1 for t in recent_trades[-MOMENTUM_WINDOW:] if t["side"] == "BUY")
    buy_ratio = buys / MOMENTUM_WINDOW

    if buy_ratio > MOMENTUM_THRESHOLD:
        return "UP"
    elif buy_ratio < (1 - MOMENTUM_THRESHOLD):
        return "DOWN"
    return None
```

### Mean Reversion
```python
REVERSION_THRESHOLD = 50000  # 5% move triggers fade
LOOKBACK_TRADES = 20

def should_fade(self, current_price, recent_trades):
    """Check if price moved enough to fade."""
    if len(recent_trades) < LOOKBACK_TRADES:
        return None

    avg_price = sum(t["price"] for t in recent_trades) / len(recent_trades)
    deviation = current_price - avg_price

    if deviation > REVERSION_THRESHOLD:
        return "SELL"  # Fade the up move
    elif deviation < -REVERSION_THRESHOLD:
        return "BUY"  # Fade the down move
    return None
```

### Probability-Weighted
```python
EDGE_THRESHOLD = 200000  # 20% from 50% = extreme

def find_edge(self, best_bid, best_ask):
    """Look for mispriced extremes."""
    mid = (best_bid + best_ask) // 2
    distance_from_fair = abs(mid - 500000)

    if distance_from_fair > EDGE_THRESHOLD:
        if mid > 500000:
            return "SELL"  # Market too bullish
        else:
            return "BUY"  # Market too bearish
    return None
```

## Important Notes for Users

- **Risk Warning**: Trading involves risk. Start with small sizes.
- **Testnet First**: Consider testing on Base Sepolia (chain_id=84532) first.
- **Monitor Positions**: Always monitor your bot and have stop-loss logic.
- **Market Expiration**: BTC 15-minute markets expire quickly. Bots handle this.
- **Gas/Fees**: Trading on Polygon has minimal gas costs but watch for fees.

## Quick Reference

**Price Scaling**: Prices are 0-1,000,000 representing 0-100%
- 500000 = 50% probability
- 250000 = 25% probability

**Size Scaling**: Sizes use 6 decimals
- 1_000_000 = 1 share
- 500_000 = 0.5 shares

**Outcome Values**:
- Outcome.YES (0) = BTC ends ABOVE strike price
- Outcome.NO (1) = BTC ends BELOW strike price
