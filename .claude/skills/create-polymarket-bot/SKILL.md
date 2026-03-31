---
name: create-polymarket-bot
description: Generate a Turbine bot that trades on Polymarket prediction markets. Handles auth, market scanning, and order placement through Turbine's API proxy.
argument-hint: "[strategy]"
---

# Create a Polymarket Trading Bot

Help the user build a Python bot that trades on **Polymarket** prediction markets through Turbine's API proxy. All traffic routes through Turbine — the bot never talks to Polymarket directly.

**What makes this different from Turbine-native bots:** Polymarket has thousands of markets across politics, sports, crypto, world events, and more. These aren't 15-minute quick markets — they're longer-duration prediction markets with diverse topics. The user's bot scans for interesting markets and trades based on its thesis.

---

## Step 0: Check Environment

```bash
# Check SDK is importable with Polymarket support
python3 -c "from turbine_client import PolymarketClient, get_polymarket_credentials; print('OK')" 2>&1

# Check for .env
test -f .env && echo "ENV_OK" || echo "NO_ENV"
```

If the SDK check fails, tell the user:
> "You need to install the SDK first: `pip install -e .` (from this repo) or `pip install turbine-client`"

If no .env exists, you'll create one in Step 1.

---

## Step 1: Polymarket Authentication

This is the biggest difference from Turbine-native bots. Users need Polymarket API credentials, which are obtained by signing an EIP-712 message with their wallet.

### Check if they already have credentials

```bash
grep -q "POLYMARKET_KEY" .env 2>/dev/null && echo "HAS_POLY_CREDS" || echo "NO_POLY_CREDS"
```

### If they DON'T have credentials

