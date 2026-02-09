# CLAUDE.md — Turbine Python Client

## What Turbine Is

Turbine is a trustless prediction markets platform built by Ojo. It lets anyone trade on whether BTC will go up or down in the next 15 minutes.

Every 15 minutes, a new market opens with a simple question: *"Will BTC be above $97,250 at 3:15 PM?"* Traders buy shares that represent their answer:

- **YES shares** pay out if BTC finishes above the strike price
- **NO shares** pay out if BTC finishes below

Shares are priced between $0.01 and $0.99, reflecting the market's confidence in each outcome. If you're right, your share pays out $1.00. If you're wrong, it pays $0.00.

**A concrete example:** You think BTC will stay above the strike. You buy a YES share at $0.60. If BTC ends above the strike, you get $1.00 back — a $0.40 profit. If it drops below, you lose your $0.60. The further the price is from 50/50, the cheaper the bet but the less likely you are to win.

**Currently live:** Only BTC Quick Markets (15-minute). Turbine's architecture supports other assets and timeframes, but BTC 15-min is the only active market right now.

**Platform:** https://beta.turbinefi.com (in beta)

### Turbine URLs

Use these for lookups, linking users to relevant pages, or fetching details you need:

| Resource | URL |
|----------|-----|
| Platform (main) | https://beta.turbinefi.com |
| Leaderboard | https://beta.turbinefi.com/leaderboard |
| Docs overview | https://beta.turbinefi.com/docs |
| Fees & Gas | https://beta.turbinefi.com/docs/fees-and-gas |
| Architecture | https://beta.turbinefi.com/docs/architecture |
| Build a Trading Bot | https://beta.turbinefi.com/docs/api/build-a-trading-bot |
| API Reference | https://beta.turbinefi.com/docs/api |
| Authentication | https://beta.turbinefi.com/docs/api/authentication |
| Contract Addresses | https://beta.turbinefi.com/docs/contract-addresses |
| Security Audit | https://beta.turbinefi.com/docs/security-scans |
| API Host | https://api.turbinefi.com |

If a user asks about Turbine features, fees, or mechanics that aren't covered in this file, fetch the relevant docs page.

### Why Gasless Matters

One of Turbine's key differentiators is that trading is entirely gasless. On most crypto platforms, every transaction costs gas fees paid in the chain's native token (ETH, MATIC, AVAX). Turbine eliminates this: users sign messages with their private key (free, off-chain), and Turbine's relayer submits the transactions on-chain and pays the gas. Users only ever need USDC — no other tokens.

This matters because it dramatically lowers the barrier to entry. A new user doesn't need to understand gas, buy native tokens, or manage multiple token balances. They just need USDC in their wallet.

### How It Works Under the Hood

Turbine runs an off-chain orderbook (CLOB) with on-chain settlement. Orders are signed off-chain using EIP-712, matched by Turbine's API, then settled on-chain via modified Gnosis CTF smart contracts. Market resolution is handled by the UMA Optimistic Oracle — after 15 minutes, the oracle checks BTC's price against the strike and declares a winner. The 1% flat fee per trade is the only cost.

### Competitions and Hackathons

Turbine is actively growing its user base through two channels:

**Weekly competitions:** An ongoing $100 prize for the bot with the highest percentage-based PnL each week. Leaderboard at https://beta.turbinefi.com/leaderboard. No limit on how many bots a single user can register — you can run multiple strategies simultaneously.

**Hackathons:** Turbine sponsors and runs hackathon events where participants build trading bots. These are time-boxed events with their own structure and prizes. (TODO: More detail on hackathon format needed from Turbine team.)

**Why this matters for Claude:** A user arriving in this repo is likely coming from one of these two paths. Someone from a hackathon may be under time pressure and need fast, guided setup. Someone exploring the weekly competition may want more depth on strategy design and performance optimization. Try to understand which context a user is in — it shapes what help they need most.

## What This Repo Is

This is the official Python SDK for Turbine's API, bundled with example trading bots and Claude Code skills for bot generation. It exists to get people trading on Turbine as fast as possible.

**Why it exists:** Turbine is a prediction markets platform, but a platform without traders is empty. This repo is the primary onboarding funnel — it's how new users go from "curious" to "actively trading." The easier it is to clone this repo, build a bot, and start competing, the more traders Turbine gets.

