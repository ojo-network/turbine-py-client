"""
Setup Stress Test Accounts - Generates and funds accounts for stress testing

This script:
1. Generates N new accounts with private keys
2. Sends ETH to each account for gas (from your funded account)
3. Has each account call the MockUSDC faucet() to get 10,000 USDC

Usage:
    TURBINE_PRIVATE_KEY=0x... python examples/setup_stress_test_accounts.py

    # Specify number of accounts
    TURBINE_PRIVATE_KEY=0x... python examples/setup_stress_test_accounts.py --accounts 10

Output:
    Prints the TURBINE_PRIVATE_KEYS environment variable to use with stress_test_bot.py
"""

import argparse
import os
import time
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

# Load environment variables
load_dotenv()

# Configuration
CHAIN_ID = int(os.environ.get("CHAIN_ID", "84532"))  # Base Sepolia
RPC_URL = os.environ.get("RPC_URL", "https://sepolia.base.org")

# Contract addresses for Base Sepolia
USDC_ADDRESS = "0xf9065CCFF7025649F16D547DC341DAffF0C7F7f6"

# Amount of ETH to send to each account for gas (0.001 ETH should be plenty)
ETH_PER_ACCOUNT = Web3.to_wei(0.001, "ether")

# faucet() function selector (no arguments)
FAUCET_SELECTOR = "0xde5f72fd"


def generate_accounts(num_accounts: int) -> list[tuple[str, str]]:
    """Generate new Ethereum accounts.

    Returns list of (address, private_key) tuples.
    """
    accounts = []
    for i in range(num_accounts):
        account = Account.create()
        accounts.append((account.address, account.key.hex()))
    return accounts


