"""Tests for convenience methods (buy/sell, from_env, parse helpers)."""

import os
import pytest
import respx
from httpx import Response

from turbine_client import TurbineClient
from turbine_client.types import Outcome


class TestParseOutcome:
    """Tests for _parse_outcome."""

    def test_enum_passthrough(self):
        assert TurbineClient._parse_outcome(Outcome.YES) == Outcome.YES
        assert TurbineClient._parse_outcome(Outcome.NO) == Outcome.NO

    def test_string_yes(self):
        assert TurbineClient._parse_outcome("yes") == Outcome.YES
        assert TurbineClient._parse_outcome("YES") == Outcome.YES
        assert TurbineClient._parse_outcome("y") == Outcome.YES

    def test_string_no(self):
        assert TurbineClient._parse_outcome("no") == Outcome.NO
        assert TurbineClient._parse_outcome("NO") == Outcome.NO
        assert TurbineClient._parse_outcome("n") == Outcome.NO

    def test_invalid_string(self):
        with pytest.raises(ValueError, match="Invalid outcome"):
            TurbineClient._parse_outcome("maybe")

    def test_invalid_type(self):
        with pytest.raises(TypeError):
            TurbineClient._parse_outcome(123)  # type: ignore


class TestParsePrice:
    """Tests for _parse_price."""

    def test_int_passthrough(self):
        assert TurbineClient._parse_price(500000) == 500000

    def test_float_probability(self):
        assert TurbineClient._parse_price(0.50) == 500000
        assert TurbineClient._parse_price(0.25) == 250000
        assert TurbineClient._parse_price(0.99) == 990000

    def test_float_percentage(self):
        assert TurbineClient._parse_price(50.0) == 500000
        assert TurbineClient._parse_price(25.0) == 250000

    def test_float_ambiguous(self):
        with pytest.raises(ValueError, match="ambiguous"):
            TurbineClient._parse_price(100.0)


class TestParseSize:
    """Tests for _parse_size."""

    def test_int_passthrough(self):
        assert TurbineClient._parse_size(1000000) == 1000000

    def test_float_shares(self):
        assert TurbineClient._parse_size(1.0) == 1000000
        assert TurbineClient._parse_size(1.5) == 1500000
        assert TurbineClient._parse_size(0.1) == 100000


class TestDefaultParams:
    """Tests for default host and chain_id."""

    def test_default_host(self):
        client = TurbineClient()
        assert client.host == "https://api.turbinefi.com"
        client.close()

    def test_default_chain_id(self):
        client = TurbineClient()
        assert client.chain_id == 137
        client.close()

    def test_override_host(self):
        client = TurbineClient(host="https://custom.api.com")
        assert client.host == "https://custom.api.com"
        client.close()


class TestFromEnv:
    """Tests for from_env class method."""

    def test_from_env_no_vars(self):
        """Should create a public client when no env vars set."""
        # Clear any existing vars
        env_backup = {}
        for key in ["TURBINE_PRIVATE_KEY", "TURBINE_API_KEY_ID", "TURBINE_API_PRIVATE_KEY"]:
            env_backup[key] = os.environ.pop(key, None)

        try:
            client = TurbineClient.from_env(dotenv=False)
            assert client.can_sign is False
            assert client.has_auth is False
            client.close()
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val


class TestBuySell:
    """Tests for buy/sell convenience methods."""

    @pytest.fixture
    def client(self, host, chain_id, private_key, api_key_id, api_private_key):
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
    def test_buy_with_floats(self, client, host, market_id, settlement_address):
        """Test buy() with float price and size."""
        # Mock stats endpoint (for settlement address lookup)
        respx.get(f"{host}/api/v1/stats/{market_id}").mock(
            return_value=Response(200, json={
                "marketId": market_id,
                "contractAddress": "0x" + "aa" * 20,
                "settlementAddress": settlement_address,
                "lastPrice": 500000,
                "totalVolume": 0,
                "volume24h": 0,
            })
        )
        # Mock order submission
        respx.post(f"{host}/api/v1/orders").mock(
            return_value=Response(200, json={"orderHash": "0x" + "ab" * 32})
        )

        result = client.buy(market_id, "yes", price=0.50, size=1.0)
        assert "orderHash" in result

    @respx.mock
    def test_sell_with_string_outcome(self, client, host, market_id, settlement_address):
        """Test sell() with string outcome."""
        respx.get(f"{host}/api/v1/stats/{market_id}").mock(
            return_value=Response(200, json={
                "marketId": market_id,
                "contractAddress": "0x" + "aa" * 20,
                "settlementAddress": settlement_address,
                "lastPrice": 500000,
                "totalVolume": 0,
                "volume24h": 0,
            })
        )
        respx.post(f"{host}/api/v1/orders").mock(
            return_value=Response(200, json={"orderHash": "0x" + "cd" * 32})
        )

        result = client.sell(market_id, "no", price=0.60, size=2.0)
        assert "orderHash" in result