The typical user journey:
1. Discover Turbine through a hackathon, competition, or word of mouth
2. Clone this repo and set up a Python environment
3. Create a crypto wallet (MetaMask), configure `.env` with their private key
4. Fund the wallet with USDC (min ~$10 for Polygon mainnet, or free test USDC on Base Sepolia)
5. Use Claude Code (via the `/market-maker` skill) to generate a trading bot
6. Run the bot — it trades automatically, switching to new markets every 15 minutes
7. Compete in weekly PnL competitions or hackathon events
8. Optionally deploy to Railway for 24/7 operation (`/railway-deploy`)

## Who Uses This

Users range widely in both technical ability and prediction market knowledge. Think of it as a 2x2 matrix:

|  | Low Technical Ability | High Technical Ability |
|--|----------------------|----------------------|
| **Knows Prediction Markets** | Understands trading concepts and strategy, but needs help writing Python and navigating the codebase | Power user — can read the SDK source and self-serve |
| **New to Prediction Markets** | Needs the most help — both "what am I trading?" and "how do I code this?" | Comfortable with code, but needs prediction market concepts explained before they can design a strategy |

**How Claude should adapt:**

- **Always start by understanding the user.** Are they here for a hackathon or the weekly competition? Do they know what prediction markets are? Have they written Python before? A 30-second conversation up front saves 30 minutes of misguided help later.
- **If they don't understand prediction markets,** stop and explain before writing any code. Use the "What Turbine Is" section above and `docs/prediction-markets.md`. Make sure they understand what YES/NO shares are, what a strike price means, and how payouts work. A user who doesn't understand the trading mechanics can't evaluate whether their bot's strategy makes sense.
- **If they're non-technical,** do more for them — create files directly, run commands, and explain what's happening at each step in plain language. Don't present options that require technical judgment they can't make.
- **If they're experienced,** be concise. They don't need the preamble — just show them the API surface, the reference bot, and get out of the way.
- **When in doubt, ask.** A simple "Are you familiar with prediction markets, or would a quick overview help?" goes a long way.

## Repository Structure

```
turbine_client/              # Python SDK (DO NOT MODIFY)
  client.py                  # TurbineClient — all API methods
  types.py                   # Dataclasses: Market, Trade, Position, Side, Outcome
  config.py                  # Chain configs (Base Sepolia, Polygon, Avalanche)
  auth.py                    # Ed25519 bearer token auth
  signer.py                  # EIP-712 order signing
  exceptions.py              # TurbineError hierarchy
  http/client.py             # HTTP client with auth
  order_builder/             # Order creation helpers
  ws/client.py               # WebSocket streaming client

examples/                    # Example bots and SDK usage (see examples/README.md)
  price_action_bot.py        # Canonical reference bot — start here
  market_maker.py            # Market making bot
  ai_trading_bot.py          # LLM-powered trading bot
  basic_usage.py             # Simple SDK usage
  ...                        # Utilities, tests, more (14 files total)

docs/                        # Documentation
  prediction-markets.md      # What prediction markets are (for newcomers)
  onboarding.md              # Step-by-step: zero to running bot
  migrate-from-polymarket.md # Migration guide for Polymarket users

tests/                       # SDK test suite (pytest)
scripts/                     # Deployment and setup scripts
.claude/skills/              # Claude Code skills
  market-maker/SKILL.md      # /market-maker — generate a new trading bot
  railway-deploy/SKILL.md    # /railway-deploy — deploy bot to Railway
```

The SDK (`turbine_client/`) is maintained by Turbine's team and should never be modified. The `examples/` directory contains 14 files ranging from simple SDK usage snippets to full production-ready trading bots — `examples/README.md` explains what each one is. When generating new bots, use `examples/price_action_bot.py` as the structural reference.

## Helping a User Get Started

If a user is new, walk them through the steps below. For a more detailed version, point them to `docs/onboarding.md`. The goal is to get them from zero to a running bot with as little friction as possible.

### 1. Environment Setup
```bash
git clone https://github.com/ojo-network/turbine-py-client.git
cd turbine-py-client
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```
Always use a virtual environment. The `curl -sSL turbinefi.com/claude | bash` install script exists but may fail on managed machines — manual setup with a venv is more reliable.

### 2. Wallet & Credentials
The user needs an Ethereum-compatible wallet. This is just a public/private key pair — the private key is what the bot uses to sign transactions.

