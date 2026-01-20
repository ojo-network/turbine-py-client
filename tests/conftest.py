"""Pytest fixtures for turbine-client tests."""

import pytest
from nacl.signing import SigningKey

from turbine_client.constants import BASE_SEPOLIA


# Test wallet private key (DO NOT use in production)
TEST_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

# Generate an Ed25519 key pair for API authentication
_signing_key = SigningKey.generate()
TEST_API_PRIVATE_KEY = _signing_key.encode().hex()
TEST_API_KEY_ID = "test-key-id-12345"


@pytest.fixture
def private_key() -> str:
    """Test wallet private key."""
    return TEST_PRIVATE_KEY


@pytest.fixture
def chain_id() -> int:
    """Test chain ID."""
    return BASE_SEPOLIA


@pytest.fixture
def api_key_id() -> str:
    """Test API key ID."""
    return TEST_API_KEY_ID


@pytest.fixture
def api_private_key() -> str:
    """Test API private key (Ed25519)."""
    return TEST_API_PRIVATE_KEY


@pytest.fixture
def market_id() -> str:
    """Test market ID."""
    return "0x" + "ab" * 32


@pytest.fixture
def test_address() -> str:
    """Test Ethereum address."""
    return "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


@pytest.fixture
def host() -> str:
    """Test API host."""
    return "https://api.turbinefi.com"


@pytest.fixture
def settlement_address() -> str:
    """Test settlement contract address."""
    return "0xf960d03967C59d516079c44c97829F43f5618aAF"
