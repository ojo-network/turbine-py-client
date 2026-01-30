"""
Example script for claiming winnings from a resolved market.

This example shows how to:
- Create an authenticated client
- Claim winnings from a resolved market using gasless permits

Requirements:
- Set TURBINE_PRIVATE_KEY environment variable (your wallet private key)
- Set TURBINE_API_KEY_ID and TURBINE_API_PRIVATE_KEY (API credentials)
- Have winning position tokens in the resolved market

Usage:
    python examples/claim_winnings.py <market_contract_address>

Example:
    python examples/claim_winnings.py 0xB8c45e915F8a78ff8FD691bBDED2125bc9Fa4d96
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional, use exported env vars

from turbine_client import TurbineClient


def main():
    if len(sys.argv) < 2:
        print("Usage: python examples/claim_winnings.py <market_contract_address> [chain_id]")
        print("\nSupported chains:")
        print("  137   - Polygon mainnet (default)")
        print("  43114 - Avalanche mainnet")
        print("  84532 - Base Sepolia")
        print("\nExample:")
        print("  python examples/claim_winnings.py 0xB8c45e915F8a78ff8FD691bBDED2125bc9Fa4d96")
        print("  python examples/claim_winnings.py 0x... 43114  # Avalanche")
        sys.exit(1)

    market_contract_address = sys.argv[1]
    chain_id = int(sys.argv[2]) if len(sys.argv) > 2 else 137

    # Get credentials from environment
    private_key = os.getenv("TURBINE_PRIVATE_KEY")
    api_key_id = os.getenv("TURBINE_API_KEY_ID")
    api_private_key = os.getenv("TURBINE_API_PRIVATE_KEY")

    if not private_key:
        print("Error: TURBINE_PRIVATE_KEY environment variable not set")
        sys.exit(1)

    if not api_key_id or not api_private_key:
        print("Error: TURBINE_API_KEY_ID and TURBINE_API_PRIVATE_KEY must be set")
        print("\nYou can register for API credentials using:")
        print("  from turbine_client import TurbineClient")
        print("  creds = TurbineClient.request_api_credentials(")
        print('      host="https://api.turbinefi.com",')
        print('      private_key="0x...",')
        print("  )")
        sys.exit(1)

    # Create authenticated client
    client = TurbineClient(
        host="https://api.turbinefi.com",
        chain_id=chain_id,
        private_key=private_key,
        api_key_id=api_key_id,
        api_private_key=api_private_key,
    )

    print(f"Claiming winnings from market: {market_contract_address}")
    print(f"Chain ID: {chain_id}")
    print(f"Wallet: {client.address}")
    print()

    try:
        result = client.claim_winnings(market_contract_address)
        print("\nSuccess!")
        print(f"Transaction hash: {result.get('tx_hash', result)}")
    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
