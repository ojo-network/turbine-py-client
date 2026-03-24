"""
Polymarket authentication helpers.

Handles the full EIP-712 signing flow to derive Polymarket API credentials
through Turbine's proxy, so users don't need to manually obtain keys.
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

from eth_account import Account
from eth_account.messages import encode_typed_data


# Polymarket L1 auth EIP-712 domain and types
POLYMARKET_AUTH_DOMAIN = {
    "name": "ClobAuthDomain",
    "version": "1",
    "chainId": 137,
}

POLYMARKET_AUTH_TYPES = {
    "ClobAuth": [
        {"name": "address", "type": "address"},
        {"name": "timestamp", "type": "string"},
        {"name": "nonce", "type": "uint256"},
        {"name": "message", "type": "string"},
    ],
}


def sign_clob_auth_message(
    private_key: str,
    nonce: int = 0,
    timestamp: Optional[int] = None,
) -> Tuple[str, str, int]:
    """Sign the Polymarket CLOB authentication message.

    Produces the EIP-712 signature needed to create or derive
    Polymarket API credentials via Turbine's ``/api/v1/polymarket/auth`` endpoint.

    Args:
        private_key: Hex-encoded wallet private key (with or without ``0x`` prefix).
        nonce: Nonce for the auth message (default 0).
        timestamp: Unix timestamp. Defaults to current time.

    Returns:
        Tuple of ``(address, signature, timestamp)``.
    """
    if timestamp is None:
        timestamp = int(time.time())

    account = Account.from_key(private_key)
    address = account.address

    message_value = {
        "address": address,
        "timestamp": str(timestamp),
        "nonce": nonce,
        "message": "This message attests that I control the given wallet",
    }

    signable = encode_typed_data(
        domain_data=POLYMARKET_AUTH_DOMAIN,
        message_types=POLYMARKET_AUTH_TYPES,
        message_data=message_value,
        primary_type="ClobAuth",
    )

    signed = account.sign_message(signable)
    return address, signed.signature.hex(), timestamp


def get_polymarket_credentials(
    client: "PolymarketClient",  # noqa: F821
    private_key: str,
    nonce: int = 0,
) -> Dict[str, str]:
    """Complete the full Polymarket auth flow in one call.

    Signs the EIP-712 auth message with the given private key and calls
    Turbine's Polymarket auth proxy to obtain API credentials.

    Args:
        client: A ``PolymarketClient`` instance (credentials not required yet).
        private_key: Hex-encoded wallet private key.
        nonce: Auth nonce (default 0).

    Returns:
        Dict with ``apiKey``, ``secret``, and ``passphrase``.

    Example::

        from turbine_client.polymarket import PolymarketClient
        from turbine_client.polymarket_auth import get_polymarket_credentials

        client = PolymarketClient(host="https://api.turbinefi.com")
        creds = get_polymarket_credentials(client, private_key="0x...")
        # creds = {"apiKey": "...", "secret": "...", "passphrase": "..."}

        # Now create an authenticated client
        client = PolymarketClient(
            host="https://api.turbinefi.com",
            polymarket_key=creds["apiKey"],
            polymarket_secret=creds["secret"],
            polymarket_passphrase=creds["passphrase"],
            private_key=private_key,
        )
    """
    address, signature, timestamp = sign_clob_auth_message(private_key, nonce=nonce)
    return client.authenticate(
        address=address,
        signature=signature,
        timestamp=timestamp,
        nonce=str(nonce),
    )
