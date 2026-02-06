"""
Turbine Stress Test Bot - Places multiple trades simultaneously

For testing the API's ability to handle concurrent transactions.
Places N trades at a time against the current BTC quick market.

Uses aiohttp for TRUE parallel HTTP requests - all orders hit the API
within milliseconds of each other, properly testing batch settlement.

Supports multiple accounts for distributed load testing.

USDC is approved gaslessly at startup via one-time max permit per settlement
contract. Orders are submitted without per-order permits.

Usage:
    # Single account
    TURBINE_PRIVATE_KEY=0x... python examples/stress_test_bot.py --trades 10

    # Multiple accounts (comma-separated)
    TURBINE_PRIVATE_KEYS=0xkey1,0xkey2,0xkey3 python examples/stress_test_bot.py -n 30

    # Multiple batches
    TURBINE_PRIVATE_KEY=0x... python examples/stress_test_bot.py -n 20 --batches 5
"""

import argparse
import asyncio
import os
import time
from pathlib import Path
from dotenv import load_dotenv
import aiohttp

from turbine_client import TurbineClient, Outcome, QuickMarket
from turbine_client.exceptions import TurbineApiError

# Load environment variables
load_dotenv()

# ============================================================
# CONFIGURATION (defaults, can be overridden via CLI args)
# ============================================================
CHAIN_ID = int(os.environ.get("CHAIN_ID", "84532"))  # Base Sepolia
TURBINE_HOST = os.environ.get("TURBINE_HOST", "http://localhost:8080")

# Default stress test parameters (overridden by CLI args)
DEFAULT_TRADES_PER_BATCH = 10
DEFAULT_ORDER_SIZE = 100_000  # 0.1 shares
DEFAULT_BATCH_DELAY = 5
DEFAULT_NUM_BATCHES = 3


def get_private_keys() -> list[str]:
    """Get private keys from environment variables.

    Supports:
    - TURBINE_PRIVATE_KEYS: comma-separated list of keys
    - TURBINE_PRIVATE_KEY: single key (fallback)
    """
    # Check for multiple keys first
    keys_str = os.environ.get("TURBINE_PRIVATE_KEYS", "")
    if keys_str:
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if keys:
            return keys

    # Fallback to single key
    single_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if single_key:
        return [single_key]

    raise ValueError(
        "Set TURBINE_PRIVATE_KEY or TURBINE_PRIVATE_KEYS in your .env file"
    )


def get_or_create_api_credentials(private_key: str) -> tuple[str, str]:
    """Get existing credentials or register new ones for a specific private key."""
    # For multi-account mode, we always register fresh credentials
    # (In production, you'd cache these per-address)
    print(f"Registering API credentials for account...")
    credentials = TurbineClient.request_api_credentials(
        host=TURBINE_HOST,
        private_key=private_key,
    )
    return credentials["api_key_id"], credentials["api_private_key"]


