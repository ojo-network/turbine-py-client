---
name: create-bot
description: Generate a Turbine trading bot. Pick an algorithm, get a complete bot file. Use after /setup.
argument-hint: "[algorithm]"
---

# Create a Turbine Trading Bot

Here's what you're helping the user build: **a Python file that automatically trades on Turbine's Bitcoin prediction markets.**

Every 15 minutes, Turbine opens a new market asking "Will BTC be above $X at [time]?" The user's bot watches these markets and places trades — buying YES shares if it thinks BTC will be above the strike, or NO shares if it thinks BTC will be below. When the market resolves 15 minutes later, winning shares pay out $1.00.

**A trading bot is a single Python file.** When you run `python my_bot.py`, it connects to Turbine, starts watching the current BTC market, and executes trades according to its strategy. It handles everything automatically — market rotation every 15 minutes, gasless USDC approval, order management, and claiming winnings.

**Different strategies = different Python files.** A Price Action bot and a Momentum bot are two separate files. Each one implements its own signal logic (the "should I buy YES, buy NO, or hold?" decision) while sharing the same underlying infrastructure for connecting to Turbine, managing orders, and handling the market lifecycle.

The creative core is the **signal function** — that's where the user's trading idea lives. Everything else is plumbing that follows a standard pattern.

**This skill replaces the old `/market-maker` skill.** If a user mentions `/market-maker`, they mean this.

### Key URLs

Reference these when explaining algorithms, linking users to docs, or looking up details:

- **Platform:** https://beta.turbinefi.com
- **Leaderboard:** https://beta.turbinefi.com/leaderboard
- **Build a Trading Bot:** https://beta.turbinefi.com/docs/api/build-a-trading-bot
- **Fees & Gas:** https://beta.turbinefi.com/docs/fees-and-gas
- **Architecture:** https://beta.turbinefi.com/docs/architecture
- **API Reference:** https://beta.turbinefi.com/docs/api
- **API Host:** https://api.turbinefi.com

If a user asks about algorithm details, fee structures, or platform mechanics you're unsure of, fetch the relevant page above.

---

## Step 0: Understand Who You're Helping

### Check for existing user context

First, check if `user-context.md` exists in the repo root. This file is created by the `/setup` skill and contains the user's technical level, PM familiarity, and goals.

```bash
test -f user-context.md && echo "USER_CONTEXT_EXISTS" || echo "NO_USER_CONTEXT"
```

**If it exists**, read it. You now know their technical level, PM familiarity, what they're here for (hackathon, competition, exploring), and their chain/wallet. Adapt accordingly — don't re-ask what you already know.

**If it doesn't exist**, the user may have skipped `/setup` or set up manually. Ask directly using `AskUserQuestion` with **two questions**:

1. **"How comfortable are you with Python?"**
   - Options: "Beginner" / "Comfortable" / "Expert"

2. **"How familiar are you with prediction markets?"**
   - Options: "New to them" / "Understand the concept" / "Experienced trader"

This matters because it changes how you explain things throughout the rest of this flow. A beginner needs the intro explained carefully. An expert wants to skip to algorithm selection.

### Quick setup check

Verify the user's environment is ready. Run silently:

```bash
# Check for .env with private key
test -f .env && grep -q "TURBINE_PRIVATE_KEY=0x" .env && echo "ENV_OK" || echo "NO_ENV"

# Check SDK is importable
python3 -c "import turbine_client" 2>&1 && echo "SDK_OK" || echo "NO_SDK"
```

**If either check fails**, don't try to fix it inline. Tell the user:

> "Looks like your environment isn't set up yet. Run `/setup` first — it'll walk you through Python, wallet, and credentials. Come back here when you're ready to build."

Then **stop**. Don't continue.

**If both pass**, proceed to the intro.

---

## Step 1: Set the Context

Before jumping into algorithm selection, make sure the user understands what they're about to build. This is especially important for users who are new to prediction markets — they need to understand what they're trading before they can make an informed choice about how to trade it.

Explain clearly:

> **Here's what we're building:** A Python bot that trades on Turbine's Bitcoin prediction markets.
>
> Every 15 minutes, a new market opens: *"Will BTC be above $X?"* Your bot will decide whether to buy YES (bet BTC stays above) or NO (bet BTC goes below), based on a strategy you choose. If your bot is right, each share pays out $1.00. If it's wrong, you lose what you paid.
>
> The bot handles everything automatically — connecting to Turbine, placing trades, switching to new markets every 15 minutes, and claiming winnings. You just pick the strategy and run it.
>
> Each strategy is a separate Python file. You can create multiple bots with different strategies and compare how they perform.

**Adapt the depth based on the user's profile:**
- **New to PMs:** Give the full explanation above. Make sure they understand YES/NO shares, strike price, and the payout mechanic. Reference `docs/prediction-markets.md` if they want to go deeper.
- **Knows PMs:** Keep it brief — "We're building a Python bot to trade Turbine's 15-min BTC binary markets. Let's pick a strategy."
- **Expert:** Skip entirely if they already indicated what they want.

