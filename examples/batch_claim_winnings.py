"""
Example script for claiming winnings from multiple resolved markets.

This example shows how to:
- Create an authenticated client
- Claim winnings from multiple resolved markets in a single batch

Requirements:
- Set TURBINE_PRIVATE_KEY environment variable (your wallet private key)
- Set TURBINE_API_KEY_ID and TURBINE_API_PRIVATE_KEY (API credentials)
- Have winning position tokens in the resolved markets

Usage:
    python examples/batch_claim_winnings.py <market1> <market2> ... [--chain CHAIN_ID]

Example:
    python examples/batch_claim_winnings.py 0xB8c4...96 0xA1b2...34
    python examples/batch_claim_winnings.py 0xB8c4...96 0xA1b2...34 --chain 43114
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
    # Parse arguments
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("Usage: python examples/batch_claim_winnings.py <market1> <market2> ... [--chain CHAIN_ID]")
        print("\nSupported chains:")
        print("  137   - Polygon mainnet (default)")
        print("  43114 - Avalanche mainnet")
        print("  84532 - Base Sepolia")
        print("\nExample:")
        print("  python examples/batch_claim_winnings.py 0xB8c4...96 0xA1b2...34")
        print("  python examples/batch_claim_winnings.py 0xB8c4...96 0xA1b2...34 --chain 43114")
        sys.exit(1)

    # Extract chain_id if provided
    chain_id = 137  # default
    market_addresses = []

    i = 0
    while i < len(args):
        if args[i] == "--chain":
            if i + 1 < len(args):
                chain_id = int(args[i + 1])
                i += 2
            else:
                print("Error: --chain requires a value")
                sys.exit(1)
        else:
            market_addresses.append(args[i])
            i += 1

    if not market_addresses:
        print("Error: At least one market contract address is required")
        sys.exit(1)

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

    print(f"Batch claiming winnings from {len(market_addresses)} markets")
    print(f"Chain ID: {chain_id}")
    print(f"Wallet: {client.address}")
    print()
    print("Markets:")
    for addr in market_addresses:
        print(f"  - {addr}")
    print()

    try:
        result = client.batch_claim_winnings(market_addresses)
        print("\nSuccess!")
        print(f"Transaction hash: {result.get('txHash', result)}")
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
