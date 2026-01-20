"""Tests for order builder."""

import time

import pytest

from turbine_client.order_builder import (
    OrderBuilder,
    calculate_cost,
    calculate_payout,
    calculate_profit,
    decimal_to_price,
    price_to_decimal,
    shares_to_size,
    size_to_shares,
    validate_price,
    validate_size,
)
from turbine_client.order_builder.helpers import round_price_down, round_price_up
from turbine_client.exceptions import OrderValidationError
from turbine_client.signer import create_signer
from turbine_client.types import Outcome, Side


class TestPriceHelpers:
    """Tests for price conversion helpers."""

    def test_price_to_decimal(self):
        """Test price to decimal conversion."""
        assert float(price_to_decimal(500000)) == pytest.approx(0.5)
        assert float(price_to_decimal(250000)) == pytest.approx(0.25)
        assert float(price_to_decimal(750000)) == pytest.approx(0.75)
        assert float(price_to_decimal(1)) == pytest.approx(0.000001)
        assert float(price_to_decimal(999999)) == pytest.approx(0.999999)

    def test_decimal_to_price(self):
        """Test decimal to price conversion."""
        assert decimal_to_price(0.5) == 500000
        assert decimal_to_price(0.25) == 250000
        assert decimal_to_price(0.75) == 750000
        assert decimal_to_price(0.000001) == 1
        assert decimal_to_price(0.999999) == 999999


class TestSizeHelpers:
    """Tests for size conversion helpers."""

    def test_size_to_shares(self):
        """Test size to shares conversion."""
        assert float(size_to_shares(1000000)) == pytest.approx(1.0)
        assert float(size_to_shares(1500000)) == pytest.approx(1.5)
        assert float(size_to_shares(100000)) == pytest.approx(0.1)

    def test_shares_to_size(self):
        """Test shares to size conversion."""
        assert shares_to_size(1.0) == 1000000
        assert shares_to_size(1.5) == 1500000
        assert shares_to_size(0.1) == 100000


class TestValidation:
    """Tests for validation helpers."""

    def test_validate_price_valid(self):
        """Test that valid prices pass."""
        validate_price(1)
        validate_price(500000)
        validate_price(999999)

    def test_validate_price_too_low(self):
        """Test that price < 1 is rejected."""
        with pytest.raises(OrderValidationError, match="at least 1"):
            validate_price(0)

    def test_validate_price_too_high(self):
        """Test that price > 999999 is rejected."""
        with pytest.raises(OrderValidationError, match="at most 999999"):
            validate_price(1000000)

    def test_validate_price_not_int(self):
        """Test that non-int price is rejected."""
        with pytest.raises(OrderValidationError, match="must be an integer"):
            validate_price(500000.5)  # type: ignore

    def test_validate_size_valid(self):
        """Test that valid sizes pass."""
        validate_size(1)
        validate_size(1000000)
        validate_size(1000000000)

    def test_validate_size_zero(self):
        """Test that size = 0 is rejected."""
        with pytest.raises(OrderValidationError, match="must be positive"):
            validate_size(0)

    def test_validate_size_negative(self):
        """Test that negative size is rejected."""
        with pytest.raises(OrderValidationError, match="must be positive"):
            validate_size(-1)


class TestRounding:
    """Tests for rounding helpers."""

    def test_round_price_down(self):
        """Test rounding price down."""
        assert float(round_price_down(0.5001, 0.0001)) == pytest.approx(0.5001)
        assert float(round_price_down(0.50015, 0.0001)) == pytest.approx(0.5001)
        assert float(round_price_down(0.5, 0.01)) == pytest.approx(0.5)
        assert float(round_price_down(0.505, 0.01)) == pytest.approx(0.50)

    def test_round_price_up(self):
        """Test rounding price up."""
        assert float(round_price_up(0.5001, 0.0001)) == pytest.approx(0.5001)
        assert float(round_price_up(0.50011, 0.0001)) == pytest.approx(0.5002)
        assert float(round_price_up(0.5, 0.01)) == pytest.approx(0.5)
        assert float(round_price_up(0.501, 0.01)) == pytest.approx(0.51)


