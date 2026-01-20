"""Tests for TurbineClient."""

import pytest
import respx
from httpx import Response

from turbine_client import TurbineClient
from turbine_client.exceptions import AuthenticationError, TurbineApiError
from turbine_client.types import OrderArgs, Outcome, Side


class TestTurbineClientInit:
    """Tests for TurbineClient initialization."""

    def test_create_public_client(self, host, chain_id):
        """Test creating a public (no auth) client."""
        client = TurbineClient(host=host, chain_id=chain_id)

        assert client.host == host.rstrip("/")
        assert client.chain_id == chain_id
        assert client.address is None
        assert client.can_sign is False
        assert client.has_auth is False

        client.close()

    def test_create_signing_client(self, host, chain_id, private_key, test_address):
        """Test creating a client with signing capability."""
        client = TurbineClient(
            host=host,
            chain_id=chain_id,
            private_key=private_key,
        )

        assert client.can_sign is True
        assert client.has_auth is False
        assert client.address.lower() == test_address.lower()

        client.close()

    def test_create_full_auth_client(
        self, host, chain_id, private_key, api_key_id, api_private_key
    ):
        """Test creating a client with full authentication."""
        client = TurbineClient(
            host=host,
            chain_id=chain_id,
            private_key=private_key,
            api_key_id=api_key_id,
            api_private_key=api_private_key,
        )

        assert client.can_sign is True
        assert client.has_auth is True

        client.close()

    def test_context_manager(self, host, chain_id):
        """Test using client as context manager."""
        with TurbineClient(host=host, chain_id=chain_id) as client:
            assert client is not None


class TestPublicEndpoints:
    """Tests for public API endpoints."""

    @pytest.fixture
    def client(self, host, chain_id):
        """Create a public client for tests."""
        client = TurbineClient(host=host, chain_id=chain_id)
        yield client
        client.close()

    @respx.mock
    def test_get_health(self, client, host):
        """Test health check endpoint."""
        respx.get(f"{host}/health").mock(
            return_value=Response(200, json={"status": "ok"})
        )

        result = client.get_health()
        assert result["status"] == "ok"

    @respx.mock
    def test_get_markets(self, client, host, market_id):
        """Test getting markets."""
        respx.get(f"{host}/api/v1/markets").mock(
            return_value=Response(
                200,
                json={
                    "markets": [
                        {
                            "id": market_id,
                            "question": "Test market?",
                            "description": "",
                            "category": "test",
                            "expirationTime": 1735689600,
                            "contractAddress": "0x" + "aa" * 20,
                            "chainId": 137,
                            "resolved": False,
                        }
                    ]
                },
            )
        )

        markets = client.get_markets()
        assert len(markets) == 1
        assert markets[0].id == market_id
        assert markets[0].question == "Test market?"

    @respx.mock
    def test_get_market(self, client, host, market_id):
        """Test getting a specific market."""
        respx.get(f"{host}/api/v1/markets/{market_id}").mock(
            return_value=Response(
                200,
                json={
                    "id": market_id,
                    "question": "Test market?",
                    "description": "",
                    "category": "test",
                    "expirationTime": 1735689600,
                    "contractAddress": "0x" + "aa" * 20,
                    "chainId": 137,
                    "resolved": False,
                },
            )
        )

        market = client.get_market(market_id)
        assert market.id == market_id

    @respx.mock
    def test_get_orderbook(self, client, host, market_id):
        """Test getting orderbook."""
        respx.get(f"{host}/api/v1/orderbook/{market_id}").mock(
            return_value=Response(
                200,
                json={
                    "marketId": market_id,
                    "bids": [{"price": 490000, "size": 5000000}],
                    "asks": [{"price": 510000, "size": 5000000}],
                    "lastUpdate": 1735689600,
                },
            )
        )

        orderbook = client.get_orderbook(market_id)
        assert orderbook.market_id == market_id
        assert len(orderbook.bids) == 1
        assert len(orderbook.asks) == 1

    @respx.mock
    def test_get_trades(self, client, host, market_id, test_address):
        """Test getting trades."""
        respx.get(f"{host}/api/v1/trades/{market_id}").mock(
            return_value=Response(
                200,
                json={
                    "trades": [
                        {
                            "marketId": market_id,
                            "price": 500000,
                            "size": 1000000,
                            "outcome": 0,
                            "side": 0,
                            "maker": test_address,
                            "taker": "0x" + "bb" * 20,
                            "timestamp": 1735689600,
                            "tradeHash": "0x" + "cc" * 32,
                        }
                    ]
                },
            )
        )

        trades = client.get_trades(market_id)
        assert len(trades) == 1
        assert trades[0].price == 500000

    @respx.mock
    def test_api_error_handling(self, client, host, market_id):
        """Test API error handling."""
        respx.get(f"{host}/api/v1/markets/{market_id}").mock(
            return_value=Response(404, json={"error": "Market not found"})
        )

        with pytest.raises(TurbineApiError) as exc_info:
            client.get_market(market_id)

        assert exc_info.value.status_code == 404
        assert "Market not found" in str(exc_info.value)


