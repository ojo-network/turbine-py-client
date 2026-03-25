#!/usr/bin/env python3
"""
Locus x402 authentication — sign up or top up using a Polygon wallet.

Usage:
    python scripts/locus_x402.py sign-up
    python scripts/locus_x402.py top-up 5.00

Reads TURBINE_PRIVATE_KEY from .env or environment.
Outputs JSON to stdout. Saves JWT to /tmp/locus-token.txt.
"""
import base64
import json
import os
import secrets
import sys
import time

import httpx
from dotenv import load_dotenv
from eth_account import Account

BASE_URL = "https://api.buildwithlocus.com/v1"

# USDC on Polygon — EIP-712 domain for EIP-3009 signing
USDC_NAME = "USD Coin"
USDC_VERSION = "2"
POLYGON_CHAIN_ID = 137
# Note: The actual USDC address comes from the 402 payment requirements,
# but this is the expected Polygon USDC address for reference
POLYGON_USDC = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"


def _load_private_key() -> str:
    """Load TURBINE_PRIVATE_KEY from .env or environment."""
    load_dotenv()
    pk = os.environ.get("TURBINE_PRIVATE_KEY")
    if not pk:
        print("Error: TURBINE_PRIVATE_KEY not set in .env or environment", file=sys.stderr)
        sys.exit(1)
    return pk


def _sign_transfer_authorization(
    account, accept: dict
) -> dict:
    """Sign an EIP-3009 TransferWithAuthorization and build x402 V2 payload.

    Args:
        account: eth_account Account object.
        accept: The selected entry from the 402 response's "accepts" array.

    Returns:
        Complete x402 V2 PaymentPayload dict ready for base64 encoding.
    """
    recipient = accept["payTo"]
    amount = int(accept["amount"])
    asset = accept["asset"]
    extra = accept.get("extra", {})
    name = extra.get("name", USDC_NAME)
    version = extra.get("version", USDC_VERSION)

    nonce = "0x" + secrets.token_hex(32)  # EIP-3009 uses random bytes32 nonce
    valid_after = 0
    valid_before = int(time.time()) + 3600  # 1 hour

    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": name,
            "version": version,
            "chainId": POLYGON_CHAIN_ID,
            "verifyingContract": asset,
        },
        "message": {
            "from": account.address,
            "to": recipient,
            "value": amount,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce,
        },
    }

    signed = Account.sign_typed_data(account.key, full_message=typed_data)

    # x402 V2 PaymentPayload: must include "accepted" echoing back the requirements
    return {
        "x402Version": 2,
        "payload": {
            "signature": "0x" + signed.signature.hex(),
            "authorization": {
                "from": account.address,
                "to": recipient,
                "value": str(amount),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": nonce,
            },
        },
        "accepted": accept,
    }


def _x402_handshake(endpoint: str, body: dict, private_key: str) -> dict:
    """Full x402 handshake: POST → 402 → sign → retry → response."""
    account = Account.from_key(private_key)

    resp = httpx.post(f"{BASE_URL}{endpoint}", json=body, timeout=30)

    if resp.status_code == 200:
        return resp.json()

    if resp.status_code != 402:
        print(f"Error: unexpected status {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)

    # Parse payment requirements from PAYMENT-REQUIRED header (base64 JSON)
    raw = resp.headers.get("payment-required", "")
    if not raw:
        print("Error: no payment-required header in 402 response", file=sys.stderr)
        print(f"Headers: {dict(resp.headers)}", file=sys.stderr)
        sys.exit(1)

    # x402 V2: payment options are in the "accepts" array
    requirements = json.loads(base64.b64decode(raw))
    accept = requirements["accepts"][0]

    # Sign EIP-3009 TransferWithAuthorization and build V2 payload
    payment = _sign_transfer_authorization(account, accept)
    payment_header = base64.b64encode(json.dumps(payment).encode()).decode()

    # Retry with signed payment in PAYMENT-SIGNATURE header
    resp = httpx.post(
        f"{BASE_URL}{endpoint}",
        json=body,
        headers={"PAYMENT-SIGNATURE": payment_header},
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"Error after payment: {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)

    return resp.json()


def sign_up():
    pk = _load_private_key()
    result = _x402_handshake("/auth/x402-sign-up", {}, pk)

    # Save JWT for subsequent use
    jwt = result.get("jwt", "")
    if jwt:
        with open("/tmp/locus-token.txt", "w") as f:
            f.write(jwt)

    print(json.dumps(result, indent=2))


def top_up(amount: float):
    pk = _load_private_key()
    result = _x402_handshake("/billing/x402-top-up", {"amount": amount}, pk)

    jwt = result.get("jwt", "")
    if jwt:
        with open("/tmp/locus-token.txt", "w") as f:
            f.write(jwt)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: locus_x402.py <sign-up|top-up> [amount]", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "sign-up":
        sign_up()
    elif cmd == "top-up":
        if len(sys.argv) < 3:
            print("Usage: locus_x402.py top-up <amount>", file=sys.stderr)
            sys.exit(1)
        top_up(float(sys.argv[2]))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
