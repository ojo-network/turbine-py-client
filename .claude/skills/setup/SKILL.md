---
name: setup
description: Get a new user from zero to ready-to-trade on Turbine. Environment, wallet, credentials, funding.
---

# Turbine Setup

You are helping a user set up their environment to trade on Turbine's prediction markets. This skill handles everything from cloning the repo to having a funded wallet — after this, the user is ready to create their first bot.

### Key URLs

Reference these throughout setup — both for your own lookups and to share with users:

- **Platform:** https://beta.turbinefi.com
- **Leaderboard:** https://beta.turbinefi.com/leaderboard
- **Docs (overview):** https://beta.turbinefi.com/docs
- **Fees & Gas:** https://beta.turbinefi.com/docs/fees-and-gas
- **Architecture:** https://beta.turbinefi.com/docs/architecture
- **Build a Trading Bot:** https://beta.turbinefi.com/docs/api/build-a-trading-bot
- **API Reference:** https://beta.turbinefi.com/docs/api
- **Authentication:** https://beta.turbinefi.com/docs/api/authentication
- **API Host:** https://api.turbinefi.com

If a user asks questions you can't answer from CLAUDE.md or the repo, fetch the relevant docs page above.

**What this skill does NOT do:**
- Generate any bot code (that's `/create-bot`)
- Explain trading algorithms or strategy design
- Deploy anything to the cloud (that's `/railway-deploy`)

---

## Step 0: Understand Who You're Helping

This may be the user's very first interaction with Claude in this repo. Before touching any code, figure out who they are. This shapes everything — how much you explain, what you skip, and what tone you use.

Turbine's users fall into a 2x2 matrix (see CLAUDE.md for full details):

|  | Low Technical | High Technical |
|--|---------------|----------------|
| **Knows PMs** | Understands trading, needs code help | Power user, can self-serve |
| **New to PMs** | Needs help with everything | Can code, needs PM concepts first |

Use `AskUserQuestion` with **two questions**:

1. **"How comfortable are you with Python and the command line?"**
   - Options: "Beginner — I'll need guidance" / "Comfortable — I've used Python before" / "Expert — just show me what to run"

2. **"How familiar are you with prediction markets?"**
   - Options: "Never heard of them" / "I get the concept but haven't traded" / "I've traded prediction markets before"

**Adapt your behavior based on the answers:**

- **Low tech + low PM:** Be thorough on everything. Explain what a virtual environment is, what a private key is, what USDC is. Don't assume any prior knowledge. This is the largest potential user group.
- **Low tech + high PM:** They understand the trading side — don't over-explain markets. Focus your patience on the technical steps (Python, wallet, .env).
- **High tech + low PM:** The code setup will be fast — they might not even need your help. But pause and make sure they understand what they're actually trading before moving on. Reference `docs/prediction-markets.md` or explain the core concepts from CLAUDE.md.
- **High tech + high PM:** Be concise. Skip explanations, just run the commands and move fast. They'll ask if they need something.

Carry this context through every subsequent step. A beginner needs "here's what a virtual environment is and why we use one." An expert needs "setting up venv" and nothing more.

### Save the user context

After the questions above, also ask:

3. **"What brings you to Turbine?"**
   - Options: "I'm in a hackathon right now" / "I want to compete in the weekly competition" / "Just exploring / learning" / "Building for a specific project"

**Create `user-context.md` in the repo root** using the Write tool. This file persists across sessions and skills so Claude doesn't have to re-ask these questions every time. It's gitignored (personal to this user).

```markdown
# User Context

## Profile
- **Technical level:** [beginner / comfortable / expert]
- **PM familiarity:** [none / conceptual / experienced]
- **Goal:** [hackathon / weekly competition / exploring / specific project]

## Setup Status
- **Date:** [today's date]
- **Chain:** [Base Sepolia / Polygon / Avalanche]
- **Wallet address:** [filled in after Step 3]

## Notes
[Any other context gathered during conversation — e.g., "interested in momentum strategies", "coming from Polymarket", "has 3 days for hackathon"]
```

Add `user-context.md` to `.gitignore` if it's not already there — this file is personal and should never be committed.

**Why this file matters:** Other skills (like `/create-bot`) will read `user-context.md` instead of re-asking the same questions. If a user runs `/create-bot` without having run `/setup`, Claude can still ask — but if the file exists, Claude already knows who it's helping.

---

## Step 1: Assess Current State

Before doing anything, figure out where the user already is. Run these checks silently — don't ask the user, just detect:

```bash
# Python available?
python3 --version 2>&1

# In a virtual environment?
echo "VIRTUAL_ENV: ${VIRTUAL_ENV:-not set}"

# Can we import the SDK?
python3 -c "import turbine_client; print('SDK importable')" 2>&1

# Does .env exist with a private key?
test -f .env && grep -q "TURBINE_PRIVATE_KEY=0x" .env && echo "PRIVATE_KEY_SET" || echo "NO_PRIVATE_KEY"

# Are API credentials populated?
test -f .env && grep -q "TURBINE_API_KEY_ID=." .env && echo "API_CREDS_SET" || echo "NO_API_CREDS"
```

Based on results, skip any steps that are already complete. Tell the user what you found:

> "Here's where you stand: [Python OK / venv active / SDK installed / .env missing]. Let me help you with the remaining steps."

If **everything** is already set up, say so and suggest `/create-bot`:

> "You're fully set up — Python environment, SDK, wallet credentials, everything looks good. Ready to build a bot? Run `/create-bot` to get started."

---

## Step 2: Python Environment

**Skip if:** Python 3.9+ is available AND a venv is active AND `turbine_client` imports successfully.

### If no virtual environment:

```bash
python3 -m venv .venv && source .venv/bin/activate
```

Explain briefly: *"A virtual environment keeps Turbine's dependencies separate from your system Python. This prevents version conflicts."*

### If SDK not installed:

```bash
pip install -e .
```

This installs the Turbine SDK and all its dependencies from the repo's `pyproject.toml`.

### Verify:

```bash
python3 -c "from turbine_client import TurbineClient; print('Turbine SDK ready')"
```

If this fails, troubleshoot:
- Wrong Python version? Need 3.9+
- Not in the repo root? `cd` to where `pyproject.toml` lives
- pip install failed? Check error output, likely a missing system dependency

---

## Step 3: Wallet & Private Key

**Skip if:** `.env` exists and contains `TURBINE_PRIVATE_KEY=0x...` (non-empty).

The user needs an Ethereum-compatible private key. This is what the bot uses to sign transactions — it never leaves their machine.

### Ask first:

Use `AskUserQuestion`:
- **"Do you already have an Ethereum wallet (e.g., MetaMask)?"**
- Options: "Yes, I have a private key ready" / "No, I need to create one"

### If they have a key:

Ask them to paste it. **Reassure them:**
> "Your private key stays local in the `.env` file — it's gitignored, so it won't be committed to version control. It's used to sign transactions (free, off-chain) and is never sent to any server."

### If they need to create one:

Offer two options:

**Option A — Generate in Python (fastest):**
```bash
python3 -c "from eth_account import Account; a = Account.create(); print(f'Address: {a.address}'); print(f'Private Key: {a.key.hex()}')"
```

Tell them to **save the address** (they'll need it for funding) and that you'll put the private key in `.env` for them.

**Option B — MetaMask (if they want a browser wallet):**
1. Install MetaMask browser extension from metamask.io
2. Create a new wallet (save the seed phrase somewhere safe)
3. Export private key: Click account icon → Settings → Security & Privacy → Export Private Key
4. Copy the key

### Create the .env file:

Once you have the private key, **create the file directly using the Write tool**. Don't tell the user to do it — do it for them:

```
TURBINE_PRIVATE_KEY=0x<their_key>
TURBINE_API_KEY_ID=
TURBINE_API_PRIVATE_KEY=
CHAIN_ID=84532
TURBINE_HOST=https://api.turbinefi.com
```

**Explain the fields briefly:**
- `TURBINE_PRIVATE_KEY` — Their wallet's signing key. Never leaves this machine.
- `TURBINE_API_KEY_ID` / `TURBINE_API_PRIVATE_KEY` — Left blank intentionally. The bot auto-registers API credentials on first run and saves them back to this file.
- `CHAIN_ID=84532` — Base Sepolia (testnet). Safe for learning. Switch to `137` (Polygon) for real trading later.
- `TURBINE_HOST` — Turbine's API endpoint.

---

## Step 4: Funding

**Skip if:** User says they already have USDC on their target chain.

The bot needs USDC (a stablecoin pegged to $1) on whichever blockchain it trades on. No other tokens are needed — Turbine is fully gasless.

### Explain the chain options:

Use `AskUserQuestion`:
- **"Which chain do you want to trade on?"**
- Options:
  - "Base Sepolia — testnet, no real money (Recommended for learning)"
  - "Polygon — real USDC, real trading, weekly competitions"

### If Base Sepolia (testnet):

> "Base Sepolia uses test USDC — no real money at risk. Great for learning how everything works before trading with real funds."

Testnet USDC acquisition varies — the user may need to get test tokens from a faucet or from someone on the Turbine team. Guide them to check Turbine's Discord or docs for the current faucet flow.

Update `.env` to set `CHAIN_ID=84532` (should already be the default).

### If Polygon (mainnet):

> "Polygon uses real USDC. You'll need at least ~$10 of USDC on the Polygon network. You can bridge USDC from other chains or withdraw from an exchange (Coinbase, Binance, etc.) that supports Polygon withdrawals."

**USDC contract on Polygon:** `0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359`

Update `.env` to set `CHAIN_ID=137`:

```
CHAIN_ID=137
```

Remind them: **No MATIC or other gas tokens needed.** Turbine's relayer pays all gas fees. They only need USDC.

---

## Step 5: Verify Everything

Run a final check to make sure the full setup works:

```bash
# Activate venv if needed
source .venv/bin/activate 2>/dev/null

# Verify SDK imports
python3 -c "
from turbine_client import TurbineClient
from dotenv import load_dotenv
import os

load_dotenv()

pk = os.environ.get('TURBINE_PRIVATE_KEY', '')
chain = os.environ.get('CHAIN_ID', '84532')
host = os.environ.get('TURBINE_HOST', 'https://api.turbinefi.com')

if not pk or pk == '0x':
    print('FAIL: No private key in .env')
else:
    client = TurbineClient(host=host, chain_id=int(chain), private_key=pk)
    print(f'Wallet address: {client.address}')
    print(f'Chain: {chain}')
    print(f'Host: {host}')

    # Try fetching current market to verify API connectivity
    try:
        qm = client.get_quick_market('BTC')
        strike = qm.start_price / 1e6
        print(f'Current BTC market: strike \${strike:,.2f}')
        print('API connection: OK')
    except Exception as e:
        print(f'API connection: FAILED ({e})')

print()
print('Setup verification complete.')
"
```

Report results to the user clearly:
- Wallet address (so they know where to send USDC)
- Chain they're configured for
- Whether the API is reachable
- Whether there's an active BTC market (confirms everything works end-to-end)

**Update `user-context.md`** with the wallet address and chain from the verification output. This keeps the user context file current for other skills.

---

## Step 6: Handoff

Everything is set up. Tell the user what they've accomplished and what's next:

> **You're all set up!** Here's what's ready:
> - Python environment with Turbine SDK installed
> - Wallet configured (address: `0x...`)
> - Trading on [chain name]
> - API connection verified
>
> **Next step: Create your first trading bot.**
>
> Run `/create-bot` — it'll help you pick a trading algorithm and generate a complete bot file. The recommended starting point is the **Price Action** strategy, which trades based on real-time BTC price movement.
>
> Or if you want to explore first:
> - Read `examples/price_action_bot.py` to see how a complete bot works
> - Check `docs/prediction-markets.md` to understand how Turbine's markets work
> - Browse `examples/README.md` for a guide to all example files

Use `AskUserQuestion`:
- **"Want to create your first trading bot now?"**
- Options: "Yes, let's build a bot" / "No, I want to explore first"

If yes: Tell them to run `/create-bot`.
If no: Wish them well and remind them `/create-bot` is there when they're ready.
