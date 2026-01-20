"""Tests for data types."""

import pytest

from turbine_client.types import (
    Market,
    Order,
    OrderArgs,
    OrderBookSnapshot,
    Outcome,
    Position,
    PriceLevel,
    Side,
    SignedOrder,
    Trade,
)


class TestSideOutcome:
    """Tests for Side and Outcome enums."""

    def test_side_values(self):
        """Test Side enum values."""
        assert Side.BUY == 0
        assert Side.SELL == 1

    def test_outcome_values(self):
        """Test Outcome enum values."""
        assert Outcome.YES == 0
        assert Outcome.NO == 1

    def test_side_int_conversion(self):
        """Test Side can be converted to int."""
        assert int(Side.BUY) == 0
        assert int(Side.SELL) == 1

    def test_outcome_int_conversion(self):
        """Test Outcome can be converted to int."""
        assert int(Outcome.YES) == 0
        assert int(Outcome.NO) == 1


class TestOrderArgs:
    """Tests for OrderArgs dataclass."""

    def test_valid_order_args(self, market_id):
        """Test creating valid OrderArgs."""
        args = OrderArgs(
            market_id=market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
            expiration=1735689600,
        )
        assert args.market_id == market_id
        assert args.side == Side.BUY
        assert args.outcome == Outcome.YES
        assert args.price == 500000
        assert args.size == 1000000
        assert args.nonce == 0  # Default
        assert args.maker_fee_recipient == "0x0000000000000000000000000000000000000000"

    def test_invalid_price_too_low(self, market_id):
        """Test that price < 1 is rejected."""
        with pytest.raises(ValueError, match="Price must be between"):
            OrderArgs(
                market_id=market_id,
                side=Side.BUY,
                outcome=Outcome.YES,
                price=0,
                size=1000000,
                expiration=1735689600,
            )

    def test_invalid_price_too_high(self, market_id):
        """Test that price > 999999 is rejected."""
        with pytest.raises(ValueError, match="Price must be between"):
            OrderArgs(
                market_id=market_id,
                side=Side.BUY,
                outcome=Outcome.YES,
                price=1000000,
                size=1000000,
                expiration=1735689600,
            )

    def test_invalid_size(self, market_id):
        """Test that size <= 0 is rejected."""
        with pytest.raises(ValueError, match="Size must be positive"):
            OrderArgs(
                market_id=market_id,
                side=Side.BUY,
                outcome=Outcome.YES,
                price=500000,
                size=0,
                expiration=1735689600,
            )

    def test_invalid_expiration(self, market_id):
        """Test that expiration <= 0 is rejected."""
        with pytest.raises(ValueError, match="Expiration must be positive"):
            OrderArgs(
                market_id=market_id,
                side=Side.BUY,
                outcome=Outcome.YES,
                price=500000,
                size=1000000,
                expiration=0,
            )


class TestSignedOrder:
    """Tests for SignedOrder dataclass."""

    def test_to_dict(self, market_id, test_address):
        """Test converting SignedOrder to API dict format."""
        order = SignedOrder(
            market_id=market_id,
            trader=test_address,
            side=0,
            outcome=0,
            price=500000,
            size=1000000,
            nonce=12345,
            expiration=1735689600,
            maker_fee_recipient="0x0000000000000000000000000000000000000000",
            signature="0x" + "ab" * 65,
            order_hash="0x" + "cd" * 32,
        )

        result = order.to_dict()

        assert result["order"]["marketId"] == market_id
        assert result["order"]["trader"] == test_address
        assert result["order"]["side"] == 0
        assert result["order"]["outcome"] == 0
        assert result["order"]["price"] == 500000
        assert result["order"]["size"] == 1000000
        assert result["order"]["nonce"] == 12345
        assert result["signature"] == "0x" + "ab" * 65


class TestPriceLevel:
    """Tests for PriceLevel dataclass."""

    def test_from_dict(self):
        """Test creating PriceLevel from dict."""
        data = {"price": "500000", "size": "10000000"}
        level = PriceLevel.from_dict(data)
        assert level.price == 500000
        assert level.size == 10000000

    def test_from_dict_int_values(self):
        """Test creating PriceLevel from dict with int values."""
        data = {"price": 500000, "size": 10000000}
        level = PriceLevel.from_dict(data)
        assert level.price == 500000
        assert level.size == 10000000


class TestOrderBookSnapshot:
    """Tests for OrderBookSnapshot dataclass."""

    def test_from_dict(self, market_id):
        """Test creating OrderBookSnapshot from dict."""
        data = {
            "marketId": market_id,
            "bids": [
                {"price": 490000, "size": 5000000},
                {"price": 480000, "size": 10000000},
            ],
            "asks": [
                {"price": 510000, "size": 5000000},
                {"price": 520000, "size": 8000000},
            ],
            "lastUpdate": 1735689600,
        }
        snapshot = OrderBookSnapshot.from_dict(data)

        assert snapshot.market_id == market_id
        assert len(snapshot.bids) == 2
        assert len(snapshot.asks) == 2
        assert snapshot.bids[0].price == 490000
        assert snapshot.asks[0].price == 510000
        assert snapshot.last_update == 1735689600


class TestTrade:
    """Tests for Trade dataclass."""

    def test_from_dict(self, market_id, test_address):
        """Test creating Trade from dict."""
        data = {
            "marketId": market_id,
            "price": 500000,
            "size": 1000000,
            "outcome": 0,
            "side": 0,
            "maker": test_address,
            "taker": "0x" + "11" * 20,
            "timestamp": 1735689600,
            "tradeHash": "0x" + "ab" * 32,
        }
        trade = Trade.from_dict(data)

        assert trade.market_id == market_id
        assert trade.price == 500000
        assert trade.size == 1000000
        assert trade.outcome == 0
        assert trade.side == 0
        assert trade.maker == test_address
        assert trade.timestamp == 1735689600


class TestPosition:
    """Tests for Position dataclass."""

    def test_from_dict(self, market_id, test_address):
        """Test creating Position from dict."""
        data = {
            "marketId": market_id,
            "userAddress": test_address,
            "yesShares": 5000000,
            "noShares": 0,
            "invested": 2500000,
            "lastTradePrice": 500000,
        }
        position = Position.from_dict(data)

        assert position.market_id == market_id
        assert position.user_address == test_address
        assert position.yes_shares == 5000000
        assert position.no_shares == 0
        assert position.invested == 2500000


class TestMarket:
    """Tests for Market dataclass."""

    def test_from_dict(self, market_id):
        """Test creating Market from dict."""
        data = {
            "id": market_id,
            "question": "Will BTC reach $100k?",
            "description": "Bitcoin price prediction",
            "category": "crypto",
            "expirationTime": 1735689600,
            "contractAddress": "0x" + "aa" * 20,
            "chainId": 137,
            "resolved": False,
            "winningOutcome": None,
        }
        market = Market.from_dict(data)

        assert market.id == market_id
        assert market.question == "Will BTC reach $100k?"
        assert market.category == "crypto"
        assert market.chain_id == 137
        assert market.resolved is False
        assert market.winning_outcome is None

    def test_from_dict_resolved(self, market_id):
        """Test creating resolved Market from dict."""
        data = {
            "id": market_id,
            "question": "Will BTC reach $100k?",
            "description": "",
            "category": "crypto",
            "expirationTime": 1735689600,
            "contractAddress": "0x" + "aa" * 20,
            "chainId": 137,
            "resolved": True,
            "winningOutcome": 0,  # YES won
        }
        market = Market.from_dict(data)

        assert market.resolved is True
        assert market.winning_outcome == 0