class TestCostCalculations:
    """Tests for cost/payout calculations."""

    def test_calculate_cost(self):
        """Test cost calculation."""
        # 50% price * 1 share = 0.5 USDC
        assert calculate_cost(500000, 1000000) == 500000

        # 25% price * 2 shares = 0.5 USDC
        assert calculate_cost(250000, 2000000) == 500000

        # 75% price * 10 shares = 7.5 USDC
        assert calculate_cost(750000, 10000000) == 7500000

    def test_calculate_payout(self):
        """Test payout calculation."""
        # Payout = size (1 share = 1 USDC if wins)
        assert calculate_payout(1000000) == 1000000
        assert calculate_payout(5000000) == 5000000

    def test_calculate_profit(self):
        """Test profit calculation."""
        # 50% price * 1 share: cost 0.5, payout 1, profit 0.5
        assert calculate_profit(500000, 1000000) == 500000

        # 25% price * 1 share: cost 0.25, payout 1, profit 0.75
        assert calculate_profit(250000, 1000000) == 750000

        # 75% price * 1 share: cost 0.75, payout 1, profit 0.25
        assert calculate_profit(750000, 1000000) == 250000


class TestOrderBuilder:
    """Tests for OrderBuilder class."""

    @pytest.fixture
    def builder(self, private_key, chain_id):
        """Create an order builder for tests."""
        signer = create_signer(private_key, chain_id)
        return OrderBuilder(signer)

    def test_create_order(self, builder, market_id, test_address):
        """Test creating an order."""
        order = builder.create_order(
            market_id=market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
        )

        assert order.market_id == market_id
        assert order.trader.lower() == test_address.lower()
        assert order.side == 0
        assert order.outcome == 0
        assert order.price == 500000
        assert order.size == 1000000
        assert order.signature is not None
        assert order.order_hash is not None

    def test_create_order_with_expiration(self, builder, market_id):
        """Test creating order with explicit expiration."""
        expiration = int(time.time()) + 86400  # 24 hours

        order = builder.create_order(
            market_id=market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
            expiration=expiration,
        )

        assert order.expiration == expiration

    def test_create_order_default_expiration(self, builder, market_id):
        """Test that default expiration is ~1 hour from now."""
        now = int(time.time())

        order = builder.create_order(
            market_id=market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
        )

        # Expiration should be within 1 hour + 10 seconds tolerance
        assert now + 3590 < order.expiration < now + 3610

    def test_create_limit_buy(self, builder, market_id):
        """Test creating a limit buy order."""
        order = builder.create_limit_buy(
            market_id=market_id,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
        )

        assert order.side == 0  # BUY

    def test_create_limit_sell(self, builder, market_id):
        """Test creating a limit sell order."""
        order = builder.create_limit_sell(
            market_id=market_id,
            outcome=Outcome.NO,
            price=300000,
            size=2000000,
        )

        assert order.side == 1  # SELL
        assert order.outcome == 1  # NO

    def test_invalid_market_id_empty(self, builder):
        """Test that empty market ID is rejected."""
        with pytest.raises(OrderValidationError, match="market_id is required"):
            builder.create_order(
                market_id="",
                side=Side.BUY,
                outcome=Outcome.YES,
                price=500000,
                size=1000000,
            )

    def test_invalid_market_id_not_hex(self, builder):
        """Test that non-hex market ID is rejected."""
        with pytest.raises(OrderValidationError, match="valid hex string"):
            builder.create_order(
                market_id="not-valid-hex",
                side=Side.BUY,
                outcome=Outcome.YES,
                price=500000,
                size=1000000,
            )

    def test_builder_address(self, builder, test_address):
        """Test that builder has correct address."""
        assert builder.address.lower() == test_address.lower()

    def test_builder_chain_id(self, builder, chain_id):
        """Test that builder has correct chain ID."""
        assert builder.chain_id == chain_id
