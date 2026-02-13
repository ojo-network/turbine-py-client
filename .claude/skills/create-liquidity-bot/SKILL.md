---
name: create-liquidity-bot
description: Generate a Turbine liquidity-providing market maker bot. Earn from spread + maker rebates. Use after /setup.
argument-hint: "[style]"
---

# Create a Turbine Liquidity Bot (Market Maker)

Here's what you're helping the user build: **a Python file that provides liquidity on Turbine's Bitcoin prediction markets by quoting both sides of the order book.**

Unlike directional trading bots that bet on outcomes, a **market maker** (MM) places both buy and sell orders — offering to trade with anyone. The MM earns from the **spread** (the gap between its buy and sell prices) and from **maker rebates** (Turbine rewards resting orders that get filled).

> **Good news for market makers:** Turbine enforces a $1 minimum on taker orders, but **maker orders are exempt**. Since MM bots place resting (maker) orders, they can use any order size — including the small sizes typical of multi-level quoting strategies.

Every 15 minutes, Turbine opens a new market asking "Will BTC be above $X at [time]?" The user's MM bot quotes both YES and NO outcomes with multi-level bid/ask ladders, dynamically adjusting prices based on the live BTC price from Pyth Network. When someone trades against the MM's resting orders, the MM collects the spread — and earns rebates on top.

**A liquidity bot is a single Python file.** When you run `python my_mm_bot.py`, it connects to Turbine, starts quoting the current BTC market on both sides, and manages its orders automatically — refreshing quotes as prices move, handling market rotation every 15 minutes, approving USDC gaslessly, and claiming winnings.

The creative core is the **pricing strategy** — how the bot sets its target probability, spread width, and how it manages inventory risk. Everything else follows a standard pattern from `examples/market_maker.py`.

### Key URLs

- **Platform:** https://beta.turbinefi.com
- **Leaderboard:** https://beta.turbinefi.com/leaderboard
- **Maker Rebates:** https://beta.turbinefi.com/docs/maker-rebates
- **Liquidity Rewards:** https://beta.turbinefi.com/docs/liquidity-rewards
- **Build a Trading Bot:** https://beta.turbinefi.com/docs/api/build-a-trading-bot
- **API Reference:** https://beta.turbinefi.com/docs/api
- **API Host:** https://api.turbinefi.com

---

## Step 0: Understand Who You're Helping

### Check for existing user context

First, check if `user-context.md` exists in the repo root. This file is created by the `/setup` skill and contains the user's technical level, PM familiarity, and goals.

```bash
test -f user-context.md && echo "USER_CONTEXT_EXISTS" || echo "NO_USER_CONTEXT"
```

**If it exists**, read it. You now know their technical level, PM familiarity, what they're here for, and their chain/wallet. Adapt accordingly — don't re-ask what you already know.

**If it doesn't exist**, ask directly using `AskUserQuestion` with **two questions**:

1. **"How comfortable are you with Python?"**
   - Options: "I'm new to Python" / "I've written some Python" / "I'm a developer"

2. **"How familiar are you with prediction markets and market making?"**
   - Options: "I'm not sure how they work" / "I understand the basics" / "I've done market making before"

### Quick setup check

Verify the user's environment is ready. Run silently:

```bash
# Check for .env with private key
test -f .env && grep -q "TURBINE_PRIVATE_KEY=0x" .env && echo "ENV_OK" || echo "NO_ENV"

# Check SDK is importable
python3 -c "import turbine_client" 2>&1 && echo "SDK_OK" || echo "NO_SDK"
```

**If either check fails**, tell the user:

> "Looks like your environment isn't set up yet. Run `/setup` first — it'll walk you through Python, wallet, and credentials. Come back here when you're ready to build."

Then **stop**. Don't continue.

**If both pass**, proceed.

---

## Step 1: Set the Context — What Is Market Making?

Before jumping into configuration, make sure the user understands what a market maker does. This is crucial — MM is fundamentally different from directional trading.

