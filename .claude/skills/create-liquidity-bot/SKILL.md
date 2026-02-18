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
> **The risk:** If BTC moves sharply in one direction, you might accumulate a large one-sided position (lots of YES shares, not enough NO shares). This is called **inventory risk**. Your bot manages this automatically with inventory tracking and quote skewing.

**Do not proceed until they confirm they understand.** Use `AskUserQuestion`:
- **"Does this make sense? Ready to configure your market maker?"**
- Options: "Yes, let's go" / "I'd like to understand more first"

If they want more info, answer their questions. Reference the maker rebates docs at https://beta.turbinefi.com/docs/maker-rebates.

### For users who know the basics:

> We're building a smart market maker for Turbine's 15-min BTC/ETH/SOL binary markets. It uses a statistical probability model (normal CDF) with Pyth price feeds — correctly handles time decay, momentum, and volatility. Built-in inventory tracking, adverse selection detection, one-sided quoting, and circuit breaker. Plus maker rebates — up to 1.56% fee rate on fills near 50¢. Let's configure it.

### For experienced market makers:

> Turbine MM bot — P(YES) = Φ(deviation / (vol × √timeRemaining)) from Pyth feeds. Rolling price tracker with velocity/volatility/momentum signals. Inventory skew, adverse selection circuit breaker, one-sided quoting when target deviates >15% from 50%. Graceful rebalance (place-before-cancel). Maker rebate: `fee_rate = 0.25 × (p(1-p))²`, daily pro-rata. Let's set parameters.

---

## Step 2: Choose a Market Making Style

If the user passed an argument (e.g., `/create-liquidity-bot simple`), use `$ARGUMENTS` to skip directly to that style.

Otherwise, ask what they're looking for. Use `AskUserQuestion`:

**"What kind of market making approach interests you?"**

Options:
- "Recommend the best approach" → Smart MM (see below)
- "I want something simple to start" → Simple Spread
- "Show me all the options" → Present the table below

### Market Making Styles

All styles place orders on both sides of the book. They differ in how they price and manage risk.

| # | Style | How It Prices | Risk Management | Best For | Complexity |
|---|-------|--------------|-----------------|----------|------------|
| 1 | **Smart MM** (recommended) | Statistical model: P(YES) = Φ(deviation / (vol × √time)). Uses Pyth price vs strike with momentum and volatility signals. | Inventory tracking, adverse selection circuit breaker, one-sided quoting, end-of-market order pulling | Most users. State-of-the-art pricing aligned with market resolution. | Medium |
| 2 | **Simple Spread** | Fixed spread around orderbook mid-price. No external price feed. | Position limits only | Learning MM basics. Quick start. | Low |

**Why Smart MM is recommended:** It uses a proper statistical model to compute probabilities — the same Pyth oracle Turbine uses for resolution, run through a normal CDF that correctly handles how time remaining affects certainty. A +0.5% BTC move with 1 minute left is near-certain YES; the same move with 7 minutes left is only mildly bullish. The bot also tracks momentum (leads price moves), manages inventory (skews quotes to reduce exposure), detects adverse selection (trips a circuit breaker if getting picked off), and automatically kills the losing side when the market is trending strongly. All of this is built into the reference implementation.

> **For beginners:** Recommend Smart MM and explain: "This is the battle-tested approach — your bot watches BTC price, computes the statistical probability of the outcome, and adapts its spread and quoting based on market conditions. It handles risk management automatically." Only show the full table if they ask.

> **For experienced MMs:** They may want to customize heavily. Smart MM is the best starting point — all the microstructure features are there to build on.

Use `AskUserQuestion` to confirm their choice.

---

## Step 3: Configure Parameters

Walk the user through the key parameters for their chosen style. These directly control risk and profitability.

### Smart MM Parameters (Style 1, recommended)

**IMPORTANT — use these defaults. They're conservative on purpose:**

| Flag | Default | What It Does |
|------|---------|-------------|
| `--allocation` | **$60** | Total USDC per asset, split across all sides and levels. With one-sided quoting, allocation concentrates on the active side. |
| `--spread` | **0.012** (1.2%) | Base spread around target probability. Dynamically widens on high volatility or strong momentum. |
| `--levels` | **6** | Price levels per side (geometric distribution concentrates at best price). |
| `--base-vol` | **0.03** (3%) | Base daily volatility for the probability model. Higher = slower probability movement. |
| `--asset-vol` | *(optional)* | Per-asset volatility overrides, e.g. `--asset-vol BTC=0.025 ETH=0.035 SOL=0.05` |
| `--assets` | **BTC,ETH,SOL** | Which assets to trade. Can specify a subset. |