class TestOrderCreation:
    """Tests for order creation."""

    @pytest.fixture
    def client(self, host, chain_id, private_key):
        """Create a signing client for tests."""
        client = TurbineClient(
            host=host,
            chain_id=chain_id,
            private_key=private_key,
        )
        yield client
        client.close()

    def test_create_order(self, client, market_id, settlement_address):
        """Test creating a signed order."""
        order_args = OrderArgs(
            market_id=market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
            expiration=1735689600,
        )

        signed_order = client.create_order(order_args, settlement_address=settlement_address)

        assert signed_order.market_id == market_id
        assert signed_order.price == 500000
        assert signed_order.signature is not None

    def test_create_limit_buy(self, client, market_id, settlement_address):
        """Test creating a limit buy order."""
        order = client.create_limit_buy(
            market_id=market_id,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
            settlement_address=settlement_address,
        )

        assert order.side == 0  # BUY

    def test_create_limit_sell(self, client, market_id, settlement_address):
        """Test creating a limit sell order."""
        order = client.create_limit_sell(
            market_id=market_id,
            outcome=Outcome.NO,
            price=300000,
            size=2000000,
            settlement_address=settlement_address,
        )

        assert order.side == 1  # SELL

    def test_create_order_requires_signer(self, host, chain_id, market_id):
        """Test that order creation requires a signer."""
        client = TurbineClient(host=host, chain_id=chain_id)

        with pytest.raises(AuthenticationError, match="Private key required"):
            client.create_order(
                OrderArgs(
                    market_id=market_id,
                    side=Side.BUY,
                    outcome=Outcome.YES,
                    price=500000,
                    size=1000000,
                    expiration=1735689600,
                )
            )

        client.close()


class TestAuthenticatedEndpoints:
    """Tests for authenticated API endpoints."""

    @pytest.fixture
    def client(self, host, chain_id, private_key, api_key_id, api_private_key):
        """Create a fully authenticated client for tests."""
        client = TurbineClient(
            host=host,
            chain_id=chain_id,
            private_key=private_key,
            api_key_id=api_key_id,
            api_private_key=api_private_key,
        )
        yield client
        client.close()

    @respx.mock
    def test_post_order(self, client, host, market_id, settlement_address):
        """Test posting an order."""
        respx.post(f"{host}/api/v1/orders").mock(
            return_value=Response(
                200,
                json={"orderHash": "0x" + "ab" * 32, "status": "open"},
            )
        )

        signed_order = client.create_order(
            OrderArgs(
                market_id=market_id,
                side=Side.BUY,
                outcome=Outcome.YES,
                price=500000,
                size=1000000,
                expiration=1735689600,
            ),
            settlement_address=settlement_address,
        )

        result = client.post_order(signed_order)
        assert "orderHash" in result

    @respx.mock
    def test_get_orders(self, client, host, market_id, test_address):
        """Test getting orders."""
        respx.get(f"{host}/api/v1/orders").mock(
            return_value=Response(
                200,
                json={
                    "orders": [
                        {
                            "orderHash": "0x" + "ab" * 32,
                            "marketId": market_id,
                            "trader": test_address,
                            "side": 0,
                            "outcome": 0,
                            "price": 500000,
                            "size": 1000000,
                            "filledSize": 0,
                            "remainingSize": 1000000,
                            "nonce": 1,
                            "expiration": 1735689600,
                            "status": "open",
                            "createdAt": 1735600000,
                        }
                    ]
                },
            )
        )

        orders = client.get_orders(trader=test_address)
        assert len(orders) == 1
        assert orders[0].price == 500000

    @respx.mock
    def test_cancel_order(self, client, host):
        """Test canceling an order."""
        order_hash = "0x" + "ab" * 32
        respx.delete(f"{host}/api/v1/orders/{order_hash}").mock(
            return_value=Response(200, json={"success": True})
        )

        result = client.cancel_order(order_hash)
        assert result["success"] is True

    def test_authenticated_endpoint_requires_auth(self, host, chain_id, private_key):
        """Test that authenticated endpoints require auth."""
        client = TurbineClient(
            host=host,
            chain_id=chain_id,
            private_key=private_key,
            # No API credentials
        )

        with pytest.raises(AuthenticationError, match="API credentials required"):
            client.get_orders()

        client.close()
