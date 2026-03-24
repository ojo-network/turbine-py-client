# Polymarket Integration Design

## Overview

Add Polymarket as a trading backend to Turbine's API. Turbine acts as a **stateless, non-custodial proxy** — same unified API surface, but requests tagged with `?polymarket=true` route to Polymarket's CLOB via the [polymarket-go-sdk](https://github.com/GoPolymarket/polymarket-go-sdk). Credentials are passed per-request in headers and never stored.

## Goals

- Pro users trade on Polymarket through Turbine's interface and bot SDK
- Non-custodial: Turbine never stores Polymarket API credentials
- Unified API: same endpoints serve both Turbine-native and Polymarket markets
- Stateless proxy: credentials passed per-request, used once, discarded

## Non-Goals (for now)

- Polymarket WebSocket streaming through Turbine
- Position/trade tracking in Turbine's database for Polymarket trades
- Polymarket rewards, balance allowances, or bridge operations

## Architecture

```
Client (browser / bot SDK)
  │
  │  X-Polymarket-Key / Secret / Passphrase headers
  │  ?polymarket=true query param
  │
  ▼
Turbine API  ──── polymarket=true? ────► Polymarket Handler
  │                                        │
  │ (no)                                   │ Uses polymarket-go-sdk
  │                                        │ Builds ephemeral client per-request
  ▼                                        ▼
Existing Turbine flow              Polymarket CLOB API
                                   (clob.polymarket.com)
```

### Key Principle: Stateless & Non-Custodial

Every Polymarket request:
1. Client sends `X-Polymarket-Key`, `X-Polymarket-Secret`, `X-Polymarket-Passphrase` headers
2. Handler builds an ephemeral polymarket-go-sdk client with those credentials
3. SDK call is made
4. Response returned to client
5. Credentials are garbage collected — never written to disk or database

## Credential Onboarding

### Endpoint

```
POST /api/v1/polymarket/auth
```

### Auth Middleware

`POST /api/v1/polymarket/auth` must be added to the auth middleware's public path exemptions (alongside existing `/api/v1/api-keys`). This endpoint authenticates via the EIP-712 wallet signature, not a Turbine bearer token.

### Flow

1. Client sends the user's EIP-712 signature (signed client-side via wallet)
2. Turbine constructs L1 auth headers (`POLY_ADDRESS`, `POLY_SIGNATURE`, `POLY_TIMESTAMP`, `POLY_NONCE`)
3. Turbine calls `POST https://clob.polymarket.com/auth/api-key` (or `GET .../auth/derive-api-key`)
4. Returns `{ apiKey, secret, passphrase }` directly to client
5. Client stores credentials locally (browser storage / bot config)

### Why this goes through Turbine (not direct client→Polymarket)

The client could call Polymarket's auth endpoint directly, but routing through Turbine allows: (a) CORS avoidance since `clob.polymarket.com` may not allow browser origins, (b) future tier gating, and (c) consistent bot SDK interface.

### Request

```json
{
  "address": "0x...",
  "signature": "0x...",
  "timestamp": "1711100000",
  "nonce": 0
}
```

### Response

```json
{
  "apiKey": "...",
  "secret": "...",
  "passphrase": "..."
}
```

## API Endpoints

All existing endpoints gain Polymarket routing via `?polymarket=true`.

**Public endpoints** (no `X-Polymarket-*` headers required):
- `GET /api/v1/markets?polymarket=true` — browse Polymarket markets
- `GET /api/v1/orderbook/{marketId}?polymarket=true` — view orderbook

**Authenticated endpoints** (require `X-Polymarket-*` headers):
- `POST /api/v1/orders?polymarket=true` — place order
- `DELETE /api/v1/orders/{orderId}?polymarket=true` — cancel order
- `GET /api/v1/orders?polymarket=true` — list user's open orders
- `GET /api/v1/users/{address}/positions?polymarket=true` — user positions

### Markets

**`GET /api/v1/markets?polymarket=true`**

- Calls `client.CLOB.Markets()` / `client.CLOB.MarketsAll()` via SDK
- Returns Polymarket markets in Turbine's market response format
- Supports pagination via `next_cursor` query param

**`GET /api/v1/orderbook/{marketId}?polymarket=true`**

- `marketId` is the Polymarket token ID / condition ID
- Calls SDK to fetch orderbook
- Returns in Turbine's orderbook response format

### Orders

**`POST /api/v1/orders?polymarket=true`**

- Client is responsible for signing the Polymarket order client-side (EIP-712 with Polymarket's domain)
- Request body includes the pre-signed order payload (token_id, side, price, size, order_type, signature)
- Handler forwards the signed order via `client.CLOB.CreateOrder()`
- Turbine never has access to the user's private key — only the resulting signature
- Returns Polymarket's order response

```json
{
  "token_id": "12345...",
  "side": "BUY",
  "price": "0.65",
  "size": "100",
  "order_type": "GTC",
  "signature": "0x..."
}
```

**`DELETE /api/v1/orders/{orderId}?polymarket=true`**

- Calls `client.CLOB.CancelOrder()` with the order ID
- Returns confirmation

**`GET /api/v1/orders?polymarket=true`**

- Calls SDK to fetch user's open orders
- Returns in Turbine's order list format

### Positions

**`GET /api/v1/users/{address}/positions?polymarket=true`**

- Calls SDK balance/allowance endpoints
- Returns user's Polymarket positions

## New Package Structure

```
api/internal/polymarket/
├── client.go      # Ephemeral SDK client builder from request headers
├── handler.go     # HTTP handlers for Polymarket-routed requests
├── auth.go        # Credential onboarding (L1 signature → API key creation)
└── convert.go     # Response format converters (Polymarket → Turbine types)
```

### client.go

```go
// NewEphemeralClient creates a one-shot polymarket-go-sdk client
// from per-request credentials. Never stored.
func NewEphemeralClient(apiKey, secret, passphrase string) (*polymarket.Client, error)
```

### Handler Integration

The polymarket handler is registered in the main router. Existing handlers check for `?polymarket=true` and delegate:

```go
// In orders handler
func (h *OrderHandler) SubmitOrder(w http.ResponseWriter, r *http.Request) {
    if r.URL.Query().Get("polymarket") == "true" {
        h.polymarketHandler.SubmitOrder(w, r)
        return
    }
    // ... existing Turbine order flow
}
```

### Header Extraction

```go
func ExtractPolymarketCreds(r *http.Request) (apiKey, secret, passphrase string, err error) {
    apiKey = r.Header.Get("X-Polymarket-Key")
    secret = r.Header.Get("X-Polymarket-Secret")
    passphrase = r.Header.Get("X-Polymarket-Passphrase")

    // Scrub credentials from request headers immediately after extraction
    // to prevent accidental logging by downstream middleware or error handlers
    r.Header.Del("X-Polymarket-Key")
    r.Header.Del("X-Polymarket-Secret")
    r.Header.Del("X-Polymarket-Passphrase")

    if apiKey == "" || secret == "" || passphrase == "" {
        return "", "", "", errors.New("missing Polymarket credentials")
    }
    return
}
```

## Response Format Mapping

Polymarket responses are converted to match Turbine's existing response shapes so the frontend/bot SDK doesn't need conditional logic per provider.

| Turbine Field | Polymarket Source |
|---|---|
| `market.id` | Polymarket condition ID |
| `market.question` | Market question text |
| `market.description` | Market description |
| `market.outcomes` | Token IDs for YES/NO |
| `market.volume` | Polymarket volume |
| `market.end_date` | Market end date/expiration |
| `market.resolved` | Resolution status |
| `market.category` | Category tag |
| `market.chain_id` | Hardcoded `137` (Polygon, where Polymarket settles) |
| `market.provider` | `"polymarket"` (new field to distinguish from native markets) |
| `order.id` | Polymarket order ID |
| `order.price` | Order price (decimal) |
| `order.size` | Order size |
| `order.side` | BUY/SELL |
| `order.status` | Order lifecycle state |
| `position.shares` | Balance from SDK |

Fields not available from Polymarket (e.g., `bestAskPrice` from in-memory orderbook) will be omitted or fetched separately from their orderbook endpoint. The `convert.go` module is expected to be the most complex part of the integration.

## Error Handling

- Missing `X-Polymarket-*` headers on `?polymarket=true` requests → `401 Unauthorized`
- Invalid/expired Polymarket credentials → forward Polymarket's error with `403`
- Polymarket API errors (rate limit, server error) → forward with appropriate HTTP status
- SDK-specific errors (`ErrInsufficientFunds`, `ErrRateLimitExceeded`) → mapped to human-readable messages

## Security Considerations

- **No credential storage**: API keys exist only in request memory, garbage collected after response
- **Credential scrubbing**: `ExtractPolymarketCreds` deletes `X-Polymarket-*` headers from the request immediately after extraction, preventing accidental logging by chi's logger, error handlers, or any future middleware
- **HTTPS only**: Credentials transit encrypted (enforced at infrastructure level)
- **No URL exposure**: Credentials in headers, not query params or body, avoiding access logs
- **Per-request isolation**: Each request builds a fresh SDK client; no shared state between users
- **Client-side order signing**: Polymarket orders are signed client-side; Turbine never has access to private keys

## Dependencies

- `github.com/GoPolymarket/polymarket-go-sdk` added to `go.mod`
- No database schema changes
- No new background workers or persistent connections

### SDK Validation

The `polymarket-go-sdk` must be validated before implementation begins:
- Confirm the SDK exists, is maintained, and the API surface matches assumptions (e.g., `client.CLOB.Markets()`, `client.CLOB.CreateOrder()`, `clob.NewOrderBuilder()`)
- If the SDK is unmaintained or has a different API, fallback plan is direct HTTP calls to `clob.polymarket.com` using Polymarket's REST API with manual L2 HMAC header construction

### Timeout Handling

SDK calls to Polymarket should use a 15-second context timeout (not the full 60-second chi timeout) to fail fast on slow Polymarket responses and avoid tying up goroutines.

## Testing Strategy

- Unit tests for response format conversion (`convert.go`) with inline assertions against known Polymarket response shapes
- Unit tests for header extraction, credential scrubbing, and validation
- Integration tests using a `PolymarketClient` interface (not concrete SDK type) with mock implementation for:
  - Successful order placement/cancellation
  - Expired/invalid credentials (403)
  - Rate limiting (429)
  - Malformed Polymarket responses
- Manual testing against Polymarket's live API (requires real credentials)

