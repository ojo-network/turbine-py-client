"""
Unit tests for the Polymarket client.
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from turbine_client.polymarket import PolymarketClient
from turbine_client.exceptions import TurbineApiError


@pytest.fixture
def client():
    """Authenticated Polymarket client."""
    return PolymarketClient(
        host="https://api.turbine.test",
        polymarket_key="test-key",
        polymarket_secret="test-secret",
        polymarket_passphrase="test-passphrase",
    )


@pytest.fixture
def public_client():
    """Unauthenticated Polymarket client."""
    return PolymarketClient(host="https://api.turbine.test")


class TestPolymarketParams:
    """All requests must include ?polymarket=true."""

    def test_get_markets_has_polymarket_param(self, client):
        response = httpx.Response(200, json={"markets": []})
        with patch.object(client._client, "get", return_value=response) as mock_get:
            client.get_markets()
            _, kwargs = mock_get.call_args
            assert kwargs["params"]["polymarket"] == "true"

    def test_get_orderbook_has_polymarket_param(self, client):
        response = httpx.Response(200, json={"bids": [], "asks": []})
        with patch.object(client._client, "get", return_value=response) as mock_get:
            client.get_orderbook("token123")
            args, kwargs = mock_get.call_args
            assert "token123" in args[0]
            assert kwargs["params"]["polymarket"] == "true"

    def test_create_order_has_polymarket_param(self, client):
        response = httpx.Response(200, json={"orderId": "abc"})
        with patch.object(client._client, "post", return_value=response) as mock_post:
            client.create_order("token123", "BUY", "0.65", "100")
            _, kwargs = mock_post.call_args
            assert kwargs["params"]["polymarket"] == "true"

    def test_cancel_order_has_polymarket_param(self, client):
        response = httpx.Response(200, json={"status": "cancelled"})
        with patch.object(client._client, "delete", return_value=response) as mock_del:
            client.cancel_order("order123")
            _, kwargs = mock_del.call_args
            assert kwargs["params"]["polymarket"] == "true"

    def test_get_open_orders_has_polymarket_param(self, client):
        response = httpx.Response(200, json=[])
        with patch.object(client._client, "get", return_value=response) as mock_get:
            client.get_open_orders()
            _, kwargs = mock_get.call_args
            assert kwargs["params"]["polymarket"] == "true"

    def test_get_positions_has_polymarket_param(self, client):
        response = httpx.Response(200, json=[])
        with patch.object(client._client, "get", return_value=response) as mock_get:
            client.get_positions("0xabc")
            args, kwargs = mock_get.call_args
            assert "0xabc" in args[0]
            assert kwargs["params"]["polymarket"] == "true"


class TestAuthHeaders:
    """Authenticated requests must include X-Polymarket-* headers."""

    def test_authenticated_request_has_all_headers(self, client):
        response = httpx.Response(200, json=[])
        with patch.object(client._client, "get", return_value=response) as mock_get:
            client.get_open_orders()
            _, kwargs = mock_get.call_args
            headers = kwargs["headers"]
            assert headers["X-Polymarket-Key"] == "test-key"
            assert headers["X-Polymarket-Secret"] == "test-secret"
            assert headers["X-Polymarket-Passphrase"] == "test-passphrase"

    def test_unauthenticated_request_no_headers(self, client):
        response = httpx.Response(200, json={"markets": []})
        with patch.object(client._client, "get", return_value=response) as mock_get:
            client.get_markets()
            _, kwargs = mock_get.call_args
            headers = kwargs["headers"]
            assert "X-Polymarket-Key" not in headers

    def test_create_order_has_auth_headers(self, client):
        response = httpx.Response(200, json={"orderId": "abc"})
        with patch.object(client._client, "post", return_value=response) as mock_post:
            client.create_order("token123", "BUY", "0.65", "100")
            _, kwargs = mock_post.call_args
            headers = kwargs["headers"]
            assert headers["X-Polymarket-Key"] == "test-key"

    def test_cancel_order_has_auth_headers(self, client):
        response = httpx.Response(200, json={})
        with patch.object(client._client, "delete", return_value=response) as mock_del:
            client.cancel_order("order123")
            _, kwargs = mock_del.call_args
            assert kwargs["headers"]["X-Polymarket-Key"] == "test-key"


class TestMarketParsing:
    """Market list response parsing."""

    def test_get_markets_returns_data(self, client):
        markets_data = {
            "markets": [
                {"id": "1", "question": "Will X happen?", "volume": "1000"},
                {"id": "2", "question": "Will Y happen?", "volume": "2000"},
            ],
            "next_cursor": "cursor123",
        }
        response = httpx.Response(200, json=markets_data)
        with patch.object(client._client, "get", return_value=response):
            result = client.get_markets()
            assert len(result["markets"]) == 2
            assert result["next_cursor"] == "cursor123"

    def test_get_markets_with_cursor(self, client):
        response = httpx.Response(200, json={"markets": []})
        with patch.object(client._client, "get", return_value=response) as mock_get:
            client.get_markets(next_cursor="abc")
            _, kwargs = mock_get.call_args
            assert kwargs["params"]["next_cursor"] == "abc"


class TestOrderCreation:
    """Order creation payload validation."""

    def test_order_payload_structure(self, client):
        response = httpx.Response(200, json={"orderId": "abc"})
        with patch.object(client._client, "post", return_value=response) as mock_post:
            client.create_order(
                token_id="token123",
                side="BUY",
                price="0.65",
                size="100",
                order_type="GTC",
                signed_order={"sig": "0xabc"},
            )
            _, kwargs = mock_post.call_args
            body = kwargs["json"]
            assert body["token_id"] == "token123"
            assert body["side"] == "BUY"
            assert body["price"] == "0.65"
            assert body["size"] == "100"
            assert body["order_type"] == "GTC"
            assert body["signed_order"] == {"sig": "0xabc"}

    def test_order_without_signed_order(self, client):
        response = httpx.Response(200, json={"orderId": "abc"})
        with patch.object(client._client, "post", return_value=response) as mock_post:
            client.create_order("token123", "SELL", "0.35", "50")
            _, kwargs = mock_post.call_args
            body = kwargs["json"]
            assert "signed_order" not in body

    def test_order_default_type_is_gtc(self, client):
        response = httpx.Response(200, json={"orderId": "abc"})
        with patch.object(client._client, "post", return_value=response) as mock_post:
            client.create_order("token123", "BUY", "0.50", "10")
            _, kwargs = mock_post.call_args
            assert kwargs["json"]["order_type"] == "GTC"


class TestAuthFlow:
    """Authentication / key derivation endpoints."""

    def test_authenticate_posts_to_correct_endpoint(self, public_client):
        response = httpx.Response(
            200,
            json={"apiKey": "k", "secret": "s", "passphrase": "p"},
        )
        with patch.object(
            public_client._client, "post", return_value=response
        ) as mock_post:
            result = public_client.authenticate("0xaddr", "0xsig", 123, "nonce1")
            args, kwargs = mock_post.call_args
            assert "/api/v1/polymarket/auth" in args[0]
            assert kwargs["json"]["address"] == "0xaddr"
            assert result["apiKey"] == "k"

    def test_derive_api_key_posts_to_derive_endpoint(self, public_client):
        response = httpx.Response(
            200,
            json={"apiKey": "k2", "secret": "s2", "passphrase": "p2"},
        )
        with patch.object(
            public_client._client, "post", return_value=response
        ) as mock_post:
            result = public_client.derive_api_key("0xaddr", "0xsig", 456, "nonce2")
            args, _ = mock_post.call_args
            assert "/api/v1/polymarket/auth/derive" in args[0]
            assert result["apiKey"] == "k2"


class TestErrorHandling:
    """API error handling."""

    def test_api_error_raises(self, client):
        response = httpx.Response(
            400, json={"error": "bad request"}
        )
        with patch.object(client._client, "get", return_value=response):
            with pytest.raises(TurbineApiError) as exc_info:
                client.get_markets()
            assert exc_info.value.status_code == 400

    def test_has_credentials_property(self):
        full = PolymarketClient(
            host="http://x",
            polymarket_key="k",
            polymarket_secret="s",
            polymarket_passphrase="p",
        )
        assert full.has_credentials is True

        empty = PolymarketClient(host="http://x")
        assert empty.has_credentials is False

    def test_context_manager(self):
        with PolymarketClient(host="http://x") as c:
            assert c._host == "http://x"


class TestURLBuilding:
    """URL construction."""

    def test_host_trailing_slash_stripped(self):
        c = PolymarketClient(host="https://api.test/")
        assert c._host == "https://api.test"

    def test_orderbook_url_contains_token_id(self, client):
        response = httpx.Response(200, json={})
        with patch.object(client._client, "get", return_value=response) as mock_get:
            client.get_orderbook("my-token-id")
            args, _ = mock_get.call_args
            assert "/api/v1/orderbook/my-token-id" in args[0]

    def test_positions_url_contains_address(self, client):
        response = httpx.Response(200, json=[])
        with patch.object(client._client, "get", return_value=response) as mock_get:
            client.get_positions("0xDeaD")
            args, _ = mock_get.call_args
            assert "/api/v1/users/0xDeaD/positions" in args[0]
