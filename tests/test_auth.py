"""Tests for bearer token authentication."""

import base64
import json
import time

import pytest

from turbine_client.auth import (
    ApiCredentials,
    BearerTokenAuth,
    create_bearer_auth,
    verify_token_timestamp,
)
from turbine_client.exceptions import AuthenticationError


class TestApiCredentials:
    """Tests for ApiCredentials."""

    def test_valid_credentials(self, api_key_id, api_private_key):
        """Test creating valid credentials."""
        creds = ApiCredentials(key_id=api_key_id, private_key=api_private_key)
        assert creds.key_id == api_key_id
        assert creds.private_key == api_private_key

    def test_missing_key_id(self, api_private_key):
        """Test that missing key_id raises error."""
        with pytest.raises(ValueError, match="key_id is required"):
            ApiCredentials(key_id="", private_key=api_private_key)

    def test_missing_private_key(self, api_key_id):
        """Test that missing private_key raises error."""
        with pytest.raises(ValueError, match="private_key is required"):
            ApiCredentials(key_id=api_key_id, private_key="")


class TestBearerTokenAuth:
    """Tests for BearerTokenAuth."""

    def test_create_bearer_auth(self, api_key_id, api_private_key):
        """Test creating bearer token auth."""
        auth = create_bearer_auth(api_key_id, api_private_key)
        assert auth is not None

    def test_generate_token(self, api_key_id, api_private_key):
        """Test generating a bearer token."""
        auth = create_bearer_auth(api_key_id, api_private_key)
        token = auth.generate_token()

        # Token should have two parts separated by .
        parts = token.split(".")
        assert len(parts) == 2

        # First part should be base64url-encoded JSON
        payload_b64 = parts[0]
        # Add padding
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += "=" * padding
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)

        assert payload["kid"] == api_key_id
        assert "ts" in payload
        assert "n" in payload

    def test_get_auth_header(self, api_key_id, api_private_key):
        """Test getting auth header."""
        auth = create_bearer_auth(api_key_id, api_private_key)
        headers = auth.get_auth_header()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    def test_token_timestamp_is_current(self, api_key_id, api_private_key):
        """Test that token timestamp is current."""
        auth = create_bearer_auth(api_key_id, api_private_key)
        token = auth.generate_token()

        # Parse token
        parts = token.split(".")
        payload_b64 = parts[0]
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += "=" * padding
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)

        # Timestamp should be within a few seconds of now
        assert abs(time.time() - payload["ts"]) < 5

    def test_tokens_have_unique_nonces(self, api_key_id, api_private_key):
        """Test that tokens have unique nonces."""
        auth = create_bearer_auth(api_key_id, api_private_key)

        tokens = [auth.generate_token() for _ in range(10)]

        # Extract nonces
        nonces = []
        for token in tokens:
            parts = token.split(".")
            payload_b64 = parts[0]
            padding = 4 - (len(payload_b64) % 4)
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            nonces.append(payload["n"])

        # All nonces should be unique
        assert len(set(nonces)) == len(nonces)

    def test_invalid_private_key(self, api_key_id):
        """Test that invalid private key raises error."""
        with pytest.raises(AuthenticationError, match="Invalid Ed25519 private key"):
            create_bearer_auth(api_key_id, "not-valid-hex")

    def test_invalid_private_key_length(self, api_key_id):
        """Test that wrong length private key raises error."""
        with pytest.raises(AuthenticationError, match="Invalid Ed25519 private key"):
            create_bearer_auth(api_key_id, "0x" + "ab" * 16)  # Too short


class TestVerifyTokenTimestamp:
    """Tests for verify_token_timestamp."""

    def test_valid_timestamp(self, api_key_id, api_private_key):
        """Test that fresh token passes verification."""
        auth = create_bearer_auth(api_key_id, api_private_key)
        token = auth.generate_token()

        assert verify_token_timestamp(token) is True

    def test_invalid_token_format(self):
        """Test that invalid token format fails."""
        assert verify_token_timestamp("invalid-token") is False

    def test_invalid_base64(self):
        """Test that invalid base64 fails."""
        assert verify_token_timestamp("!!!.!!!") is False