The SDK handles this automatically. The user just needs a private key (same wallet they'd use for Polymarket). Add this to the generated bot's startup:

```python
from turbine_client.polymarket import PolymarketClient
from turbine_client.polymarket_auth import get_polymarket_credentials

# First: get credentials (one-time)
client = PolymarketClient(host=TURBINE_HOST)
creds = get_polymarket_credentials(client, private_key=PRIVATE_KEY)

# Now create the authenticated client
client = PolymarketClient(
    host=TURBINE_HOST,
    polymarket_key=creds["apiKey"],
    polymarket_secret=creds["secret"],
    polymarket_passphrase=creds["passphrase"],
    private_key=PRIVATE_KEY,
)
```

**Important:** The wallet must have previously been used on Polymarket (deposited USDC, enabled trading). If `authenticate()` returns an error, the user needs to:
1. Go to https://polymarket.com
2. Connect their wallet
3. Deposit USDC and enable trading
4. Then come back and run the bot

### .env template for Polymarket bots

```
TURBINE_HOST=https://api.turbinefi.com
POLYMARKET_PRIVATE_KEY=0x...
# These get auto-populated after first auth, or set manually:
POLYMARKET_KEY=
POLYMARKET_SECRET=
POLYMARKET_PASSPHRASE=
CHAIN_ID=137
```

---

## Step 2: Understand the User

Ask two questions:

1. **"What kind of Polymarket markets are you interested in?"**
   - Options: "Crypto price markets" / "Politics & elections" / "Sports" / "Everything — scan for best opportunities" / "I have a specific market in mind"

2. **"How should your bot decide when to trade?"**
   - Options: "Buy underpriced outcomes (value betting)" / "Follow market momentum" / "I have my own thesis" / "Recommend something"

---

## Step 3: Choose a Strategy

Polymarket strategies differ from Turbine-native because markets are diverse and longer-duration.

| Strategy | How It Works | Best For |
|----------|-------------|----------|
| **Value Scanner** (recommended) | Scans markets for mispriced outcomes (YES price very low on likely events, or very high on unlikely ones). Buys what looks cheap. | Beginners. Simple thesis: find undervalued bets. |
| **Category Focus** | Filters to specific categories (crypto, politics, sports). Trades based on external signals or news. | Users with domain expertise. |
| **Momentum** | Watches price movement across markets. Buys into markets trending in one direction. | Active markets with clear sentiment shifts. |
| **Portfolio** | Builds a diversified portfolio across multiple markets. Manages total exposure and correlations. | Risk-conscious traders. |
| **Custom** | User defines their own signal logic. | Experienced users with a specific thesis. |

**Recommend Value Scanner for beginners.** It's the simplest: scan all markets, find ones where the price seems wrong, and buy.

---

## Step 4: Generate the Bot

**Reference implementation:** `examples/polymarket_bot.py`

Read it first — it contains the canonical patterns for:
- Credential loading from .env
- Auto-authentication if no credentials exist
- Market scanning and filtering
- Order placement through Turbine
- Position tracking
- Graceful shutdown

### What the generated bot MUST include

1. **Auto-auth flow:** If POLYMARKET_KEY is empty in .env, automatically run `get_polymarket_credentials()` and save the creds back to .env for next time.

2. **Market scanning loop:** Periodically fetch markets, filter by the user's criteria, and identify trading opportunities.

3. **Order management:** Place orders via `client.create_order()`. Include the `signed_order` from py_clob_client for authenticated order placement.

4. **Position tracking:** Periodically check `client.get_positions()` and log P&L.

5. **Error handling:** Catch `TurbineApiError`, handle rate limits, reconnect on failures.

6. **Graceful shutdown:** Handle SIGINT/SIGTERM, cancel open orders, log final positions.

7. **Logging:** Clear, timestamped logs showing market scans, trades, positions.

### Bot structure

```python
"""
Turbine Polymarket Bot — [Strategy Name]

[One-line description of what this bot does]

Usage:
    python my_polymarket_bot.py [--categories crypto,politics] [--max-positions 10]
"""

import asyncio, logging, os, signal, sys, time, argparse
from dotenv import load_dotenv
from turbine_client.polymarket import PolymarketClient
from turbine_client.polymarket_auth import get_polymarket_credentials
from turbine_client.exceptions import TurbineApiError

# Config from .env
# Auto-auth if needed
# Strategy class with scan() and should_trade() methods
# Main loop: scan → filter → trade → track → repeat
# Graceful shutdown
```

### Key differences from Turbine-native bots

- **No market rotation.** Polymarket markets last days/weeks/months, not 15 minutes.
- **No USDC approval flow.** That's handled on Polymarket's side.
- **No claiming.** Polymarket handles settlement natively.
- **Multiple simultaneous markets.** The bot can hold positions across many markets at once.
- **Order signing uses py_clob_client,** not the Turbine signer.

### Auto-save credentials pattern

```python
def ensure_credentials():
    """Get or create Polymarket credentials, saving to .env."""
    key = os.environ.get("POLYMARKET_KEY", "")
    if key:
        return  # Already have creds

    log.info("No Polymarket credentials found. Authenticating...")
    client = PolymarketClient(host=TURBINE_HOST)
    creds = get_polymarket_credentials(client, private_key=PRIVATE_KEY)

    # Save to .env for next time
    env_path = Path(__file__).parent / ".env"
    with open(env_path, "a") as f:
        f.write(f"\nPOLYMARKET_KEY={creds['apiKey']}\n")
        f.write(f"POLYMARKET_SECRET={creds['secret']}\n")
        f.write(f"POLYMARKET_PASSPHRASE={creds['passphrase']}\n")

    os.environ["POLYMARKET_KEY"] = creds["apiKey"]
    os.environ["POLYMARKET_SECRET"] = creds["secret"]
    os.environ["POLYMARKET_PASSPHRASE"] = creds["passphrase"]
    log.info("Credentials saved to .env")
```

---

## Step 5: Test & Run

After generating the bot:

1. Verify it parses and imports correctly:
   ```bash
   python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location('bot', 'my_polymarket_bot.py'); mod = importlib.util.module_from_spec(spec); print('Imports OK')"
   ```

2. Walk the user through running it:
   ```bash
   python my_polymarket_bot.py
   ```

3. Explain what they'll see: market scanning logs, trade decisions, position updates.

---

## Common Issues

- **"missing Polymarket credentials" error:** Auto-auth failed. User needs to visit polymarket.com first and enable trading with their wallet.
- **"HTTP 403" on orders:** Polymarket credentials expired. Delete POLYMARKET_KEY/SECRET/PASSPHRASE from .env and restart (auto-auth will re-derive).
- **"HTTP 401" on Turbine:** User needs a Turbine Pro subscription ($49/mo) for Polymarket access.
- **No markets returned:** The `?polymarket=true` proxy might not be deployed yet. Check with the team.