**Adapt depth based on user profile:**

### For users new to market making:

> **Here's what we're building:** A bot that *provides liquidity* on Turbine's Bitcoin prediction markets — instead of betting on one side, it offers to trade on *both* sides and earns from the difference.
>
> **How it works:** Every 15 minutes, a market opens: "Will BTC be above $97,250 at 3:15 PM?" Your bot places orders on both sides:
> - **Bid:** "I'll buy YES shares at 48¢" (and simultaneously "I'll buy NO shares at 48¢")
> - **Ask:** "I'll sell YES shares at 52¢" (and simultaneously "I'll sell NO shares at 52¢")
>
> That 4¢ gap is the **spread**. When someone buys from your ask at 52¢ and later someone sells to your bid at 48¢, you pocket the 4¢ difference — regardless of whether BTC goes up or down.
>
> **Concrete example:** Your bot quotes YES shares with a bid at 48¢ and ask at 52¢. A trader buys 100 YES shares from you at 52¢ ($52 total). Later another trader sells you 100 YES shares at 48¢ ($48 total). You made $4 from the spread — and you don't care whether BTC went up or down.
>
> **The bonus — Maker Rebates:** Turbine rewards liquidity providers through a **maker rebate program**. When your resting orders get filled, you earn rebates from a pool funded by virtual taker fees. The rebate formula is `fee_rate = 0.25 × (p × (1 - p))²` where `p` is the fill price — rebates peak at 50¢ (1.56% fee rate) and drop at extremes. Rebates are distributed daily based on your share of total maker volume. This means you earn from spread **plus** rebates.
>
> **The risk:** If BTC moves sharply in one direction, you might accumulate a large one-sided position (lots of YES shares, not enough NO shares). This is called **inventory risk**. Your bot manages this with position limits and probability-based pricing.

**Do not proceed until they confirm they understand.** Use `AskUserQuestion`:
- **"Does this make sense? Ready to configure your market maker?"**
- Options: "Yes, let's go" / "I'd like to understand more first"

If they want more info, answer their questions. Reference the maker rebates docs at https://beta.turbinefi.com/docs/maker-rebates.

### For users who know the basics:

> We're building a probability-based market maker for Turbine's 15-min BTC binary markets. It quotes multi-level bid/ask ladders on both YES and NO outcomes using Pyth price feeds, with dynamic spread and time-decay sensitivity. Plus you earn maker rebates — up to 1.56% fee rate on fills near 50¢. Let's configure it.

### For experienced market makers:

> Turbine MM bot — probability-based pricing from Pyth BTC/USD, geometric multi-level ladders, time-decay sensitivity, rebalance-on-threshold. Maker rebate program: `fee_rate = 0.25 × (p(1-p))²`, daily distribution pro-rata by maker volume. Let's set your parameters.

---

## Step 2: Choose a Market Making Style

If the user passed an argument (e.g., `/create-liquidity-bot inventory-aware`), use `$ARGUMENTS` to skip directly to that style.

Otherwise, ask what they're looking for. Use `AskUserQuestion`:

**"What kind of market making approach interests you?"**

Options:
- "Recommend the best approach" → Probability-Based (see below)
- "I want something simple to start" → Simple Spread
- "Show me all the options" → Present the table below

### Market Making Styles

All styles place orders on both sides of the book. They differ in how they price and manage risk.

| # | Style | How It Prices | Risk Management | Best For | Complexity |
|---|-------|--------------|-----------------|----------|------------|
| 1 | **Probability-Based** (recommended) | Uses Pyth BTC price vs strike to compute target probability. Spread tightens and sensitivity increases toward expiration. | Position limits, time-decay, rebalance threshold | Most users. Aligns pricing with market resolution. | Medium |
| 2 | **Simple Spread** | Fixed spread around orderbook mid-price. No external price feed. | Position limits only | Learning MM basics. Quick start. | Low |
| 3 | **Inventory-Aware** | Like Probability-Based, but skews quotes to reduce accumulated position. Widens on the side where you're overexposed. | Active inventory management + position limits | Extended running, lower risk | Higher |