Use `AskUserQuestion`:
- **"Does this make sense? Ready to pick a strategy?"**
- Options: "Yes, let's go" / "I'd like to understand more first"

If they want more info, answer their questions. Reference CLAUDE.md, `docs/prediction-markets.md`, or the Turbine docs URLs above. Don't rush past this — a user who doesn't understand what they're trading can't evaluate whether their strategy makes sense.

If they're ready, proceed.

---

## Step 2: Choose a Strategy

If the user passed an argument (e.g., `/create-bot momentum`), use `$ARGUMENTS` to skip directly to that algorithm.

Otherwise, ask what they're looking for. Use `AskUserQuestion`:

**"What kind of trading strategy interests you?"**

Options:
- "Recommend something for me" → Price Action (see below)
- "I have my own idea" → Listen, map it to the closest type or build custom
- "Show me all the options" → Present the table below

### Algorithm Options

Each algorithm answers the same core question differently: *"Given the current market, should I buy YES, buy NO, or hold?"*

| # | Algorithm | How It Decides | Risk | Best For |
|---|-----------|---------------|------|----------|
| 1 | **Price Action** (recommended) | Compares live BTC price (Pyth) to strike price. Above strike → YES, below → NO. | Medium | Beginners. Signal aligns with how markets resolve. |
| 2 | **Simple Spread** | Places bid + ask around mid-price with fixed spread. Profits from the spread. | Medium | Learning market making basics. |
| 3 | **Inventory-Aware** | Like Simple Spread, but skews quotes to reduce accumulated position. | Lower | Balanced exposure, less directional risk. |
| 4 | **Momentum** | Detects which direction recent trades are flowing. Follows the trend. | Higher | Trending markets, breakouts. |
| 5 | **Mean Reversion** | Fades large moves — buys after dips, sells after spikes. Bets on reversion. | Higher | Range-bound markets, overreactions. |
| 6 | **Probability-Weighted** | Bets that prices far from 50% will revert toward uncertainty. | Medium | Markets with overconfident pricing. |

**Why Price Action is recommended for beginners:** It uses Pyth Network — the same oracle Turbine uses to resolve markets. The bot's trading signal is directly aligned with how winners are determined. It's the simplest to understand and the most intuitive to reason about.

**If the user has their own idea:** Listen to what they describe. Map it to the closest algorithm type above, or if it's truly novel, design a custom signal function that fits into the standard bot structure. The infrastructure stays the same — only the signal logic changes.

Use `AskUserQuestion` to confirm their choice.

---

## Step 3: Generate the Bot

### Reference implementation

**Read `examples/price_action_bot.py` first.** This is the canonical reference — a complete, production-ready bot (~787 lines) that handles the entire lifecycle. Every generated bot should follow its structure.

**CRITICAL: Do not use inline code snippets from this skill as the basis for generated code.** Always read the actual reference file. It contains tested patterns for:
- Credential loading and auto-registration
- Gasless USDC approval (one-time max permit per settlement)
- Order creation, submission, and verification
- Position tracking in USDC terms
- Market transition detection and handling
- Background claiming of winnings from resolved markets
- Clean shutdown on Ctrl+C

### What changes between strategies

The **only things that change** between algorithms are:

1. **The signal function** — the core logic that decides BUY_YES / BUY_NO / HOLD
2. **Algorithm-specific state** — any data the signal needs (price history, trade history, etc.)
3. **Algorithm-specific parameters** — configurable knobs (thresholds, windows, spreads)
4. **The docstring** — describe what this specific bot does

Everything else — credentials, market management, USDC approval, order execution, position tracking, claiming — comes directly from the reference implementation. Don't rewrite it, don't simplify it, don't "improve" it.

### Generation approach

**For Price Action (algorithm 1):**
The reference implementation IS a Price Action bot. Copy it and let the user customize parameters (order size, max position, confidence thresholds).

**For all other algorithms (2-6):**
1. Read `examples/price_action_bot.py` for the full infrastructure
2. Keep ALL infrastructure code identical
3. Replace `calculate_signal()` with the new algorithm's logic
4. Replace `get_current_btc_price()` only if the new algorithm doesn't need external price data
5. Add any algorithm-specific state to `__init__`
6. Update the docstring and parameter defaults

### Signal logic for each algorithm

When generating non-Price-Action bots, here's the core signal logic to implement. **These are conceptual — adapt them to fit the reference implementation's structure (Signal dataclass, confidence scores, etc.).**

**Simple Spread (2):**
- Get orderbook mid-price: `(best_bid + best_ask) / 2`
- Place a BUY order at `mid - half_spread` and a SELL order at `mid + half_spread`
- Spread parameter: configurable BPS (default 200 = 2%)
- Requires placing TWO orders per cycle (both sides)

**Inventory-Aware (3):**
- Same as Simple Spread, but skew the quotes based on current position
- If holding YES shares → lower the bid more (discourage more buying, encourage selling)
- Skew factor: `position_shares * skew_bps` adjustment to both bid and ask