Tell the user: "I've set proven defaults — $60 allocation with a 1.2% base spread. This is real USDC. Start by watching how it behaves, then adjust once you're comfortable."

> **For beginners**, explain what each parameter means:
> - "**Allocation** is the total USDC your bot uses per asset. The bot intelligently allocates more capital to the likely-winning side."
> - "**Spread** is the base gap between your buy and sell prices. It automatically widens when the market is volatile or momentum is strong, and widens further in the last 90 seconds of each market."
> - "**Base volatility** controls how quickly the probability model reacts. BTC with 3% daily vol means a 0.1% move in 15 minutes shifts probability moderately. Lower vol = more responsive. Higher vol = more stable."
> - "**Levels** is how many price points you quote per side. 6 levels with geometric distribution means most of your capital is at the best price."

#### Built-in Smart Features (no configuration needed)

These are automatic — explain them so users understand what the bot is doing:

- **One-sided quoting:** When YES probability deviates >15% from 50%, the bot stops quoting the losing side entirely. Avoids getting picked off in directional moves.
- **Inventory tracking:** After fills, the bot skews quotes to reduce net exposure. Long YES → widen YES bids, tighten YES asks.
- **Adverse selection circuit breaker:** If one side gets filled disproportionately in 30 seconds, the bot pulls all orders and pauses for 10 seconds.
- **End-of-market safety:** Orders pulled entirely in the last 30 seconds (too risky). Spread widens in the last 90 seconds.
- **Smart fill replacement:** When orders get filled, replacements go in at the CURRENT fair value — not the old fill price.
- **Graceful rebalance:** New orders placed BEFORE old ones are cancelled, so there's no gap in liquidity.
- **Momentum tracking:** EMA-smoothed velocity signal shifts probability in the direction of price movement.

### Simple Spread Parameters (Style 2)

- `--spread` — **0.04** (4% for simple spread — wider because no price intelligence)
- `--allocation` — **$10** (conservative for a simpler strategy)
- No volatility model or smart features — fixed spread around orderbook mid-price

---

## Step 4: Generate the Bot

### Reference implementation

**`examples/market_maker.py`** is the reference for ALL market making styles. It's a complete, production-ready smart market maker that handles everything described above.

**CRITICAL: Always read `examples/market_maker.py` before generating.** Do not use inline code snippets from this skill as the basis for generated code. The reference file contains tested, battle-hardened patterns.

### What changes between styles

1. **Smart MM (Style 1, recommended):** The reference IS the Smart MM. Copy it with the user's chosen parameters. Adjust defaults at the top of the file to match their choices.

2. **Simple Spread (Style 2):** Significantly simplify the reference:
   - Remove `PriceTracker`, `InventoryTracker`, and the statistical model
   - Replace `calculate_smart_prices()` with a simple midpoint + fixed spread
   - Remove Pyth price fetching — use orderbook midpoint instead
   - Remove circuit breaker, one-sided quoting, and momentum logic
   - Keep: multi-level geometric distribution, market transitions, gasless approval, claiming

### Generation approach

1. Read `examples/market_maker.py` for the full infrastructure
2. Copy the entire file as the base
3. Modify ONLY the parts specific to the chosen style (see above)
4. Update the docstring to describe the user's specific configuration
5. Update default parameter values to match user's choices

### File naming and location

Save the generated bot in the **repo root** with a descriptive name:
- `market_maker_bot.py` (smart MM)
- `simple_spread_bot.py` (simple spread)

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
> This is why market making on Turbine is attractive — you earn from spread AND rebates. The smart MM's statistical pricing naturally places orders near fair value, which tends to be near 50¢ early in each market.
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

With custom parameters:
```bash
python market_maker_bot.py --allocation 50 --spread 0.012 --assets BTC,ETH --asset-vol BTC=0.025 ETH=0.035
```

> **For non-technical users:** Be explicit:
> - "Open a new terminal window (separate from this one). Navigate to the project folder:"
>   ```
>   cd [path to repo]
>   source .venv/bin/activate
>   python market_maker_bot.py
>   ```
> - "You'll see text scrolling — that's your bot quoting prices and tracking fills."
> - "To stop the bot, press `Ctrl+C`. The bot cancels all open orders on shutdown."

Explain what will happen on first run:
1. **API credentials auto-register** — signs a message, gets API keys, saves to `.env`
2. **USDC approval** — gasless max permit for the settlement contract (one-time)
3. **Market connection** — fetches the current markets for each asset and their strike prices
4. **Initial quotes** — places multi-level bid/ask orders with smart allocation
5. **Fast price polling** — checks prices every 2 seconds via Pyth, updates probability model
6. **Smart rebalance** — when target probability shifts >2%, gracefully replaces orders (new first, then cancel old)
7. **Fill detection** — detects fills, records inventory, replaces at current fair value
8. **Market rotation** — every 15 minutes, resets state and quotes the new market
9. **Claiming** — automatically claims winnings from resolved markets

