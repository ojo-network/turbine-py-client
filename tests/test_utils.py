"""Tests for utility functions."""

import os

import pytest

from turbine_client.utils import (
    calculate_american_odds,
    calculate_implied_probability,
    calculate_odds,
    dict_to_camel_case,
    dict_to_snake_case,
    format_price,
    format_size,
    format_usdc,
    market_id_to_hex,
    parse_market_id,
    validate_address,
)


class TestValidateAddress:
    """Tests for address validation."""

    def test_valid_address(self, test_address):
        """Test validating a valid address."""
        result = validate_address(test_address)
        assert result == test_address

    def test_lowercase_address(self, test_address):
        """Test validating a lowercase address."""
        result = validate_address(test_address.lower())
        # Should return checksummed
        assert result == test_address

    def test_invalid_address(self):
        """Test that invalid address raises error."""
        with pytest.raises(ValueError, match="Invalid Ethereum address"):
            validate_address("not-an-address")

    def test_short_address(self):
        """Test that short address raises error."""
        with pytest.raises(ValueError, match="Invalid Ethereum address"):
            validate_address("0x1234")


class TestFormatPrice:
    """Tests for price formatting."""

    def test_format_price_50(self):
        """Test formatting 50% price."""
        assert format_price(500000) == "50.00%"

    def test_format_price_25(self):
        """Test formatting 25% price."""
        assert format_price(250000) == "25.00%"

    def test_format_price_75(self):
        """Test formatting 75% price."""
        assert format_price(750000) == "75.00%"

    def test_format_price_decimal(self):
        """Test formatting price with decimal."""
        assert format_price(555555) == "55.56%"


class TestFormatSize:
    """Tests for size formatting."""

    def test_format_size_whole(self):
        """Test formatting whole number."""
        assert format_size(1000000) == "1.00"

    def test_format_size_fraction(self):
        """Test formatting fraction."""
        assert format_size(1500000) == "1.50"

    def test_format_size_large(self):
        """Test formatting large number."""
        assert format_size(10000000000) == "10,000"

    def test_format_size_small(self):
        """Test formatting small number."""
        assert format_size(1000) == "0.001"


class TestFormatUsdc:
    """Tests for USDC formatting."""

    def test_format_usdc_dollar(self):
        """Test formatting $1."""
        assert format_usdc(1000000) == "$1.00"

    def test_format_usdc_cents(self):
        """Test formatting $0.50."""
        assert format_usdc(500000) == "$0.50"

    def test_format_usdc_large(self):
        """Test formatting large amount."""
        assert format_usdc(1000000000) == "$1,000.00"

    def test_format_usdc_small(self):
        """Test formatting small amount."""
        assert format_usdc(100) == "$0.0001"


class TestMarketIdParsing:
    """Tests for market ID parsing."""

    def test_parse_market_id_with_prefix(self):
        """Test parsing market ID with 0x prefix."""
        market_id = "0x" + "ab" * 32
        result = parse_market_id(market_id)
        assert len(result) == 32
        assert result == bytes.fromhex("ab" * 32)

    def test_parse_market_id_without_prefix(self):
        """Test parsing market ID without 0x prefix."""
        market_id = "ab" * 32
        result = parse_market_id(market_id)
        assert len(result) == 32
        assert result == bytes.fromhex("ab" * 32)

    def test_parse_market_id_short(self):
        """Test parsing short market ID (padded)."""
        market_id = "0x123"
        result = parse_market_id(market_id)
        assert len(result) == 32
        assert result.hex().endswith("123")

    def test_market_id_to_hex(self):
        """Test converting bytes to hex string."""
        market_bytes = bytes.fromhex("ab" * 32)
        result = market_id_to_hex(market_bytes)
        assert result == "0x" + "ab" * 32


class TestOddsCalculations:
    """Tests for odds calculations."""

    def test_implied_probability_50(self):
        """Test 50% implied probability."""
        assert calculate_implied_probability(500000) == pytest.approx(0.5)

    def test_implied_probability_25(self):
        """Test 25% implied probability."""
        assert calculate_implied_probability(250000) == pytest.approx(0.25)

    def test_decimal_odds_50(self):
        """Test decimal odds at 50%."""
        assert calculate_odds(500000) == pytest.approx(2.0)

    def test_decimal_odds_25(self):
        """Test decimal odds at 25%."""
        assert calculate_odds(250000) == pytest.approx(4.0)

    def test_decimal_odds_75(self):
        """Test decimal odds at 75%."""
        assert calculate_odds(750000) == pytest.approx(1.333, rel=0.01)

    def test_american_odds_50(self):
        """Test American odds at 50%."""
        assert calculate_american_odds(500000) == -100

    def test_american_odds_25(self):
        """Test American odds at 25%."""
        assert calculate_american_odds(250000) == 300

    def test_american_odds_75(self):
        """Test American odds at 75%."""
        assert calculate_american_odds(750000) == -300


class TestDictConversion:
    """Tests for dictionary key conversion."""

    def test_to_camel_case_simple(self):
        """Test simple snake_case to camelCase conversion."""
        result = dict_to_camel_case({"market_id": "123", "user_address": "0x..."})
        assert result == {"marketId": "123", "userAddress": "0x..."}

    def test_to_camel_case_nested(self):
        """Test nested conversion."""
        result = dict_to_camel_case({
            "outer_key": {
                "inner_key": "value"
            }
        })
        assert result == {"outerKey": {"innerKey": "value"}}

    def test_to_camel_case_list(self):
        """Test list conversion."""
        result = dict_to_camel_case({
            "items": [
                {"item_name": "a"},
                {"item_name": "b"},
            ]
        })
        assert result == {"items": [{"itemName": "a"}, {"itemName": "b"}]}

    def test_to_snake_case_simple(self):
        """Test simple camelCase to snake_case conversion."""
        result = dict_to_snake_case({"marketId": "123", "userAddress": "0x..."})
        assert result == {"market_id": "123", "user_address": "0x..."}

    def test_to_snake_case_nested(self):
        """Test nested conversion."""
        result = dict_to_snake_case({
            "outerKey": {
                "innerKey": "value"
            }
        })
        assert result == {"outer_key": {"inner_key": "value"}}

    def test_to_snake_case_list(self):
        """Test list conversion."""
        result = dict_to_snake_case({
            "items": [
                {"itemName": "a"},
                {"itemName": "b"},
            ]
        })
        assert result == {"items": [{"item_name": "a"}, {"item_name": "b"}]}
