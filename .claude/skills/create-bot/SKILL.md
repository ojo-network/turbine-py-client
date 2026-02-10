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

- **New to PMs:** Give the full explanation above, PLUS walk through a concrete example with real dollar amounts:
  > "Here's a specific example: the market asks 'Will BTC be above $97,250 at 3:15 PM?' Your bot checks the live BTC price and sees it's at $97,400 — above the strike. So it buys a YES share at $0.65. If BTC stays above $97,250 by 3:15, the share pays out $1.00 — that's a $0.35 profit. If BTC drops below, the share is worth $0.00 and you lose the $0.65."
  >
  > "The **strategy** is the part that decides *when* to buy and *which side* to take. That's what we're about to pick."

  **Do not proceed to strategy selection until they confirm they understand this.** A user who doesn't grasp the payout mechanic can't evaluate whether a strategy makes sense. If they seem uncertain, reference `docs/prediction-markets.md` for a fuller explanation.

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

> **For users new to PMs:** The algorithm table above is meaningless without PM context. Don't just show the table — translate each strategy into plain English tied to what they now understand:
> - **Price Action:** "Checks the live BTC price. If BTC is above the strike, buy YES. If below, buy NO. The simplest possible logic."
> - **Momentum:** "Watches what other traders are doing. If lots of people are buying YES, follow the crowd."
> - **Mean Reversion:** "If the price spikes in one direction, bet it comes back. Contrarian approach."
>
> For beginners, **strongly recommend Price Action** and don't overwhelm them with all 6 options. Say: "I'd recommend starting with Price Action — it's the most intuitive and directly aligned with how markets resolve. You can always create another bot with a different strategy later."

> **For users new to technical concepts (low tech):** They can't evaluate algorithmic tradeoffs. Don't ask them to choose from a table of options they can't meaningfully compare. Instead, recommend Price Action directly and explain it in one sentence: "Your bot will check if Bitcoin is above or below the target price and trade accordingly." Only present the full table if they ask for options.

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

Check the user's chain from `user-context.md` or `.env` (`CHAIN_ID`) to determine defaults:

**Base Sepolia (testnet, chain 84532):**
- `--order-size` — default: $1.00
- `--max-position` — default: $10.00
- It's fake money, so larger defaults are fine. The user gets to see more action and the bot behaves more realistically with meaningful amounts.
- Tell them: "These are test dollars — not real money. I've set the sizes larger so you can see the bot actively trading."

**Polygon or Avalanche (mainnet, chains 137/43114):**
- `--order-size` — default: $0.10
- `--max-position` — default: $1.00
- Real money. Keep defaults tiny. The user can always increase once they see the bot working and understand the risk.
- Tell them: "I've set these small on purpose — this is real USDC. Start by watching how your bot behaves, then increase the amounts once you're comfortable."

> **For users new to PMs:** Explain what these numbers mean in context:
> - "**Order size** is how much you bet each time. Your bot spends this amount per trade. If the trade wins, you get back more. If it loses, you lose the order size."
> - "**Max position** is the most your bot can have on the line at once. Even if the bot places many trades, it won't risk more than this amount total in any single market."

**Algorithm-specific parameters:**
- Spread bots: spread width (BPS)
- Momentum: lookback window, threshold
- Mean Reversion: reversion threshold, lookback trades
- Probability-Weighted: edge threshold (distance from 50%)

> **For non-technical users:** Don't present algorithm-specific parameters unless they ask. Use sensible defaults and move on. Say: "I've set the defaults to reasonable values. You can tweak them later once you see how the bot performs."

---

## Step 5: Run It

Give the user the command to run their bot themselves. **Do NOT offer to run the bot for them** — the user should see the output live in their own terminal. This is the payoff moment.

```bash
source .venv/bin/activate    # If not already active
python <bot_filename>.py
```

> **For non-technical users:** Running a Python file may not be obvious. Be explicit:
> - "To run the bot, you'll need a separate terminal window from this one (this one is for Claude). Open a new terminal window, then navigate to the project folder:"
>   ```
>   cd [path to repo]
>   source .venv/bin/activate
>   python price_action_bot.py
>   ```
> - "Make sure you see `(.venv)` at the start of your prompt — that means the virtual environment is active."
> - "You'll see text scrolling — that's your bot thinking and trading. Don't close this window or the bot stops."
> - "To stop the bot, press `Ctrl+C` (hold Control and press C)."
> - "You can come back to this Claude window anytime to ask questions about what's happening."
>
> If they're in an IDE with an integrated terminal, this is simpler: "Open a new terminal tab in your IDE (usually the + button next to the terminal) and run the command there."

Explain what will happen on first run:
1. **API credentials auto-register** — the bot signs a message with the wallet, gets API keys, and saves them to `.env`. This takes a few seconds on the very first run.
2. **USDC approval** — the bot signs a gasless permit to allow trading. One-time per chain.
3. **Trading begins** — the bot fetches the current BTC market, runs its algorithm, and places trades.
4. **Market rotation** — every 15 minutes, the market rotates. The bot detects this automatically, cancels old orders, and switches to the new market.
5. **Claiming** — when past markets resolve, the bot automatically claims any winnings via the gasless relayer.

> **For non-technical users:** Also explain what the output means as it scrolls by: "The first few lines are setup — registering credentials and approving USDC. After that, you'll see lines about the current market, the BTC price, and what your bot decided to do. If you see 'BUY_YES' or 'BUY_NO', your bot is actively trading."

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