**Why Probability-Based is recommended:** It uses the same Pyth BTC oracle that Turbine uses for resolution — so your pricing is directly aligned with the market's ground truth. It dynamically adjusts as BTC price moves and as expiration approaches, giving you tighter quotes (more fills, more rebates) when the market outcome becomes clearer.

> **For beginners:** Recommend Probability-Based and explain: "This is the standard approach — your bot watches the real BTC price and uses it to decide where to place orders. It's smarter than a fixed spread because it adapts as BTC moves." Only show the full table if they ask.

> **For experienced MMs:** They may want to customize heavily. Probability-Based is the best starting point — they can add inventory skew, custom sensitivity curves, or their own pricing model on top.

Use `AskUserQuestion` to confirm their choice.

---

## Step 3: Configure Parameters

Walk the user through the key parameters for their chosen style. These directly control risk and profitability.

### Universal MM Parameters

**IMPORTANT — use these defaults. They're conservative on purpose:**

- `--allocation` — **$10.00** total USDC split across all sides and levels ($2.50 per side: YES-bid, YES-ask, NO-bid, NO-ask)
- `--spread` — **0.02** (2% base spread around target probability)
- `--levels` — **6** price levels per side (geometric distribution concentrates at best price)

Tell the user: "I've set conservative defaults — $10 total allocation with a 2% spread. This is real USDC. Start by watching how it behaves, then adjust once you're comfortable."

> **For beginners**, explain what each parameter means:
> - "**Allocation** is the total USDC your bot splits across all its orders. With $10, each of the 4 sides (YES-bid, YES-ask, NO-bid, NO-ask) gets $2.50."
> - "**Spread** is the gap between your buy and sell prices. A 2% spread means if the fair price is 50¢, you bid at 49¢ and ask at 51¢. Wider spread = safer but fewer fills. Tighter = more fills and rebates but more risk."
> - "**Levels** is how many price points you quote per side. 6 levels means 6 different prices on the bid side and 6 on the ask side, with most size concentrated at the best price."

### Probability-Based Parameters (Style 1, recommended)

- `--sensitivity` — **1.5** probability shift per 1% BTC price deviation from strike
  - Higher = more aggressive price movement, follows BTC more closely
  - Lower = more conservative, stays closer to 50/50
- Rebalance threshold: **2%** — only refreshes quotes when target probability shifts by >2%
- Time decay: sensitivity multiplies by **2.5x** at expiration, spread tightens to **0.5%** minimum
  - "As expiration approaches, your bot gets more confident and quotes tighter — more fills, more rebates."

### Simple Spread Parameters (Style 2)

- `--spread` — **0.04** (4% for simple spread — wider because no price intelligence)
- No sensitivity or time decay — fixed spread around orderbook mid-price

### Inventory-Aware Parameters (Style 3)

- All Probability-Based parameters, PLUS:
- `--skew-factor` — **0.01** per share of inventory imbalance
  - "If you've accumulated 100 YES shares, the bot widens your YES bid by 1¢ and tightens your YES ask by 1¢ — discouraging more YES buying and encouraging selling."
- `--max-position` — **$5.00** maximum position in any single outcome before the bot stops quoting that side

> **For non-technical users:** Don't overwhelm with all parameters. Set sensible defaults and say: "I've configured everything with safe defaults. You can tweak these later once you see how the bot performs."

---

## Step 4: Generate the Bot

### Reference implementation

**`examples/market_maker.py`** is the reference for ALL market making styles. It's a complete, production-ready bot that handles:
- Probability-based dynamic pricing from Pyth BTC price
- Multi-level quoting with geometric size distribution
- Time-decay sensitivity and spread tightening toward expiration
- Cancel-then-place order refresh to avoid self-trade issues
- Gasless USDC approval (one-time max permit per settlement)
- Automatic market transition when 15-minute markets rotate
- Automatic claiming of winnings from resolved markets
- WebSocket for real-time trade notifications