> **What the output means:**
> - `[BTC] Quoting: YES 62% / NO 38% | Spread 1.5% | Sides 4/4 | Alloc YES[B=$12 S=$18] NO[B=$18 S=$12]` — smart allocation based on probability
> - `[BTC] REBALANCE: $97,450 (+0.15%) | YES 55% → 62% | Spread 1.5% | Inv 0.12 | 420s left` — probability shifted, graceful requote
> - `[BTC] ONE-SIDED: YES=0.72 — skipping NO orders (trending UP)` — strong trend, killing losing side
> - `[BTC] FILL: BUY YES @ 0.5800 (size: 10.00)` — order filled, inventory updated
> - `[BTC] ADVERSE SELECTION detected — circuit breaker for 10s` — protective pause
> - `[BTC] PULLING all orders (25s remaining — too risky)` — end-of-market safety
> - `[BTC] 💰 Claimed winnings from abc123... TX: 0x...` — won on a resolved market

---

## Step 7: What's Next

After the bot is running, suggest next steps based on the user's goals:

**For competition/leaderboard users:**
> Market makers can climb the leaderboard through consistent volume and PnL. Check https://beta.turbinefi.com/leaderboard. The smart MM's statistical model gives you an edge — experiment with tighter spreads and per-asset volatility tuning.

**For hackathon users:**
> You've got a production-grade MM bot! Consider customizing the volatility parameters for each asset, adjusting the one-side threshold, or adding your own signal on top of the statistical model. Deploy to Railway with `/railway-deploy` so it runs 24/7.

**For explorers:**
> Watch the logs to see how the bot adapts. Key things to experiment with:
> - `--spread` — tighter = more fills + rebates, but more risk
> - `--base-vol` — lower = more reactive to price moves, higher = more stable
> - `--asset-vol` — tune per asset (SOL is more volatile than BTC)
> - Watch the one-sided quoting and circuit breaker in action during volatile periods

**For everyone:**
> - **Deploy 24/7** — run `/railway-deploy` to keep your bot running in the cloud
> - **Try a directional bot** — run `/create-bot` to build a strategy that bets on outcomes
> - **Read the code** — `examples/market_maker.py` shows all the smart features
> - **Check your rebates** — visit https://beta.turbinefi.com/docs/maker-rebates
> - **Explore liquidity rewards** — https://beta.turbinefi.com/docs/liquidity-rewards

**Update `user-context.md`** with a note about which bot was created (style, filename, parameters) under a `## Bots Created` section.

---

## Critical Infrastructure Patterns

**DO NOT modify these when generating bots.** They exist in `examples/market_maker.py` for a reason and must be preserved exactly:

1. **Gasless USDC + CTF approval:** Dynamic per-market settlement address from the API (not hardcoded). One-time max EIP-2612 permit for USDC + setApprovalForAll for CTF per settlement contract. Handled in `ensure_settlement_approved()` when entering each market. Never do per-order approvals or use chain config defaults.

2. **Graceful rebalance:** Place new orders FIRST, brief pause, then cancel old ones. This ensures continuous liquidity — no gap where traders can't trade. This is critical and different from cancel-then-place.

3. **Market transitions:** Poll every 5 seconds for new markets. On transition: clear order tracking (expired orders auto-removed by API), reset all smart state (price tracker, inventory, circuit breaker), approve USDC for new settlement if needed, place initial quotes.

4. **Rebalance threshold:** Only refresh quotes when YES target probability shifts by >2%. Minimum 2 seconds between rebalances. Force rebalance on volatility spikes.

5. **Geometric distribution:** Concentrate liquidity at the best price (tightest level). Use `lambda^i` for bids and `lambda^(n-1-i)` for asks. This ensures most capital is at the most competitive price.

6. **Claiming:** Background task checks resolved markets every 120 seconds. 15-second delay between claims.

7. **Fast polling:** 2-second price checks drive the statistical model. Price tracker maintains a rolling window with velocity, volatility, and momentum. This is what makes the model accurate.

8. **Order expiration:** 5-minute expiration on all orders — safety net if the bot crashes.

9. **End-of-market:** Pull ALL orders in last 30 seconds. Widen spread in last 90 seconds. These prevent losses from resolution-time volatility.

10. **Smart fill replacement:** Replace filled orders at CURRENT fair value, not the old fill price. This is the single most important edge vs naive market makers.

These patterns are battle-tested. When in doubt, copy exactly from `examples/market_maker.py`.