**MetaMask** is the easiest path for newcomers:
  - Install the MetaMask browser extension
  - Create a new account
  - Export private key: Settings → Security & Privacy → Export Private Key

**Or generate one in Python** (no browser extension needed):
```python
from eth_account import Account
acct = Account.create()
print(f"Address: {acct.address}")
print(f"Private Key: {acct.key.hex()}")
```

Then create a `.env` file (use the Write tool to create it for the user — don't just tell them to do it):
```
TURBINE_PRIVATE_KEY=0x...
TURBINE_API_KEY_ID=
TURBINE_API_PRIVATE_KEY=
CHAIN_ID=84532
TURBINE_HOST=https://api.turbinefi.com
```

The API credentials (`TURBINE_API_KEY_ID` and `TURBINE_API_PRIVATE_KEY`) don't need to be filled in manually. On first bot run, the SDK automatically registers API credentials by signing a message with the wallet, then saves them back to `.env`.

### 3. Funding
The bot needs USDC on whichever chain it's trading on:

- **Base Sepolia (84532):** Testnet — uses test USDC, no real money at risk. Good for learning.
- **Polygon (137):** Recommended for real trading. Needs real USDC on Polygon (minimum ~$10). Bridge from other chains or withdraw from an exchange that supports Polygon. USDC contract: `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359`.
- **Avalanche (43114):** Alternative mainnet.

No native gas tokens (MATIC, AVAX) are needed on any chain. Everything is gasless.

### 4. Build a Bot
The fastest path is the `/market-maker` skill — it walks the user through algorithm selection and generates a complete trading bot.

Alternatively, they can study `examples/price_action_bot.py` directly. This is the canonical reference implementation: 787 lines covering every aspect of the bot lifecycle (credentials, market management, USDC approval, order execution, position tracking, claiming winnings).

**Price Action is the recommended starting algorithm.** It fetches the live BTC price from Pyth Network — the same oracle Turbine uses to resolve markets — so the bot's trading signal is directly aligned with how winners are determined. This is the simplest and most intuitive strategy for newcomers.

### 5. Run It
```bash
python my_bot.py
```
Once running, the bot handles everything automatically: connects to the current BTC market, approves USDC (one-time gasless permit), places trades based on its algorithm, switches to new markets every 15 minutes, and claims winnings when markets resolve. The user can walk away.

For 24/7 operation without keeping a laptop open, use `/railway-deploy` to deploy to Railway (free $5 credit for 30 days).

## Helping a User Build a Strategy

The core creative decision in building a Turbine bot is the **trading signal**: given the current state of the market, should the bot buy YES, buy NO, or hold? Everything else — market management, USDC approval, order submission, position tracking, claiming — is infrastructure that follows the same pattern across all bots.

When a user wants to create or modify a bot:

1. **Understand their idea.** What signal do they want to trade on? Are they following price momentum? Fading large moves? Using external data? The clearer the thesis, the better the bot.

2. **Use the reference.** `examples/price_action_bot.py` is the canonical implementation. All bots should follow its structure for infrastructure. Only the signal logic (the `calculate_signal()` function and its supporting state) changes between strategies.

3. **Available algorithm types** (from Turbine's official docs):

   | Algorithm | Strategy | Risk | Best For |
   |-----------|----------|------|----------|
   | **Price Action** (recommended) | Fetches live BTC from Pyth, compares to strike. YES if above, NO if below. | Medium | Beginners, alignment with resolution oracle |
   | **Simple Spread** | Symmetric bid/ask around mid-price with fixed spread | Medium | Learning market making basics |
   | **Inventory-Aware** | Spread market making + adjusts quotes to reduce accumulated position | Lower | Balanced exposure |
   | **Momentum** | Detects price direction from recent trades, follows the trend | Higher | Trending markets |
   | **Mean Reversion** | Fades large moves, bets on reversion to average | Higher | Range-bound markets |
   | **Probability-Weighted** | Bets that prices far from 50% will revert toward uncertainty | Medium | Markets with overconfident pricing |

4. **Preserve critical infrastructure patterns.** These exist in every working bot and must not be removed or altered:
   - **Order verification chain:** After submitting an order, wait 2 seconds, then check failed trades → pending trades → recent trades → open orders. This sequence ensures the bot knows the true state of its order.
   - **Gasless USDC approval:** One-time max EIP-2612 permit per settlement contract. Check allowance first, skip if already approved.
   - **Market transitions:** Poll for new markets every 5 seconds. When a new market appears, cancel all orders on the old market, reset state, and start trading the new one.
   - **Claiming:** Background task that checks for resolved markets and claims winnings via the gasless relayer. Enforce a 15-second delay between claims (API rate limit).
   - **Market expiration:** Stop placing new orders when less than 60 seconds remain in a market. The `market_expiring` flag prevents the bot from getting stuck with orders on an expired market.

## SDK Quick Reference

### Key Types
```python
from turbine_client import TurbineClient, Outcome, Side

Side.BUY = 0, Side.SELL = 1
Outcome.YES = 0, Outcome.NO = 1
```

### Price & Size
- **Prices:** 0 to 1,000,000 = 0% to 100% (6 decimals). 500,000 = 50%.
- **Sizes:** 6 decimals. 1,000,000 = 1 share.
- **Strike price:** `quick_market.start_price / 1e6` = USD price. (Note: the README says `/1e8` in one place — that is wrong. Always use `/1e6`.)

### Common API Calls
```python
# Public (no auth required)
client.get_quick_market("BTC")           # Current 15-min market
client.get_orderbook(market_id)          # Orderbook snapshot
client.get_trades(market_id)             # Recent trades
client.get_markets()                     # All markets
client.get_resolution(market_id)         # Check if a market has resolved

# Trading (requires wallet + API credentials)
client.create_limit_buy(market_id, outcome, price, size)  # Create signed order
client.post_order(signed_order)          # Submit to orderbook
client.cancel_order(order_hash)          # Cancel an open order
client.get_user_positions(address)       # Current positions
client.get_orders(trader)                # Open orders

# Gasless relayer operations
client.approve_usdc_for_settlement(addr) # One-time max USDC permit (gasless)
client.claim_winnings(contract_addr)     # Claim from a resolved market (gasless)
client.batch_claim_winnings(addrs)       # Claim from multiple markets at once
```

### Supported Chains
| Chain | ID | Type | Notes |
|-------|-----|------|-------|
| Base Sepolia | 84532 | Testnet (default) | Safe for experimentation, test USDC |
| Polygon | 137 | Mainnet | Recommended for real trading, real USDC |
| Avalanche | 43114 | Mainnet | Alternative mainnet |

## Key Domain Concepts

For a deeper explanation aimed at newcomers, see `docs/prediction-markets.md`.

- **Market:** A 15-min binary question about BTC's price. A new one opens every 15 minutes. Each market has a unique `market_id` (hex string) that changes on rotation.
- **Strike price:** The BTC price threshold set when the market opens. If BTC ends above it, YES wins. Below, NO wins. This is the anchor that every trading decision revolves around.
- **Settlement address:** The on-chain contract that holds USDC collateral and executes trades. There's one per chain, shared across all markets. Requires a one-time gasless approval before the bot can trade.
- **Contract address:** A per-market contract for outcome tokens (ERC1155). Only needed when claiming winnings after a market resolves — not during trading.
- **Gasless:** Turbine's relayer pays all gas fees. Users sign messages with their private key (free, off-chain), and the relayer handles on-chain submission. This is why users only need USDC — no ETH, MATIC, or AVAX.
- **USDC approval:** A one-time max EIP-2612 permit per settlement contract. Once approved, all future orders on that chain reuse the allowance. No per-trade approval overhead.
- **UMA Oracle:** The decentralized oracle that resolves markets. After a market expires, UMA checks BTC's price and declares whether YES or NO wins. This is trustless — no single party controls the outcome.
- **Pyth Network:** Provides real-time BTC price data. This is the same feed Turbine uses for market resolution, which is why the Price Action strategy (which trades based on Pyth data) is recommended — the bot's signal aligns with how winners are determined.

## Files to Never Modify

- Everything in `turbine_client/` — the SDK is maintained by Turbine's team
- `examples/price_action_bot.py` — canonical reference implementation
- `tests/conftest.py` — test fixtures (unless adding new ones)

## Development

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests
pytest tests/ -v

# Lint
ruff check turbine_client/
```

**Style:** Python 3.9+ — use `X | None`, `dict[str, int]`, `list[str]` (not `Optional`, `Dict`, `List`).
