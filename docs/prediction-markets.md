# Prediction Markets and Turbine

This page explains what prediction markets are and how Turbine's markets work. If you're already familiar with prediction markets, skip to [How Turbine Works](#how-turbine-works).

## What Are Prediction Markets?

A prediction market lets you trade on the outcome of a future event. Instead of buying stocks or crypto, you're buying shares that represent your belief about what will happen.

The simplest version is a **binary market** — a yes-or-no question. For example:

> *"Will it rain tomorrow?"*

Two types of shares exist:
- **YES shares** — pay out if the answer is yes
- **NO shares** — pay out if the answer is no

Share prices reflect the market's confidence. If YES shares trade at $0.70, the market collectively believes there's about a 70% chance the answer is yes.

**The payout is always $1.00 or $0.00.** If you bought YES at $0.70 and the answer is yes, you get $1.00 back — a $0.30 profit. If the answer is no, your share is worth $0.00 and you lose your $0.70.

This is what makes prediction markets interesting: the price IS the probability, and you profit when you're more right than the market.

## How Turbine Works

Turbine runs binary prediction markets on **Bitcoin's price**. Right now, the only active market type is **BTC Quick Markets** — 15-minute questions about where BTC will be.

### The Market

Every 15 minutes, a new market opens with a question like:

> *"Will BTC be above $97,250 at 3:15 PM?"*

The dollar amount ($97,250 in this example) is the **strike price** — it's set to BTC's current price when the market opens. You're betting on whether BTC goes up or down from that point over the next 15 minutes.

### Trading

You can buy:
- **YES shares** — if you think BTC will finish above the strike
- **NO shares** — if you think BTC will finish below the strike

Share prices range from $0.01 to $0.99. The closer to $0.50, the more uncertain the market is. The closer to $0.01 or $0.99, the more confident.

### A Concrete Example

The market asks: *"Will BTC be above $97,250 at 3:15 PM?"*

You check the current BTC price and see it's at $97,400 — above the strike. You think it'll stay above, so you buy a YES share at $0.65.

**If BTC finishes above $97,250:** Your YES share pays out $1.00. You paid $0.65, so you profit $0.35 (54% return).

**If BTC drops below $97,250:** Your YES share pays out $0.00. You lose your $0.65.

The price you pay ($0.65) reflects the risk. Cheaper shares mean higher potential return but lower probability of winning.

### Resolution

After 15 minutes, the market resolves automatically:

1. The [UMA Optimistic Oracle](https://uma.xyz/) checks BTC's actual price
2. If BTC is above the strike → YES wins, NO loses
3. If BTC is below the strike → NO wins, YES loses
4. Winners claim their $1.00 per share via Turbine's gasless relayer

Then a new market opens immediately with a fresh strike price, and the cycle repeats.

### What "Gasless" Means

On most crypto platforms, every transaction costs gas fees in the chain's native token (ETH, MATIC, AVAX). This means you need multiple tokens just to start.

Turbine eliminates this completely. When you trade:

1. You sign a message with your private key (this is free — it happens off-chain)
2. Turbine's relayer submits the transaction on-chain and pays the gas for you

**You only need USDC.** No ETH, no MATIC, no AVAX. Just USDC in your wallet and you can trade.

This also applies to claiming winnings — the relayer handles that gas too.

### Fees

Turbine charges a **1% flat fee** per share. Buy a YES share at $0.60, pay a $0.006 fee. That's the only cost.

## Key Terms

| Term | What It Means |
|------|--------------|
| **Strike price** | The BTC price threshold for a market. If BTC ends above it, YES wins. Below it, NO wins. |
| **YES / NO shares** | The two sides of a binary market. Each pays out $1.00 if correct, $0.00 if not. |
| **USDC** | A stablecoin (cryptocurrency pegged to $1 USD). The only currency you need to trade on Turbine. |
| **Market rotation** | Every 15 minutes, the current market closes and a new one opens with a fresh strike price. |
| **Settlement** | The on-chain smart contract that holds USDC and executes trades. You approve it once per chain. |
| **Gasless** | Turbine's relayer pays all blockchain transaction fees. You only need USDC. |
| **Oracle** | The UMA Optimistic Oracle that checks BTC's price and resolves markets. Trustless — no single party controls outcomes. |
| **Pyth Network** | Provides real-time BTC price data. The same feed Turbine uses for resolution, which is why the Price Action strategy uses it. |

## The Weekly Competition

Turbine runs an ongoing **$100 weekly prize** for the bot with the highest percentage-based PnL. There's no limit on how many bots you can register — run multiple strategies and see which performs best.

Leaderboard: https://beta.turbinefi.com/leaderboard

## Building a Trading Bot

A trading bot automates this entire process. Instead of manually watching BTC and clicking buttons, your bot:

1. Connects to Turbine's API
2. Watches the current 15-minute BTC market
3. Decides whether to buy YES or NO (this is the **strategy** — the creative part)
4. Places orders automatically
5. Switches to new markets every 15 minutes
6. Claims winnings when markets resolve

The strategy — the "should I buy YES, NO, or hold?" decision — is where your edge comes from. Everything else is infrastructure that every bot shares. See `examples/price_action_bot.py` for a complete working example.
