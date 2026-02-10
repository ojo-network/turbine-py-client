# Examples

14 files serving different purposes. Here's what each one is and when to use it.

## Start Here

| File | What It Does |
|------|-------------|
| **[price_action_bot.py](price_action_bot.py)** | Canonical reference bot (~787 lines). Fetches live BTC price from Pyth Network, compares to strike, buys YES or NO. Handles the full lifecycle: credentials, USDC approval, trading, market rotation, claiming. **Read this first** — every other bot follows its structure. |

## More Bots

| File | What It Does |
|------|-------------|
| [market_maker.py](market_maker.py) | Spread market maker. Streams the orderbook via WebSocket, places symmetric bid/ask quotes around mid-price. |
| [ai_trading_bot.py](ai_trading_bot.py) | Uses an LLM (OpenAI or Anthropic) to analyze orderbook and trade data, then make trading decisions. Requires an API key for your chosen AI provider. |

## SDK Usage Snippets

Small scripts demonstrating individual SDK features. Good for understanding the API surface.

| File | What It Does |
|------|-------------|
| [basic_usage.py](basic_usage.py) | Read-only API calls — fetch markets, orderbook, trades. No auth required. Start here to explore the data. |
| [create_order.py](create_order.py) | Create signed orders using helper functions. Shows EIP-712 signing and price/size conversion. |
| [submit_order.py](submit_order.py) | Full authenticated order workflow: create, submit, retrieve, and cancel orders. |
| [websocket_stream.py](websocket_stream.py) | Subscribe to real-time WebSocket streams for orderbook updates, trades, and market rotations. |

## Utility Scripts

One-off scripts for managing positions and claiming winnings outside of a bot.

| File | What It Does |
|------|-------------|
| [claim_winnings.py](claim_winnings.py) | Claim winnings from a single resolved market via the gasless relayer. Takes a contract address as argument. |
| [batch_claim_winnings.py](batch_claim_winnings.py) | Claim winnings from multiple resolved markets in one batch operation. |
| [position_monitoring.py](position_monitoring.py) | Fetch your current positions and calculate P&L. |

## Testing & Stress

Load testing and integration tests. Not relevant for building a trading bot.

| File | What It Does |
|------|-------------|
| [stress_test_bot.py](stress_test_bot.py) | Places N trades simultaneously to test API concurrency. Supports multiple accounts. |
| [setup_stress_test_accounts.py](setup_stress_test_accounts.py) | Generates test accounts and funds them with testnet USDC via faucet. |
| [test_order_integration.py](test_order_integration.py) | Integration test for API credential registration via wallet signature. |
| [full_order_lifecycle.py](full_order_lifecycle.py) | End-to-end test: place order → cancel → fill → sell position. |