**Momentum (4):**
- Track the last N trades from `client.get_trades(market_id)`
- Calculate buy ratio: `buys / total` over the window
- If buy ratio > threshold (e.g., 0.65) → BUY_YES (following the crowd)
- If buy ratio < (1 - threshold) → BUY_NO
- Otherwise HOLD

**Mean Reversion (5):**
- Track recent trade prices, compute a moving average
- If current price > average + reversion_threshold → sell into the move (BUY_NO)
- If current price < average - reversion_threshold → buy the dip (BUY_YES)
- Requires a warmup period (don't trade until you have enough history)

**Probability-Weighted (6):**
- Look at the mid-price as an implied probability
- If mid > 70% (700,000) → market may be overconfident → BUY_NO
- If mid < 30% (300,000) → market may be overly bearish → BUY_YES
- The further from 50%, the larger the edge (scale confidence with distance)

### File naming and location

Save the generated bot in the **repo root** with a descriptive name:
- `price_action_bot.py` (if different from the example)
- `momentum_bot.py`
- `mean_reversion_bot.py`
- `spread_bot.py`
- etc.

Tell the user where you saved it.

---

## Step 4: Configure Parameters

After generating, walk the user through the key parameters they can tweak:

**Universal parameters (all algorithms):**
- `--order-size` — USDC per trade (default: $1). Start small.
- `--max-position` — Maximum total USDC exposed (default: $10). Limits risk.

**Algorithm-specific parameters:**
- Spread bots: spread width (BPS)
- Momentum: lookback window, threshold
- Mean Reversion: reversion threshold, lookback trades
- Probability-Weighted: edge threshold (distance from 50%)

**Important: Remind them about risk.**
> "Start with small sizes while you're testing. You can increase later once you see how the bot performs. If you're on Base Sepolia (testnet), there's no real money at risk."

---

## Step 5: Run It

Tell the user how to run their bot:

```bash
python <bot_filename>.py
```

Explain what will happen on first run:
1. **API credentials auto-register** — the bot signs a message with the wallet, gets API keys, and saves them to `.env`. This takes a few seconds on the very first run.
2. **USDC approval** — the bot signs a gasless permit to allow trading. One-time per chain.
3. **Trading begins** — the bot fetches the current BTC market, runs its algorithm, and places trades.
4. **Market rotation** — every 15 minutes, the market rotates. The bot detects this automatically, cancels old orders, and switches to the new market.
5. **Claiming** — when past markets resolve, the bot automatically claims any winnings via the gasless relayer.

> "You can leave it running — it handles everything. Press `Ctrl+C` to stop. The bot cancels all open orders on shutdown."

---

## Step 6: What's Next

After the bot is running, suggest next steps based on the user's goals (from `user-context.md` or what they've told you):

**For competition users:**
> Check the leaderboard at https://beta.turbinefi.com/leaderboard to see how your PnL ranks. You can run multiple strategies simultaneously — try `/create-bot` again with a different algorithm and compare results.

**For hackathon users:**
> You've got a working bot! If time allows, try tweaking parameters or building a second strategy. Deploy to Railway with `/railway-deploy` so it keeps trading while you work on other things.

**For explorers:**
> Watch the logs to see how your bot makes decisions. When you're ready, tweak the parameters, try a different algorithm, or design your own signal logic. Each strategy is just a Python file — experiment freely.

**For everyone:**
> - **Deploy 24/7** — run `/railway-deploy` to put your bot in the cloud (free $5 Railway credit for 30 days)
> - **Build another strategy** — run `/create-bot` again with a different algorithm
> - **Read the code** — `examples/price_action_bot.py` shows exactly what your bot is doing under the hood

**Update `user-context.md`** with a note about which bot was created (strategy type, filename) under a `## Bots Created` section. This helps Claude in future sessions know what the user has already built.

---

## Critical Infrastructure Patterns

**DO NOT modify these when generating bots.** They exist in the reference implementation for a reason and must be preserved exactly:

1. **Order verification chain:** After `post_order()`, sleep 2 seconds, then check failed trades → pending trades → recent trades → open orders. This sequence ensures the bot knows the true state of its order. Skipping steps causes phantom orders or missed fills.

2. **Gasless USDC approval:** One-time max EIP-2612 permit per settlement contract. Check allowance first, skip if already approved. Never do per-order approvals.

3. **Market transitions:** Poll every 5 seconds for new markets. On transition: cancel all orders on the old market, reset state (pending orders, processed trade IDs, expiration flag), approve USDC for the new settlement if needed, then resume trading.

4. **Claiming:** Background task checks for resolved markets every 120 seconds. Enforce 15-second delay between individual claim calls (API rate limit). Remove markets from tracking after successful claim or if no position exists.

5. **Market expiration:** Set `market_expiring = True` when < 60 seconds remain. Stop placing new orders. Reset the flag when switching to the new market.

6. **Pending order tracking:** Track TX hashes of submitted orders. Don't place new orders while any are still pending settlement. Clean up pending orders by checking the API.

These patterns are battle-tested in the reference implementation. When in doubt, copy exactly.
