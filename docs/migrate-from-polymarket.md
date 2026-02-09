# Migrating from Polymarket to Turbine

Already running a Polymarket trading bot? Here's how to add Turbine markets in ~20 lines of code.

## Why Add Turbine?

| Feature | Polymarket | Turbine |
|---------|-----------|---------|
| Market type | Binary prediction | Binary prediction |
| Orderbook | CLOB | CLOB |
| BTC 15-min markets | ✅ (Oct 2025) | ✅ |
| Gas costs | You pay gas | **Gasless** (Turbine covers it) |
| Chains | Polygon | Polygon + Avalanche |
| Resolution | UMA Oracle | UMA Oracle |
| API auth | HMAC + API key | EIP-712 + Ed25519 |
| Claiming winnings | Manual tx | **Gasless auto-claim** |
| SDK | py-clob-client | turbine-py-client |

**TL;DR:** Same market structure, no gas fees, faster onboarding.

## Concept Mapping

If you know Polymarket, you already know Turbine:

```
Polymarket              →  Turbine
─────────────────────────────────────
py-clob-client          →  turbine-py-client
ClobClient              →  TurbineClient
condition_id            →  market_id
token_id (YES/NO)       →  Outcome.YES / Outcome.NO
BUY/SELL                →  Side.BUY / Side.SELL
price (0-1 float)       →  price (0-1,000,000 int)
size (float)            →  size (int, 6 decimals)
create_and_post_order   →  create_order + post_order
```

## Quick Migration

### Before (Polymarket)

```python
from py_clob_client.client import ClobClient

client = ClobClient(
    host="https://clob.polymarket.com",
    key=PRIVATE_KEY,
    chain_id=137,
    funder=FUNDER_ADDRESS,
)

# Place a buy order
order = client.create_and_post_order(OrderArgs(
    token_id=YES_TOKEN_ID,
    price=0.55,
    size=10,
    side=BUY,
))
```

### After (Turbine)

```python
from turbine_client import TurbineClient, OrderArgs, Side, Outcome

client = TurbineClient(
    host="https://api.turbinefi.com",
    chain_id=137,
    private_key=PRIVATE_KEY,
    api_key_id=API_KEY_ID,
    api_private_key=API_PRIVATE_KEY,
)

# Place a buy order
order = client.create_order(OrderArgs(
    market_id=MARKET_ID,
    outcome=Outcome.YES,
    price=550000,        # 55% (scaled by 1e6)
    size=10_000_000,     # 10 shares (6 decimals)
    side=Side.BUY,
    expiration=int(time.time()) + 300,
))
result = client.post_order(order)
```

## Key Differences

### 1. Price Format

Polymarket uses floats (0.0 to 1.0). Turbine uses integers scaled by 1,000,000:

```python
# Polymarket: 55 cents
poly_price = 0.55

# Turbine: 55 cents
turbine_price = 550000  # 0.55 * 1_000_000
```

### 2. Size Format

Polymarket uses float shares. Turbine uses integers with 6 decimal places:

```python
# Polymarket: 10 shares
poly_size = 10.0

# Turbine: 10 shares
turbine_size = 10_000_000  # 10 * 1_000_000
```

### 3. Authentication

Polymarket uses HMAC-based API keys. Turbine uses Ed25519 bearer tokens:

```python
# Register for Turbine API credentials (one-time)
creds = TurbineClient.request_api_credentials(
    host="https://api.turbinefi.com",
    private_key=YOUR_WALLET_KEY,
)
# Save creds['api_key_id'] and creds['api_private_key']
```

### 4. Quick Markets (15-min BTC)

```python
# Get the current 15-minute BTC market
qm = client.get_quick_market("BTC")
print(f"Will BTC be above ${qm.start_price / 1e8:.0f} in 15 min?")
print(f"Market ID: {qm.market_id}")
print(f"Expires: {qm.end_time}")

# Trade it
order = client.create_order(OrderArgs(
    market_id=qm.market_id,
    outcome=Outcome.YES,
    price=600000,  # 60 cents
    size=5_000_000,  # 5 shares
    side=Side.BUY,
    expiration=int(time.time()) + 300,
))
client.post_order(order)
```

### 5. Gasless Claiming

On Polymarket, you pay gas to redeem winning shares. On Turbine, it's free:

```python
# Claim winnings — no gas required
result = client.claim_winnings("0xMarketAddress")

# Or batch claim from multiple markets
result = client.batch_claim_winnings([
    "0xMarket1", "0xMarket2", "0xMarket3"
])
```

## Running Both Simultaneously

Many bot operators run on multiple venues. Here's a pattern:

```python
from turbine_client import TurbineClient, OrderArgs, Side, Outcome
from py_clob_client.client import ClobClient

class MultiVenueBot:
    def __init__(self):
        self.turbine = TurbineClient(
            host="https://api.turbinefi.com",
            chain_id=137,
            private_key=PRIVATE_KEY,
            api_key_id=API_KEY_ID,
            api_private_key=API_PRIVATE_KEY,
        )
        self.polymarket = ClobClient(
            host="https://clob.polymarket.com",
            key=PRIVATE_KEY,
            chain_id=137,
        )

    def trade_btc_direction(self, direction: str, confidence: float):
        """Place the same directional bet on both venues."""
        outcome = Outcome.YES if direction == "up" else Outcome.NO
        price = int(confidence * 1_000_000)

        # Turbine (gasless)
        qm = self.turbine.get_quick_market("BTC")
        turbine_order = self.turbine.create_order(OrderArgs(
            market_id=qm.market_id,
            outcome=outcome,
            price=price,
            size=5_000_000,
            side=Side.BUY,
            expiration=int(time.time()) + 300,
        ))
        self.turbine.post_order(turbine_order)

        # Polymarket (requires gas)
        # ... your existing Polymarket logic
```

## Get Started

```bash
pip install turbine-py-client
```

1. Register for API credentials (see above)
2. Swap your client initialization
3. Adjust price/size formats
4. Run your existing strategy on Turbine markets

Questions? Open an issue on [GitHub](https://github.com/ojo-network/turbine-py-client/issues) or find us on [Moltbook](https://moltbook.com/u/Wozbot).
