"""Tests for EIP-712 signing."""

import pytest
from eth_utils import to_checksum_address

from turbine_client.signer import Signer, create_signer
from turbine_client.types import OrderArgs, Outcome, Side
from turbine_client.exceptions import SignatureError


class TestSigner:
    """Tests for the Signer class."""

    def test_create_signer(self, private_key, chain_id):
        """Test creating a signer."""
        signer = create_signer(private_key, chain_id)
        assert signer is not None
        assert signer.chain_id == chain_id

    def test_signer_address(self, private_key, chain_id, test_address):
        """Test that signer has correct address."""
        signer = create_signer(private_key, chain_id)
        assert signer.address == to_checksum_address(test_address)

    def test_signer_without_0x_prefix(self, chain_id, test_address):
        """Test creating signer with private key without 0x prefix."""
        private_key_no_prefix = "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        signer = create_signer(private_key_no_prefix, chain_id)
        assert signer.address == to_checksum_address(test_address)

    def test_get_domain(self, private_key, chain_id):
        """Test getting EIP-712 domain."""
        signer = create_signer(private_key, chain_id)
        domain = signer.get_domain()

        assert domain["name"] == "Turbine"
        assert domain["version"] == "1"
        assert domain["chainId"] == chain_id
        assert "verifyingContract" in domain

    def test_sign_order(self, private_key, chain_id, market_id, test_address):
        """Test signing an order."""
        signer = create_signer(private_key, chain_id)

        order_args = OrderArgs(
            market_id=market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
            expiration=1735689600,
        )

        signed_order = signer.sign_order(order_args)

        assert signed_order.market_id == market_id
        assert signed_order.trader == to_checksum_address(test_address)
        assert signed_order.side == 0
        assert signed_order.outcome == 0
        assert signed_order.price == 500000
        assert signed_order.size == 1000000
        assert signed_order.nonce != 0  # Auto-generated
        assert signed_order.expiration == 1735689600
        assert signed_order.signature.startswith("0x") or len(signed_order.signature) > 0
        assert signed_order.order_hash.startswith("0x")

    def test_sign_order_with_nonce(self, private_key, chain_id, market_id):
        """Test signing an order with explicit nonce."""
        signer = create_signer(private_key, chain_id)

        order_args = OrderArgs(
            market_id=market_id,
            side=Side.SELL,
            outcome=Outcome.NO,
            price=250000,
            size=5000000,
            expiration=1735689600,
            nonce=12345,
        )

        signed_order = signer.sign_order(order_args)

        assert signed_order.nonce == 12345

    def test_sign_order_deterministic(self, private_key, chain_id, market_id):
        """Test that signing with same inputs produces same signature."""
        signer = create_signer(private_key, chain_id)

        order_args = OrderArgs(
            market_id=market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
            expiration=1735689600,
            nonce=99999,
        )

        signed1 = signer.sign_order(order_args)
        signed2 = signer.sign_order(order_args)

        assert signed1.signature == signed2.signature
        assert signed1.order_hash == signed2.order_hash

    def test_different_orders_different_signatures(self, private_key, chain_id, market_id):
        """Test that different orders produce different signatures."""
        signer = create_signer(private_key, chain_id)

        order_args1 = OrderArgs(
            market_id=market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
            expiration=1735689600,
            nonce=1,
        )

        order_args2 = OrderArgs(
            market_id=market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=600000,  # Different price
            size=1000000,
            expiration=1735689600,
            nonce=1,
        )

        signed1 = signer.sign_order(order_args1)
        signed2 = signer.sign_order(order_args2)

        assert signed1.signature != signed2.signature
        assert signed1.order_hash != signed2.order_hash

    def test_sign_order_with_market_id_no_prefix(self, private_key, chain_id, test_address):
        """Test signing with market ID without 0x prefix."""
        signer = create_signer(private_key, chain_id)

        market_id = "12" * 32  # No 0x prefix

        order_args = OrderArgs(
            market_id=market_id,
            side=Side.BUY,
            outcome=Outcome.YES,
            price=500000,
            size=1000000,
            expiration=1735689600,
        )

        signed_order = signer.sign_order(order_args)
        assert signed_order is not None
        assert signed_order.market_id == market_id