**CRITICAL: Always read `examples/market_maker.py` before generating.** Do not use inline code snippets from this skill as the basis for generated code. The reference file contains tested, battle-hardened patterns.

### What changes between styles

1. **Simple Spread (Style 2):** Simplify `calculate_target_prices_with_time()` to just use orderbook mid-price instead of Pyth. Remove Pyth price fetching. Keep everything else identical.

2. **Probability-Based (Style 1):** The reference IS a probability-based MM. Copy it with the user's chosen parameters.

3. **Inventory-Aware (Style 3):** Start from the reference, then add:
   - Position tracking via `client.get_user_positions(address)` in the main loop
   - Quote skew in `place_multi_level_quotes()`: adjust bid/ask prices based on current inventory
   - Position limit check: stop quoting one side if max position exceeded
   - Add `--skew-factor` and `--max-position` CLI parameters

### Generation approach

1. Read `examples/market_maker.py` for the full infrastructure
2. Copy the entire file as the base
3. Modify ONLY the parts specific to the chosen style (see above)
4. Update the docstring to describe the user's specific configuration
5. Update default parameter values to match user's choices

### File naming and location

Save the generated bot in the **repo root** with a descriptive name:
- `liquidity_bot.py` (probability-based)
- `simple_spread_bot.py` (simple spread)
- `inventory_mm_bot.py` (inventory-aware)

Tell the user where you saved it.

---

## Step 5: Explain the Maker Rebate Opportunity

After generating the bot, highlight the maker rebate program — this is a key incentive for running an MM bot.

> **💰 Maker Rebates — Why Market Making Pays Extra**
>
> Turbine runs a maker rebate program that rewards liquidity providers. Here's how it works:
>
> When your resting orders get filled by takers, a virtual fee is calculated on the taker side:
> `fee_rate = 0.25 × (p × (1 - p))²` where `p` is the fill price.
>
> - At **50¢** (most uncertain): **1.56%** fee rate — maximum rebates
> - At **25¢ or 75¢**: 0.88% fee rate
> - At **10¢ or 90¢**: 0.20% fee rate — minimal rebates
>
> These fees fund a daily rebate pool distributed to makers proportional to their share of total maker fill volume. **The closer your fills are to 50¢, the more rebates you earn.**
>
> This is why market making on Turbine is attractive — you earn from spread AND rebates. Your bot's probability-based pricing naturally places orders near fair value, which tends to be near 50¢ early in each market.
>
> Track the leaderboard at https://beta.turbinefi.com/leaderboard and learn more about rebates at https://beta.turbinefi.com/docs/maker-rebates.

> **For beginners:** Simplify: "Turbine pays you extra just for providing liquidity. On top of the spread you earn, you get daily rebates based on how much your orders get filled. It's like getting paid to help the market work."

> **For experts:** They may want the exact formula and optimization strategies. Point them to the docs and note that fills near 50¢ maximize rebate capture, so tighter spreads at market open (when prices hover near 50¢) can be highly profitable.

---

## Step 6: Run It

Give the user the command to run their bot themselves. **Do NOT offer to run the bot for them.**

```bash
source .venv/bin/activate    # If not already active
python <bot_filename>.py
```

> **For non-technical users:** Be explicit:
> - "Open a new terminal window (separate from this one). Navigate to the project folder:"
>   ```
>   cd [path to repo]
>   source .venv/bin/activate
>   python liquidity_bot.py
>   ```
> - "You'll see text scrolling — that's your bot quoting prices and tracking fills."
> - "To stop the bot, press `Ctrl+C`. The bot cancels all open orders on shutdown."