def send_eth(w3: Web3, from_account, to_address: str, amount: int, nonce: int) -> str:
    """Send ETH from one account to another."""
    tx = {
        "from": from_account.address,
        "to": to_address,
        "value": amount,
        "gas": 21000,
        "gasPrice": w3.eth.gas_price,
        "nonce": nonce,
        "chainId": CHAIN_ID,
    }

    signed = from_account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def call_faucet(w3: Web3, account, usdc_address: str) -> str:
    """Call the faucet() function on MockUSDC."""
    nonce = w3.eth.get_transaction_count(account.address)

    tx = {
        "from": account.address,
        "to": usdc_address,
        "data": FAUCET_SELECTOR,
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
        "nonce": nonce,
        "chainId": CHAIN_ID,
    }

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def wait_for_tx(w3: Web3, tx_hash: str, timeout: int = 60) -> bool:
    """Wait for a transaction to be mined."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt:
                return receipt["status"] == 1
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate and fund stress test accounts"
    )
    parser.add_argument(
        "-n", "--accounts",
        type=int,
        default=10,
        help="Number of accounts to generate (default: 10)"
    )
    parser.add_argument(
        "--eth-amount",
        type=float,
        default=0.001,
        help="Amount of ETH to send to each account (default: 0.001)"
    )
    parser.add_argument(
        "--skip-faucet",
        action="store_true",
        help="Skip calling faucet (just generate and fund with ETH)"
    )
    args = parser.parse_args()

    # Get funder private key
    funder_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if not funder_key:
        print("Error: Set TURBINE_PRIVATE_KEY to fund the new accounts")
        return

    # Connect to RPC
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print(f"Error: Could not connect to RPC at {RPC_URL}")
        return

    print(f"Connected to {RPC_URL}")
    print(f"Chain ID: {CHAIN_ID}")

    # Load funder account
    funder = Account.from_key(funder_key)
    funder_balance = w3.eth.get_balance(funder.address)
    print(f"\nFunder account: {funder.address}")
    print(f"Funder balance: {Web3.from_wei(funder_balance, 'ether'):.4f} ETH")

    eth_per_account = Web3.to_wei(args.eth_amount, "ether")
    total_eth_needed = eth_per_account * args.accounts

    if funder_balance < total_eth_needed:
        print(f"\nError: Insufficient ETH. Need {Web3.from_wei(total_eth_needed, 'ether'):.4f} ETH")
        return

    # Generate accounts
    print(f"\nGenerating {args.accounts} accounts...")
    accounts = generate_accounts(args.accounts)

    # Display accounts
    print("\n" + "=" * 70)
    print("GENERATED ACCOUNTS")
    print("=" * 70)
    for i, (address, private_key) in enumerate(accounts):
        print(f"[{i+1}] {address}")
        print(f"    Key: {private_key}")

    # Send ETH to each account
    print("\n" + "=" * 70)
    print("FUNDING ACCOUNTS WITH ETH")
    print("=" * 70)

    funder_nonce = w3.eth.get_transaction_count(funder.address)
    eth_tx_hashes = []

    for i, (address, _) in enumerate(accounts):
        tx_hash = send_eth(w3, funder, address, eth_per_account, funder_nonce + i)
        eth_tx_hashes.append(tx_hash)
        print(f"[{i+1}] Sent {args.eth_amount} ETH to {address[:10]}... tx: {tx_hash[:10]}...")

    # Wait for ETH transfers to confirm
    print("\nWaiting for ETH transfers to confirm...")
    for i, tx_hash in enumerate(eth_tx_hashes):
        success = wait_for_tx(w3, tx_hash)
        status = "OK" if success else "FAILED"
        print(f"[{i+1}] {status}")
        if not success:
            print(f"    Warning: ETH transfer may have failed")

    # Call faucet for each account
    if not args.skip_faucet:
        print("\n" + "=" * 70)
        print("CALLING USDC FAUCET FOR EACH ACCOUNT")
        print("=" * 70)

        faucet_tx_hashes = []
        for i, (address, private_key) in enumerate(accounts):
            account = Account.from_key(private_key)
            try:
                tx_hash = call_faucet(w3, account, USDC_ADDRESS)
                faucet_tx_hashes.append((i, tx_hash))
                print(f"[{i+1}] Faucet called for {address[:10]}... tx: {tx_hash[:10]}...")
            except Exception as e:
                print(f"[{i+1}] Failed to call faucet: {e}")
                faucet_tx_hashes.append((i, None))

        # Wait for faucet calls to confirm
        print("\nWaiting for faucet transactions to confirm...")
        for i, tx_hash in faucet_tx_hashes:
            if tx_hash:
                success = wait_for_tx(w3, tx_hash)
                status = "OK - 10,000 USDC" if success else "FAILED"
                print(f"[{i+1}] {status}")
            else:
                print(f"[{i+1}] SKIPPED")

    # Output the environment variable
    print("\n" + "=" * 70)
    print("SETUP COMPLETE!")
    print("=" * 70)

    private_keys = [pk for _, pk in accounts]
    keys_str = ",".join(private_keys)

    print("\nAdd this to your .env file or export it:")
    print()
    print(f"TURBINE_PRIVATE_KEYS={keys_str}")
    print()
    print("Then run the stress test with:")
    print(f"  python examples/stress_test_bot.py -n {args.accounts}")
    print()

    # Also write to a file for convenience
    env_file = "stress_test_accounts.env"
    with open(env_file, "w") as f:
        f.write(f"# Generated {args.accounts} stress test accounts\n")
        f.write(f"# Each account has {args.eth_amount} ETH and 10,000 USDC\n")
        f.write(f"TURBINE_PRIVATE_KEYS={keys_str}\n")
        f.write("\n# Individual keys for reference:\n")
        for i, (address, private_key) in enumerate(accounts):
            f.write(f"# Account {i+1}: {address}\n")
            f.write(f"# PRIVATE_KEY_{i+1}={private_key}\n")

    print(f"Keys also saved to: {env_file}")


if __name__ == "__main__":
    main()
