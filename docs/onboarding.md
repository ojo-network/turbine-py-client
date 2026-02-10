# Getting Started with Turbine

This guide walks you from zero to a running trading bot. If you're using Claude Code, the `/setup` skill does all of this interactively — but this page covers the same ground for people who prefer reading docs.

## Prerequisites

- **Python 3.9+** (check with `python3 --version`)
- **git** (check with `git --version`)
- **A terminal** (Terminal on Mac, Command Prompt/PowerShell on Windows, any Linux terminal)
- **Claude Code** (optional but recommended) — install from https://claude.com/claude-code

## 1. Clone and Install

```bash
git clone https://github.com/ojo-network/turbine-py-client.git
cd turbine-py-client
python3 -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -e .
```

Verify it worked:
```bash
python3 -c "from turbine_client import TurbineClient; print('SDK ready')"
```

> **Why a virtual environment?** It keeps Turbine's dependencies separate from your system Python. This prevents version conflicts and makes cleanup easy — just delete the `.venv` folder.

## 2. Create a Wallet

Your bot needs an Ethereum-compatible private key to sign transactions. This key never leaves your machine.

### Option A: Generate in Python (fastest)

```bash
python3 -c "
from eth_account import Account
acct = Account.create()
print(f'Address: {acct.address}')
print(f'Private Key: {acct.key.hex()}')
"
```

Save both values. You'll need the address for funding and the private key for the next step.

### Option B: MetaMask (if you want a browser wallet too)

1. Install the [MetaMask browser extension](https://metamask.io)
2. Create a new wallet and save your seed phrase
3. Export your private key: Account icon → Settings → Security & Privacy → Export Private Key

## 3. Configure .env

Create a `.env` file in the repo root:

```
TURBINE_PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE
TURBINE_API_KEY_ID=
TURBINE_API_PRIVATE_KEY=
CHAIN_ID=137
TURBINE_HOST=https://api.turbinefi.com
```

**What each field does:**
- `TURBINE_PRIVATE_KEY` — Your wallet's signing key. Used locally to sign transactions.
- `TURBINE_API_KEY_ID` / `TURBINE_API_PRIVATE_KEY` — Leave blank. The bot auto-registers API credentials on first run and fills these in.
- `CHAIN_ID=137` — Polygon mainnet, where Turbine's active markets are.
- `TURBINE_HOST` — Turbine's API endpoint.

## 4. Fund Your Wallet

Turbine currently runs on **Polygon mainnet**. Your wallet needs real USDC (minimum ~$10). **No gas tokens (ETH, MATIC) are needed** — Turbine is fully gasless.

The default bot sizes are small ($0.10 per trade), so $10 lasts a long time while you're learning.

**If you already have crypto:**
- Send USDC to your wallet address on the Polygon network
- Bridge from another chain using [Jumper](https://jumper.exchange) if needed

**If you're new to crypto:**
1. Create an account on an exchange like [Coinbase](https://coinbase.com)
2. Buy USDC (at least $10)
3. Withdraw to your wallet address — select **Polygon** as the network

**For hackathon participants:** Your hackathon organizer may provide USDC directly. Share your wallet address with them.

USDC contract on Polygon: `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359`

## 6. Build a Bot

### With Claude Code (recommended)
```bash
claude "/create-bot"
```
Claude walks you through algorithm selection and generates a complete trading bot.

### Without Claude Code
Study `examples/price_action_bot.py` — the canonical reference bot. It's ~787 lines covering the full lifecycle. See `examples/README.md` for a guide to all example files.

The **Price Action** strategy is recommended for beginners. It fetches the live BTC price from Pyth Network (the same oracle Turbine uses to resolve markets) and compares it to the strike. Simple, intuitive, and directly aligned with how winners are determined.

## 7. Run It

```bash
source .venv/bin/activate    # If not already active
python price_action_bot.py
```

### What happens on first run

1. **API credentials register** — the bot signs a message with your wallet, gets API keys, and saves them to `.env`
2. **USDC approval** — a one-time gasless permit is signed to allow trading
3. **Trading starts** — the bot fetches the current BTC market, runs its strategy, and places trades
4. **Market rotation** — every 15 minutes the market expires and a new one opens. The bot switches automatically.
5. **Claiming** — the bot claims winnings from resolved markets in the background

Press `Ctrl+C` to stop. The bot cancels all open orders on shutdown.

## 8. What's Next

- **Watch the leaderboard** — https://beta.turbinefi.com/leaderboard
- **Try another strategy** — run `/create-bot` again or write your own signal logic
- **Deploy 24/7** — use `/railway-deploy` to put your bot in the cloud (free $5 Railway credit)
- **Read the code** — `examples/price_action_bot.py` shows everything the bot does under the hood
- **Customize parameters** — most bots accept `--order-size` and `--max-position` flags

## Troubleshooting

**`pip install -e .` fails with "externally managed environment"**
You're not in a virtual environment. Run `python3 -m venv .venv && source .venv/bin/activate` first.

**`ModuleNotFoundError: No module named 'turbine_client'`**
Either the venv isn't active or the SDK isn't installed. Run `source .venv/bin/activate && pip install -e .`

**Bot says "No active BTC market"**
Markets rotate every 15 minutes. Wait a moment — a new market should open shortly.

**401 errors on order submission**
Try clearing the API credentials in `.env` (set `TURBINE_API_KEY_ID=` and `TURBINE_API_PRIVATE_KEY=` to blank) and restarting the bot. It will re-register fresh credentials.
