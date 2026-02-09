# Turbine Python SDK

Trade on [Turbine](https://beta.turbinefi.com) prediction markets from Python. Binary BTC/ETH markets with 15-minute resolution, CLOB orderbook, gasless execution on Polygon & Avalanche.

```bash
pip install turbine-py-client
```

> **Import name:** `from turbine_client import TurbineClient` (underscore, not hyphen)

## 30-Second Quickstart

### Read market data (no credentials)

```python
from turbine_client import TurbineClient

client = TurbineClient()  # defaults to Polygon mainnet
qm = client.get_quick_market("BTC")
print(f"BTC strike: ${qm.start_price / 1e6:,.2f}")

book = client.get_orderbook(qm.market_id)
print(f"Best bid: {book.bids[0].price / 1e4:.1f}%")
```

### Place a trade (3 lines)

```python
from turbine_client import TurbineClient

client = TurbineClient.from_env()  # reads TURBINE_PRIVATE_KEY from .env
qm = client.get_quick_market("BTC")

result = client.buy(qm.market_id, "yes", price=0.55, size=1.0)
# Buys 1 YES share at 55¢ ($0.55 USDC risk, $1.00 payout if correct)
```

**Setup:** Create a `.env` file with your wallet private key:

```env
TURBINE_PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE
```

`from_env()` auto-registers API credentials on first run and prints them. Save them to `.env` for next time:

```env
TURBINE_PRIVATE_KEY=0x...
TURBINE_API_KEY_ID=abc123
TURBINE_API_PRIVATE_KEY=base64...
```

See [`.env.example`](.env.example) for the template.

---

## How Turbine Markets Work

- **Binary markets:** "Will BTC be above $X in 15 minutes?" → YES or NO
- **Price = probability:** 60¢ for YES means the market thinks 60% chance of YES
- **Payout:** Winning shares pay $1.00 USDC. Losing shares pay $0.
- **CLOB orderbook:** Limit orders matched on-chain, gasless via relayer
- **Chains:** Polygon (137), Avalanche (43114), Base Sepolia testnet (84532)

### Price & Size Conventions

| Human value | SDK value | Notes |
|---|---|---|
| 55% / $0.55 | `price=0.55` or `price=550000` | Floats 0–1 auto-scale |
| 1 share | `size=1.0` or `size=1_000_000` | Floats auto-scale (6 decimals) |
| $10 USDC | `10_000_000` (raw) | 6 decimal places |

The `buy()` and `sell()` convenience methods accept **floats** (0.55, 1.0) or **raw ints** (550000, 1000000).

---

## Client Setup

```python
# Option 1: From environment (recommended)
client = TurbineClient.from_env()

# Option 2: Explicit credentials
client = TurbineClient(
    private_key="0x...",
    api_key_id="...",
    api_private_key="...",
)

# Option 3: Read-only (public endpoints only)
client = TurbineClient()

# Option 4: Different chain
client = TurbineClient.from_env(chain_id=43114)  # Avalanche
```

### Getting API Credentials

```python
# One-time registration (or use from_env() which does this automatically)
creds = TurbineClient.request_api_credentials(
    host="https://api.turbinefi.com",
    private_key="0x...",
)
print(creds["api_key_id"])       # save this
print(creds["api_private_key"])  # save this — shown only once!
```

---

## Trading

### Convenience Methods (Recommended)

```python
# Buy YES shares — creates, signs, and submits in one call
result = client.buy(qm.market_id, "yes", price=0.60, size=5.0)

# Sell YES shares
result = client.sell(qm.market_id, "yes", price=0.70, size=5.0)

# Works with enums too
from turbine_client import Outcome
result = client.buy(qm.market_id, Outcome.NO, price=0.40, size=2.0)
```

### Low-Level Order Creation

```python
from turbine_client import Outcome

# Step 1: Create and sign
order = client.create_limit_buy(
    market_id=qm.market_id,
    outcome=Outcome.YES,
    price=550000,       # 55% (raw int)
    size=5_000_000,     # 5 shares (raw int)
    expiration=int(time.time()) + 300,  # 5 min
)

# Step 2: Submit
result = client.post_order(order)
print(result["orderHash"])

# Cancel
client.cancel_order(result["orderHash"], market_id=qm.market_id)

# Cancel all orders in a market
client.cancel_market_orders(qm.market_id)
```

---

## Market Data

```python
# Quick markets (15-min BTC/ETH)
qm = client.get_quick_market("BTC")
price = client.get_quick_market_price("BTC")
history = client.get_quick_market_history("BTC", limit=10)

# Orderbook
book = client.get_orderbook(qm.market_id)
for bid in book.bids[:3]:
    print(f"BID {bid.price / 1e4:.1f}% × {bid.size / 1e6:.2f}")

# Trades
trades = client.get_trades(qm.market_id, limit=20)

# All markets
markets = client.get_markets()

# Platform stats
stats = client.get_platform_stats()
```

---

## Positions & Account

```python
# Your positions
positions = client.get_user_positions(client.address, chain_id=137)
for pos in positions:
    print(f"YES: {pos.yes_shares / 1e6:.2f}  NO: {pos.no_shares / 1e6:.2f}")

# Your open orders
orders = client.get_orders(trader=client.address)

# Your P&L
stats = client.get_user_stats()
print(f"PNL: ${stats.pnl / 1e6:.2f} ({stats.pnl_percentage:.1f}%)")
```

---

## Claiming Winnings

After a market resolves, claim your USDC — gasless, no native token needed:

```python
# Single market
result = client.claim_winnings("0xMarketContractAddress")

# Batch claim multiple markets
result = client.batch_claim_winnings([
    "0xMarket1Address",
    "0xMarket2Address",
])
```

---

## WebSocket Streaming

```python
import asyncio
from turbine_client import TurbineWSClient

async def main():
    ws = TurbineWSClient(host="https://api.turbinefi.com")
    async with ws.connect() as stream:
        await stream.subscribe(market_id="0x...")
        async for msg in stream:
            if msg.type == "orderbook":
                print(f"Book update: {len(msg.data['bids'])} bids")
            elif msg.type == "trade":
                print(f"Trade: {msg.data}")

asyncio.run(main())
```

---

## USDC Approval (Gasless)

Before your first trade on a new settlement contract, USDC must be approved. This happens gaslessly via EIP-2612 permits:

```python
# One-time max approval (recommended) — no gas needed
client.approve_usdc_for_settlement()

# Also approve CTF tokens for claiming winnings
client.approve_ctf_for_settlement()

# Check current allowance
allowance = client.get_usdc_allowance()
```

---

## Examples

| File | Description |
|---|---|
| [`fetch_market_data.py`](examples/fetch_market_data.py) | Read orderbooks, prices, trades — no auth needed |
| [`simple_trading_loop.py`](examples/simple_trading_loop.py) | Buy YES/NO based on price vs strike |
| [`momentum_bot.py`](examples/momentum_bot.py) | Trade on short-term BTC momentum |
| [`price_action_bot.py`](examples/price_action_bot.py) | Full production bot with Pyth oracle, auto-claiming |
| [`market_maker.py`](examples/market_maker.py) | Two-sided quoting around mid price |
| [`websocket_stream.py`](examples/websocket_stream.py) | Real-time orderbook & trade streaming |
| [`basic_usage.py`](examples/basic_usage.py) | Walkthrough of public API endpoints |

---

## Error Handling

```python
from turbine_client.exceptions import (
    TurbineApiError,
    OrderValidationError,
    AuthenticationError,
)

try:
    client.buy(market_id, "yes", price=0.50, size=1.0)
except OrderValidationError as e:
    print(f"Bad order: {e}")
except AuthenticationError as e:
    print(f"Auth issue: {e}")
except TurbineApiError as e:
    print(f"API error ({e.status_code}): {e.message}")
```

---

## Architecture

```
turbine_client/
├── client.py              # TurbineClient — main entry point
├── types.py               # Dataclasses: OrderArgs, Market, Position, etc.
├── signer.py              # EIP-712 order signing
├── auth.py                # Ed25519 bearer token generation
├── config.py              # Chain configs (Polygon, Avalanche, Base Sepolia)
├── constants.py           # Endpoints, chain IDs, scaling factors
├── exceptions.py          # TurbineApiError, AuthenticationError, etc.
├── order_builder/         # OrderBuilder + price/size helpers
├── http/                  # HTTP client with auth
└── ws/                    # WebSocket client for streaming
```

---

## API Reference

### Public Endpoints (no auth)

| Method | Description |
|---|---|
| `get_markets()` | List all markets |
| `get_market(id)` | Market stats |
| `get_orderbook(id)` | Orderbook snapshot |
| `get_trades(id)` | Trade history |
| `get_quick_market(asset)` | Active 15-min market |
| `get_quick_market_price(asset)` | Current oracle price |
| `get_quick_market_history(asset)` | Historical quick markets |
| `get_quick_market_price_history(asset)` | Historical prices |
| `get_platform_stats()` | Platform-wide stats |
| `get_holders(id)` | Top position holders |
| `get_resolution(id)` | Market resolution status |
| `get_failed_trades()` | Failed trades |
| `get_pending_trades()` | Pending trades |
| `get_settlement_status(tx)` | Settlement TX status |

### Authenticated Endpoints

| Method | Description |
|---|---|
| `buy(market_id, outcome, price, size)` | Create + sign + submit buy |
| `sell(market_id, outcome, price, size)` | Create + sign + submit sell |
| `create_limit_buy(...)` | Create signed buy order |
| `create_limit_sell(...)` | Create signed sell order |
| `post_order(signed_order)` | Submit signed order |
| `get_orders(...)` | Query open orders |
| `cancel_order(hash)` | Cancel an order |
| `cancel_market_orders(id)` | Cancel all orders in market |
| `get_positions(market_id)` | Positions for a market |
| `get_user_positions(addr)` | All user positions |
| `get_user_stats()` | User P&L stats |
| `claim_winnings(addr)` | Gasless claim from resolved market |
| `batch_claim_winnings(addrs)` | Batch gasless claim |
| `approve_usdc_for_settlement()` | Gasless USDC max approval |
| `approve_ctf_for_settlement()` | Gasless CTF approval |

---

## Supported Chains

| Chain | ID | Status |
|---|---|---|
| Polygon | 137 | ✅ Production |
| Avalanche | 43114 | ✅ Production |
| Base Sepolia | 84532 | 🧪 Testnet |

---

## Development

```bash
git clone https://github.com/ojo-network/turbine-py-client.git
cd turbine-py-client
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check turbine_client/
```

---

## Claude Skill

Generate a trading bot interactively with Claude Code:

```bash
curl -sSL turbinefi.com/claude | bash
```

Deploy to Railway (free $5 credit):

```bash
claude "/railway-deploy"
```

---

## Links

- [Turbine App](https://beta.turbinefi.com)
- [Documentation](https://docs.ojolabs.xyz)
- [GitHub Issues](https://github.com/ojo-network/turbine-py-client/issues)

## License

MIT — see [LICENSE](LICENSE)