Explain what will happen on first run:
1. **API credentials auto-register** — signs a message, gets API keys, saves to `.env`
2. **USDC approval** — gasless max permit for the settlement contract (one-time)
3. **Market connection** — fetches the current BTC market and its strike price
4. **Initial quotes** — places multi-level bid/ask orders on both YES and NO outcomes
5. **Price monitoring** — checks BTC price every 10 seconds, rebalances if target shifts >2%
6. **Market rotation** — every 15 minutes, cancels old orders and quotes the new market
7. **Claiming** — automatically claims winnings from resolved markets

> **What the output means:**
> - `Quoting 6 levels x 2 outcomes: YES 62.0% / NO 38.0% | Spread 1.8% | $2.50/side` — your bot placed orders
> - `Rebalance: BTC $97,450 (+0.15% from $97,300) | YES 55% -> 62%` — BTC moved, bot is re-quoting
> - `-> Our fill: 10.00 YES @ 61.00%` — someone traded against your resting order (you earned spread + rebates!)
> - `Claimed winnings from abc123... TX: 0x...` — won on a resolved market

---

## Step 7: What's Next

After the bot is running, suggest next steps based on the user's goals:

**For competition/leaderboard users:**
> Market makers can climb the leaderboard through consistent volume and PnL. Check https://beta.turbinefi.com/leaderboard. Tighter spreads = more fills = more rebates, but watch your inventory risk.

**For hackathon users:**
> You've got a working MM bot! Consider adding inventory management, custom pricing curves, or multi-market support. Deploy to Railway with `/railway-deploy` so it runs 24/7.

**For explorers:**
> Watch the logs to see how your bot prices and rebalances. Try adjusting the spread (tighter = more fills, riskier) or sensitivity (higher = more reactive to BTC moves). Each parameter change is a new experiment.

**For everyone:**
> - **Deploy 24/7** — run `/railway-deploy` to keep your bot running in the cloud
> - **Try a directional bot** — run `/create-bot` to build a strategy that bets on outcomes instead of providing liquidity
> - **Read the code** — `examples/market_maker.py` shows exactly what your bot does under the hood
> - **Check your rebates** — visit https://beta.turbinefi.com/docs/maker-rebates for details on the daily rebate distribution
> - **Explore liquidity rewards** — https://beta.turbinefi.com/docs/liquidity-rewards for additional incentive programs

**Update `user-context.md`** with a note about which bot was created (MM style, filename, parameters) under a `## Bots Created` section.

---

## Critical Infrastructure Patterns

**DO NOT modify these when generating bots.** They exist in `examples/market_maker.py` for a reason and must be preserved exactly:

1. **Gasless USDC approval:** One-time max EIP-2612 permit per settlement contract. Check allowance first, skip if already approved. Never do per-order approvals.

2. **Cancel-then-place:** Always cancel existing orders before placing new ones. This avoids self-trade issues where your own bid and ask would fill against each other.

3. **Market transitions:** Poll every 5 seconds for new markets. On transition: clear order tracking (expired orders are auto-removed by API), reset pricing state, approve USDC for new settlement if needed, place initial quotes.

4. **Rebalance threshold:** Only refresh quotes when the YES target probability shifts by >2%. This avoids excessive order churn and API rate limits. Minimum 5 seconds between rebalances.

5. **Geometric distribution:** Concentrate liquidity at the best price (tightest level). Use `lambda^i` for bids and `lambda^(n-1-i)` for asks. This ensures most of your capital is at the most competitive price.

6. **Claiming:** Background task checks for resolved markets every 120 seconds. 15-second delay between individual claim calls (API rate limit).

7. **WebSocket + polling hybrid:** WebSocket provides real-time trade notifications. Periodic price polling (every 10s) from Pyth drives requoting decisions. Don't rely solely on either.

8. **Order expiration:** Set 5-minute expiration on all orders. This provides a safety net — if the bot crashes, orders auto-expire rather than sitting stale.

These patterns are battle-tested. When in doubt, copy exactly from `examples/market_maker.py`.
