# Turbine Python Client

A Python client for market makers to interact with the Turbine CLOB (Central Limit Order Book) prediction markets API.

## Overview

This client provides a clean, typed interface for:
- Creating and signing EIP-712 orders
- Submitting orders to the Turbine orderbook
- Managing positions and tracking fills
- Subscribing to real-time orderbook updates via WebSocket
- Multi-chain support (Base Sepolia, Polygon, etc.)

Inspired by [Polymarket's py-clob-client](https://github.com/Polymarket/py-clob-client).

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Authentication](#authentication)
5. [Order Management](#order-management)
6. [Market Data](#market-data)
7. [WebSocket Streaming](#websocket-streaming)
8. [Data Types](#data-types)
9. [API Reference](#api-reference)
10. [Examples](#examples)
11. [Development](#development)

---

## Installation

```bash
pip install turbine-py-client
```

Or install from source:

```bash
git clone https://github.com/turbine/turbine-py-client.git
cd turbine-py-client
pip install -e .
```

### Dependencies

- `eth-account>=0.13.0` - Ethereum account management and signing
- `eth-utils>=4.1.1` - Ethereum utilities (keccak, address validation)
- `httpx[http2]>=0.27.0` - HTTP client with HTTP/2 support
- `websockets>=12.0` - WebSocket client
- `pynacl>=1.5.0` - Ed25519 signing for bearer tokens
- `python-dotenv>=1.0.0` - Environment variable management

---

## Quick Start

### Read-Only Access (No Authentication)

```python
from turbine_client import TurbineClient

# Public endpoints - no auth required
client = TurbineClient(
    host="https://api.turbine.markets",
    chain_id=84532  # Base Sepolia
)

# Get all markets
markets = client.get_markets()

# Get orderbook for a market
orderbook = client.get_orderbook(market_id="0x...")

# Get recent trades
trades = client.get_trades(market_id="0x...")
```

### Trading with EIP-712 Signed Orders

```python
from turbine_client import TurbineClient, OrderArgs, Side, Outcome

# Initialize with private key for order signing
client = TurbineClient(
    host="https://api.turbine.markets",
    chain_id=84532,
    private_key="0x...",  # Your wallet private key
)

# Create and sign an order
order_args = OrderArgs(
    market_id="0x1234...",
    side=Side.BUY,
    outcome=Outcome.YES,
    price=500000,      # 50% (price scaled by 1e6)
    size=1000000,      # 1 share (6 decimals)
    expiration=int(time.time()) + 3600,  # 1 hour from now
)

signed_order = client.create_order(order_args)
response = client.post_order(signed_order)
print(f"Order submitted: {response['orderHash']}")
```

### With Bearer Token Authentication

```python
from turbine_client import TurbineClient

# For authenticated endpoints (positions, user orders)
client = TurbineClient(
    host="https://api.turbine.markets",
    chain_id=84532,
    private_key="0x...",
    api_key_id="abc123...",           # Ed25519 key ID
    api_private_key="0x...",          # Ed25519 private key (hex)
)

# Get your positions
positions = client.get_positions(user_address="0x...")

# Get your open orders
orders = client.get_orders(trader="0x...")
```

---

## Architecture

### Project Structure

```
turbine_py_client/
├── __init__.py                 # Main exports
├── client.py                   # TurbineClient class
├── signer.py                   # EIP-712 order signing
├── auth.py                     # Bearer token generation (Ed25519)
├── config.py                   # Chain configurations
├── constants.py                # Constants (endpoints, chain IDs)
├── exceptions.py               # Custom exceptions
├── types.py                    # Data types and models
├── order_builder/
│   ├── __init__.py
│   ├── builder.py              # OrderBuilder class
│   └── helpers.py              # Price/size utilities
├── http/
│   ├── __init__.py
│   └── client.py               # HTTP request handling
├── ws/
│   ├── __init__.py
│   └── client.py               # WebSocket client
└── utils.py                    # Utility functions
```

### Design Patterns

Following Polymarket's proven patterns:

1. **Modular Authentication** - Separate concerns for EIP-712 signing vs Bearer tokens
2. **Builder Pattern** - OrderBuilder encapsulates order creation and signing
3. **Dataclass Types** - Clean, serializable data structures with type hints
4. **Async WebSocket** - Non-blocking real-time updates

---

## Authentication

Turbine uses two authentication mechanisms:

### 1. EIP-712 Order Signing (Required for Trading)

All orders must be signed using EIP-712 structured data. The client handles this automatically.

**Domain Separator:**
```python
{
    "name": "Turbine",
    "version": "1",
    "chainId": 84532,  # Chain-specific
    "verifyingContract": "0x..."  # Settlement contract
}
```

**Order Type:**
```python
Order(
    bytes32 marketId,
    address trader,
    uint8 side,        # 0=BUY, 1=SELL
    uint8 outcome,     # 0=YES, 1=NO
    uint256 price,
    uint256 size,
    uint256 nonce,
    uint256 expiration,
    address makerFeeRecipient
)
```

### 2. Bearer Token Authentication (For Private Endpoints)

Some endpoints require Ed25519 bearer tokens:

```python
# Token format: base64url(payload).base64url(signature)
# Payload: {"kid": keyId, "ts": timestamp, "n": nonce}
```

**Generate API Keys:**
```bash
# Use Turbine CLI to generate keys
./turbine genkey --name "my-market-maker" --owner 0x...
```

---

## Order Management

### Creating Orders

```python
from turbine_client import OrderArgs, Side, Outcome

# Basic limit order
order = OrderArgs(
    market_id="0x1234...",
    side=Side.BUY,
    outcome=Outcome.YES,
    price=500000,       # 50%
    size=10000000,      # 10 shares
    expiration=int(time.time()) + 86400,  # 24 hours
)

signed = client.create_order(order)
result = client.post_order(signed)
```

### Price Representation

Prices are scaled by 1,000,000 (1e6):
- `500000` = 50% (even odds)
- `250000` = 25%
- `750000` = 75%
- Range: 1 to 999,999

### Order Lifecycle

1. **Create** - Build order parameters
2. **Sign** - EIP-712 signature via eth_account
3. **Submit** - POST to `/api/v1/orders`
4. **Match** - Engine matches against orderbook
5. **Settle** - On-chain settlement
6. **Confirm** - Position updated

### Canceling Orders

```python
# Cancel single order
client.cancel_order(
    order_hash="0x...",
    market_id="0x...",
    side=Side.BUY
)

# Cancel all orders for a market
client.cancel_market_orders(market_id="0x...")
```

---

## Market Data

### Get Markets

```python
# All markets
markets = client.get_markets()

# Filter by chain
markets = client.get_markets(chain_id=84532)

# Single market
market = client.get_market(market_id="0x...")
```

### Get Orderbook

```python
# Full orderbook
orderbook = client.get_orderbook(market_id="0x...")

# Filter by outcome
yes_book = client.get_orderbook(market_id="0x...", outcome=Outcome.YES)

# Access bids/asks
for bid in orderbook.bids:
    print(f"Bid: {bid.price} x {bid.size}")
```

### Get Trades

```python
# Recent trades (last 100)
trades = client.get_trades(market_id="0x...")

# Trade details
for trade in trades:
    print(f"{trade.timestamp}: {trade.price} x {trade.size}")
```

### Get Statistics

```python
# Market stats
stats = client.get_stats(market_id="0x...")
print(f"24h Volume: {stats.volume_24h}")
print(f"Last Price: {stats.last_price}")

# Platform stats
platform = client.get_platform_stats()
print(f"Total Markets: {platform.market_count}")
```

### Quick Markets (15-minute BTC/ETH)

```python
# Get active quick market
qm = client.get_quick_market(asset="BTC")
print(f"Strike: ${qm.start_price / 1e8}")
print(f"Expires: {qm.end_time}")

# Price feed
price = client.get_quick_market_price(asset="BTC")
print(f"Current BTC: ${price.price_usd}")
```

---

## WebSocket Streaming

### Basic Subscription

```python
import asyncio
from turbine_client import TurbineWSClient

async def main():
    ws = TurbineWSClient(host="wss://api.turbine.markets")

    async with ws.connect() as stream:
        # Subscribe to market
        await stream.subscribe(market_id="0x...")

        async for message in stream:
            if message.type == "orderbook":
                print(f"Orderbook update: {len(message.data.bids)} bids")
            elif message.type == "trade":
                print(f"Trade: {message.data.price} x {message.data.size}")

asyncio.run(main())
```

### Message Types

```python
# Orderbook update
{
    "type": "orderbook",
    "marketId": "0x...",
    "data": {
        "bids": [{"price": 500000, "size": 10000}],
        "asks": [{"price": 510000, "size": 5000}],
        "lastUpdate": 1705000000
    }
}

# Trade execution
{
    "type": "trade",
    "marketId": "0x...",
    "data": {
        "price": 505000,
        "size": 5000,
        "outcome": 0,
        "side": 0,
        "maker": "0x...",
        "taker": "0x..."
    }
}

# Quick market update
{
    "type": "quick_market",
    "data": {
        "asset": "BTC",
        "marketId": "0x...",
        "startPrice": 95000000000,
        "resolved": false
    }
}
```

---

## Data Types

### Core Types

```python
from dataclasses import dataclass
from enum import Enum, IntEnum

class Side(IntEnum):
    BUY = 0
    SELL = 1

class Outcome(IntEnum):
    YES = 0
    NO = 1

@dataclass
class OrderArgs:
    market_id: str
    side: Side
    outcome: Outcome
    price: int          # 0 to 1,000,000
    size: int           # 6 decimals
    expiration: int     # Unix timestamp
    nonce: int = 0      # Auto-generated if 0
    maker_fee_recipient: str = "0x0000000000000000000000000000000000000000"

@dataclass
class SignedOrder:
    market_id: str
    trader: str
    side: int
    outcome: int
    price: int
    size: int
    nonce: int
    expiration: int
    maker_fee_recipient: str
    signature: str
    order_hash: str

@dataclass
class OrderBookSnapshot:
    market_id: str
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    last_update: int

@dataclass
class PriceLevel:
    price: int
    size: int

@dataclass
class Trade:
    market_id: str
    price: int
    size: int
    outcome: int
    side: int
    maker: str
    taker: str
    timestamp: int
    trade_hash: str

@dataclass
class Position:
    market_id: str
    user_address: str
    yes_shares: int
    no_shares: int
    invested: int
    last_trade_price: int

@dataclass
class Market:
    id: str
    question: str
    description: str
    category: str
    expiration_time: int
    contract_address: str
    chain_id: int
    resolved: bool
    winning_outcome: int | None
```

---

## API Reference

### Public Endpoints (No Auth)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get_markets()` | `GET /api/v1/markets` | List all markets |
| `get_orderbook(market_id)` | `GET /api/v1/orderbook/{id}` | Get orderbook |
| `get_trades(market_id)` | `GET /api/v1/trades/{id}` | Get trade history |
| `get_stats(market_id)` | `GET /api/v1/stats/{id}` | Get market stats |
| `get_platform_stats()` | `GET /api/v1/platform/stats` | Get platform stats |
| `get_holders(market_id)` | `GET /api/v1/holders/{id}` | Get top holders |
| `get_quick_market(asset)` | `GET /api/v1/quick-markets/{asset}` | Get active quick market |

### Authenticated Endpoints (Bearer Token)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `post_order(order)` | `POST /api/v1/orders` | Submit signed order |
| `get_orders(trader)` | `GET /api/v1/orders` | Get user's open orders |
| `cancel_order(hash)` | `DELETE /api/v1/orders/{hash}` | Cancel order |
| `get_positions(user)` | `GET /api/v1/positions/{market}` | Get user position |
| `get_user_positions(addr)` | `GET /api/v1/users/{addr}/positions` | All positions |
| `get_user_activity(addr)` | `GET /api/v1/users/{addr}/activity` | Trading activity |

### Relayer Endpoints (Gasless)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `ctf_approval(request)` | `POST /api/v1/relayer/ctf-approval` | Gasless CTF approval |
| `ctf_redemption(request)` | `POST /api/v1/relayer/ctf-redemption` | Gasless redemption |

---

## Examples

### Market Making Bot

```python
import asyncio
from turbine_client import TurbineClient, TurbineWSClient, OrderArgs, Side, Outcome

class SimpleMarketMaker:
    def __init__(self, client: TurbineClient, market_id: str):
        self.client = client
        self.market_id = market_id
        self.spread = 20000  # 2% spread

    async def run(self):
        ws = TurbineWSClient(host=self.client.host)

        async with ws.connect() as stream:
            await stream.subscribe(market_id=self.market_id)

            async for msg in stream:
                if msg.type == "orderbook":
                    await self.update_quotes(msg.data)

    async def update_quotes(self, orderbook):
        # Cancel existing orders
        self.client.cancel_market_orders(self.market_id)

        # Calculate mid price
        best_bid = orderbook.bids[0].price if orderbook.bids else 400000
        best_ask = orderbook.asks[0].price if orderbook.asks else 600000
        mid = (best_bid + best_ask) // 2

        # Place new quotes
        buy_order = self.client.create_order(OrderArgs(
            market_id=self.market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=mid - self.spread // 2,
            size=1000000,
            expiration=int(time.time()) + 300,
        ))

        sell_order = self.client.create_order(OrderArgs(
            market_id=self.market_id,
            side=Side.SELL,
            outcome=Outcome.YES,
            price=mid + self.spread // 2,
            size=1000000,
            expiration=int(time.time()) + 300,
        ))

        self.client.post_order(buy_order)
        self.client.post_order(sell_order)
```

### Position Monitoring

```python
from turbine_client import TurbineClient

client = TurbineClient(
    host="https://api.turbine.markets",
    chain_id=84532,
    api_key_id="...",
    api_private_key="..."
)

# Get all positions
positions = client.get_user_positions(
    address="0x...",
    chain_id=84532
)

for pos in positions:
    market = client.get_market(pos.market_id)
    print(f"\n{market.question}")
    print(f"  YES: {pos.yes_shares / 1e6:.2f} shares")
    print(f"  NO:  {pos.no_shares / 1e6:.2f} shares")
    print(f"  Cost Basis: ${pos.invested / 1e6:.2f}")
```

---

## Development

### Setup

```bash
# Clone repo
git clone https://github.com/turbine/turbine-py-client.git
cd turbine-py-client

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/
```

### Type Checking

```bash
mypy turbine_py_client/
```

### Linting

```bash
ruff check turbine_py_client/
ruff format turbine_py_client/
```

---

## Chain Configuration

| Chain | Chain ID | Settlement Contract |
|-------|----------|---------------------|
| Base Sepolia (Testnet) | 84532 | TBD |
| Polygon | 137 | TBD |

---

## Error Handling

```python
from turbine_client.exceptions import (
    TurbineApiError,
    OrderValidationError,
    SignatureError,
    AuthenticationError,
)

try:
    client.post_order(signed_order)
except OrderValidationError as e:
    print(f"Invalid order: {e}")
except AuthenticationError as e:
    print(f"Auth failed: {e}")
except TurbineApiError as e:
    print(f"API error ({e.status_code}): {e.message}")
```

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

---

## License

MIT License - see [LICENSE](LICENSE)

---

## Links

- [Turbine Markets](https://turbine.markets)
- [API Documentation](https://docs.turbine.markets)
- [GitHub Issues](https://github.com/turbine/turbine-py-client/issues)