class StressTestBot:
    """Bot that places multiple trades simultaneously for stress testing.

    Uses aiohttp for TRUE parallel HTTP requests, ensuring all orders
    hit the API within milliseconds of each other.

    Supports multiple accounts to distribute trades across wallets.

    USDC is approved gaslessly at startup via one-time max permit per
    settlement contract. Orders are submitted without per-order permits.
    """

    def __init__(
        self,
        clients: list[TurbineClient],
        trades_per_batch: int = DEFAULT_TRADES_PER_BATCH,
        order_size: int = DEFAULT_ORDER_SIZE,
        batch_delay: float = DEFAULT_BATCH_DELAY,
        num_batches: int = DEFAULT_NUM_BATCHES,
    ):
        if not clients:
            raise ValueError("At least one client is required")
        self.clients = clients
        self.trades_per_batch = trades_per_batch
        self.order_size = order_size
        self.batch_delay = batch_delay
        self.num_batches = num_batches
        self.market_id: str | None = None
        self.settlement_address: str | None = None
        self.strike_price: int = 0
        self.total_orders_placed = 0
        self.total_orders_succeeded = 0
        self.total_orders_failed = 0

        # Shared aiohttp session for parallel requests
        self._session: aiohttp.ClientSession | None = None

    @property
    def client(self) -> TurbineClient:
        """Primary client (for market queries and general operations)."""
        return self.clients[0]

    def get_client_for_trade(self, trade_index: int) -> TurbineClient:
        """Get the client to use for a specific trade (round-robin distribution)."""
        return self.clients[trade_index % len(self.clients)]

    async def get_active_market(self) -> tuple[str, int, int, str] | None:
        """Get the currently active BTC quick market."""
        try:
            response = self.client._http.get("/api/v1/quick-markets/BTC")
            quick_market_data = response.get("quickMarket")
            if not quick_market_data:
                return None
            quick_market = QuickMarket.from_dict(quick_market_data)

            # Get settlement address from markets list
            markets = self.client.get_markets()
            settlement_address = None
            for market in markets:
                if market.id == quick_market.market_id:
                    settlement_address = market.settlement_address
                    break

            return quick_market.market_id, quick_market.end_time, quick_market.start_price, settlement_address
        except Exception as e:
            print(f"Failed to get active market: {e}")
            return None

    def prepare_order(
        self,
        client: TurbineClient,
        outcome: Outcome,
        price: int,
    ) -> tuple[dict, dict]:
        """Prepare an order for async submission.

        Creates and signs the order using the sync client, then returns
        the payload and headers needed for async HTTP submission.
        No per-order permit — relies on one-time max permit allowance.

        Returns:
            Tuple of (order_payload, headers) for async submission.
        """
        # Create and sign order (CPU-bound, done synchronously)
        order = client.create_limit_buy(
            market_id=self.market_id,
            outcome=outcome,
            price=price,
            size=self.order_size,
            expiration=int(time.time()) + 300,
            settlement_address=self.settlement_address,
        )

        # No per-order permit — using one-time max permit allowance

        # Get the payload and auth headers
        payload = order.to_dict()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        headers.update(client._http._auth.get_auth_header())

        return payload, headers

    async def submit_order_async(
        self,
        session: aiohttp.ClientSession,
        payload: dict,
        headers: dict,
        order_num: int,
        account_addr: str,
        outcome_name: str,
        price: int,
    ) -> dict:
        """Submit a prepared order using async HTTP.

        This is the I/O-bound part that benefits from true parallelism.
        """
        result = {
            "order_num": order_num,
            "outcome": outcome_name,
            "price": price,
            "account": account_addr[:10],
            "success": False,
            "error": None,
            "order_hash": None,
            "status": None,
        }

        url = f"{TURBINE_HOST}/api/v1/orders"

        try:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status >= 400:
                    error_body = await response.json()
                    error_msg = error_body.get("error", error_body.get("message", str(error_body)))
                    result["error"] = error_msg
                else:
                    response_data = await response.json()
                    result["success"] = True
                    result["order_hash"] = response_data.get("orderHash")
                    result["status"] = response_data.get("status", "unknown")

        except aiohttp.ClientError as e:
            result["error"] = f"HTTP error: {e}"
        except Exception as e:
            result["error"] = f"Unexpected: {e}"

        return result

    # Half of max uint256 — threshold for "already has max approval"
    MAX_APPROVAL_THRESHOLD = (2**256 - 1) // 2

    def ensure_all_approved(self) -> None:
        """Ensure all clients have gasless max USDC approval for the settlement contract.

        Signs a one-time max permit per client via the relayer. No native gas required.
        """
        print(f"\n{'='*60}")
        print("ENSURING GASLESS USDC APPROVALS")
        print(f"{'='*60}")

        for i, client in enumerate(self.clients):
            print(f"\n[{i+1}/{len(self.clients)}] {client.address}")

            # Check current allowance
            current_allowance = client.get_usdc_allowance(spender=self.settlement_address)

            if current_allowance >= self.MAX_APPROVAL_THRESHOLD:
                print(f"  ✓ Already has max approval")
                continue

            # Submit gasless max permit via relayer
            print(f"  Submitting gasless max permit...")
            try:
                result = client.approve_usdc_for_settlement(self.settlement_address)
                tx_hash = result.get("tx_hash", "unknown")
                print(f"  Relayer TX: {tx_hash}")
                print(f"  Waiting for confirmation...")

                # Wait for transaction confirmation
                from web3 import Web3
                rpc_urls = {
                    137: "https://polygon-rpc.com",
                    43114: "https://api.avax.network/ext/bc/C/rpc",
                    84532: "https://sepolia.base.org",
                }
                rpc_url = rpc_urls.get(client.chain_id)
                w3 = Web3(Web3.HTTPProvider(rpc_url))

                for _ in range(30):
                    try:
                        receipt = w3.eth.get_transaction_receipt(tx_hash)
                        if receipt:
                            if receipt["status"] == 1:
                                print(f"  ✓ Max approval confirmed (gasless)")
                            else:
                                print(f"  ✗ Transaction failed")
                            break
                    except Exception:
                        pass
                    time.sleep(1)
                else:
                    print(f"  ⚠ Transaction pending (may still confirm)")

            except Exception as e:
                print(f"  ✗ Gasless approval failed: {e}")

        print(f"\n{'='*60}")
        print("APPROVAL SETUP COMPLETE")
        print(f"{'='*60}")

    async def place_batch_orders(self, batch_num: int) -> list[dict]:
        """Place a batch of orders with TRUE parallel HTTP requests."""
        print(f"\n{'='*60}")
        print(f"BATCH {batch_num}: Placing {self.trades_per_batch} orders across {len(self.clients)} accounts")
        print(f"{'='*60}")

        # No permit nonce sync needed — using one-time max permit allowance

        # Get current orderbook to determine prices
        try:
            yes_orderbook = self.client.get_orderbook(self.market_id, outcome=Outcome.YES)
            no_orderbook = self.client.get_orderbook(self.market_id, outcome=Outcome.NO)
        except Exception as e:
            print(f"Failed to get orderbook: {e}")
            return []

        # Determine base prices (slightly above best ask to try to fill)
        yes_price = yes_orderbook.asks[0].price + 5000 if yes_orderbook.asks else 500000
        no_price = no_orderbook.asks[0].price + 5000 if no_orderbook.asks else 500000

        # Cap prices
        yes_price = min(yes_price, 990000)
        no_price = min(no_price, 990000)

        print(f"YES price: {yes_price / 10000:.1f}%")
        print(f"NO price: {no_price / 10000:.1f}%")

        # Show account distribution
        trades_per_account = {}
        for i in range(self.trades_per_batch):
            client = self.get_client_for_trade(i)
            addr = client.address[:10]
            trades_per_account[addr] = trades_per_account.get(addr, 0) + 1
        print(f"Trades per account: {trades_per_account}")

        # PHASE 1: Prepare all orders synchronously (CPU-bound: signing)
        print(f"\nPreparing {self.trades_per_batch} orders...")
        prep_start = time.time()

        prepared_orders = []
        for i in range(self.trades_per_batch):
            client = self.get_client_for_trade(i)

            if i % 2 == 0:
                outcome = Outcome.YES
                price = yes_price + (i * 1000)
            else:
                outcome = Outcome.NO
                price = no_price + (i * 1000)

            price = min(price, 990000)

            payload, headers = self.prepare_order(client, outcome, price)
            prepared_orders.append({
                "payload": payload,
                "headers": headers,
                "order_num": i + 1,
                "account": client.address,
                "outcome": outcome.name,
                "price": price,
            })

        prep_elapsed = time.time() - prep_start
        print(f"Orders prepared in {prep_elapsed:.2f}s")

        # PHASE 2: Submit all orders in TRUE PARALLEL using aiohttp
        print(f"Submitting {self.trades_per_batch} orders in parallel...")
        submit_start = time.time()

        async with aiohttp.ClientSession() as session:
            tasks = [
                self.submit_order_async(
                    session,
                    order["payload"],
                    order["headers"],
                    order["order_num"],
                    order["account"],
                    order["outcome"],
                    order["price"],
                )
                for order in prepared_orders
            ]
            results = await asyncio.gather(*tasks)

        submit_elapsed = time.time() - submit_start
        print(f"All {self.trades_per_batch} orders submitted in {submit_elapsed:.3f}s (avg {submit_elapsed/self.trades_per_batch*1000:.1f}ms/order)")

        # Summarize results
        succeeded = sum(1 for r in results if r["success"])
        failed = sum(1 for r in results if not r["success"])

        self.total_orders_placed += self.trades_per_batch
        self.total_orders_succeeded += succeeded
        self.total_orders_failed += failed

        print(f"\nBatch {batch_num} Results:")
        print(f"  Succeeded: {succeeded}/{self.trades_per_batch}")
        print(f"  Failed: {failed}/{self.trades_per_batch}")

        # Show individual results
        for r in results:
            status = "OK" if r["success"] else "FAIL"
            if r["success"]:
                print(f"  [{r['order_num']:2d}] {status} - {r['outcome']:3s} @ {r['price']/10000:.1f}% [{r['account']}] - {r['status']}")
            else:
                print(f"  [{r['order_num']:2d}] {status} - {r['outcome']:3s} @ {r['price']/10000:.1f}% [{r['account']}] - {r['error']}")

        return results

    async def check_settlement_status(self) -> None:
        """Check the status of pending and failed trades."""
        try:
            pending = self.client.get_pending_trades()
            # Filter to our market and any of our accounts
            our_addresses = {c.address.lower() for c in self.clients}
            my_pending = [t for t in pending
                         if t.market_id == self.market_id
                         and t.buyer_address.lower() in our_addresses]

            failed = self.client.get_failed_trades()
            my_failed = [t for t in failed
                        if t.market_id == self.market_id
                        and t.buyer_address.lower() in our_addresses]

            print(f"\nSettlement Status:")
            print(f"  Pending trades: {len(my_pending)}")
            print(f"  Failed trades: {len(my_failed)}")

            if my_failed:
                print(f"  Recent failures:")
                for t in my_failed[:5]:
                    print(f"    - {t.reason}")

        except Exception as e:
            print(f"Could not check settlement status: {e}")

    async def run(self) -> None:
        """Run the stress test."""
        # Get active market
        market_info = await self.get_active_market()
        if not market_info:
            print("No active BTC market found. Please ensure quick markets are running.")
            return

        market_id, end_time, start_price, settlement_address = market_info
        self.market_id = market_id
        self.settlement_address = settlement_address
        self.strike_price = start_price

        print(f"\n{'='*60}")
        print(f"STRESS TEST CONFIGURATION")
        print(f"{'='*60}")
        print(f"Market ID: {market_id[:16]}...")
        print(f"Settlement: {settlement_address[:16]}..." if settlement_address else "Settlement: Not found")
        print(f"Strike Price: ${start_price / 1e6:,.2f}")
        print(f"Market Expires: {time.strftime('%H:%M:%S', time.localtime(end_time))}")
        print(f"Accounts: {len(self.clients)}")
        for i, c in enumerate(self.clients):
            print(f"  [{i+1}] {c.address}")
        print(f"Trades per batch: {self.trades_per_batch}")
        print(f"Order size: {self.order_size / 1_000_000:.2f} shares")
        print(f"Batches: {self.num_batches if self.num_batches > 0 else 'Infinite'}")
        print(f"Delay between batches: {self.batch_delay}s ({int(self.batch_delay * 1000)}ms)")
        print(f"Approval mode: GASLESS (one-time max permit)")
        print(f"HTTP mode: ASYNC (true parallel requests)")

        # Ensure all clients have gasless max USDC approval
        self.ensure_all_approved()

        # Run batches
        batch_num = 0
        try:
            while self.num_batches == 0 or batch_num < self.num_batches:
                batch_num += 1

                # Check if market is about to expire
                time_remaining = end_time - int(time.time())
                if time_remaining < 60:
                    print(f"\nMarket expires in {time_remaining}s - stopping test")
                    break

                await self.place_batch_orders(batch_num)

                # Delay before next batch
                if self.num_batches == 0 or batch_num < self.num_batches:
                    if self.batch_delay >= 1:
                        print(f"\nWaiting {self.batch_delay}s before next batch...")
                    else:
                        print(f"\nWaiting {int(self.batch_delay * 1000)}ms before next batch...")
                    await asyncio.sleep(self.batch_delay)

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")

        # Final summary
        print(f"\n{'='*60}")
        print(f"STRESS TEST COMPLETE")
        print(f"{'='*60}")
        print(f"Total orders placed: {self.total_orders_placed}")
        print(f"Total succeeded: {self.total_orders_succeeded}")
        print(f"Total failed: {self.total_orders_failed}")
        print(f"Success rate: {self.total_orders_succeeded / max(self.total_orders_placed, 1) * 100:.1f}%")


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Stress test bot - places multiple trades simultaneously across multiple accounts"
    )
    parser.add_argument(
        "-n", "--trades",
        type=int,
        default=DEFAULT_TRADES_PER_BATCH,
        help=f"Number of trades to place per batch (default: {DEFAULT_TRADES_PER_BATCH})"
    )
    parser.add_argument(
        "-s", "--size",
        type=int,
        default=DEFAULT_ORDER_SIZE,
        help=f"Order size in 6 decimals, e.g. 100000 = 0.1 shares (default: {DEFAULT_ORDER_SIZE})"
    )
    parser.add_argument(
        "-b", "--batches",
        type=int,
        default=DEFAULT_NUM_BATCHES,
        help=f"Number of batches to run, 0 = infinite (default: {DEFAULT_NUM_BATCHES})"
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=DEFAULT_BATCH_DELAY,
        help=f"Delay in seconds between batches, supports decimals like 0.1 (default: {DEFAULT_BATCH_DELAY})"
    )
    args = parser.parse_args()

    # Get private keys (supports multiple)
    private_keys = get_private_keys()
    print(f"Found {len(private_keys)} account(s)")

    # Create clients for each account
    clients = []
    for i, private_key in enumerate(private_keys):
        print(f"\nSetting up account {i+1}/{len(private_keys)}...")
        api_key_id, api_private_key = get_or_create_api_credentials(private_key)

        client = TurbineClient(
            host=TURBINE_HOST,
            chain_id=CHAIN_ID,
            private_key=private_key,
            api_key_id=api_key_id,
            api_private_key=api_private_key,
        )
        clients.append(client)
        print(f"  Address: {client.address}")

    print(f"\nAll {len(clients)} accounts ready")
    print(f"Chain ID: {CHAIN_ID}")
    print(f"API Host: {TURBINE_HOST}")
    print(f"Mode: GASLESS (one-time max permit)")

    # Run stress test with CLI args
    bot = StressTestBot(
        clients,
        trades_per_batch=args.trades,
        order_size=args.size,
        batch_delay=args.delay,
        num_batches=args.batches,
    )

    try:
        await bot.run()
    finally:
        for client in clients:
            client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
