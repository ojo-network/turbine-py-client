"""
Full order lifecycle integration test.

This example demonstrates:
1. Place a limit order
2. Cancel the order
3. Scan for existing orders in the orderbook
4. Place an order to fill against existing liquidity (and wait for fill)
5. Sell the position back at the opposite price (and wait for fill)

Run locally with environment variables:
    INTEGRATION_WALLET_PRIVATE_KEY=... \
    INTEGRATION_API_KEY_ID=... \
    INTEGRATION_API_PRIVATE_KEY=... \
    python examples/full_order_lifecycle.py
"""

import os
import sys
import time

from turbine_client import TurbineClient
from turbine_client.types import Outcome, Side

# Get credentials from environment variables
WALLET_PRIVATE_KEY = os.environ.get("INTEGRATION_WALLET_PRIVATE_KEY")
API_KEY_ID = os.environ.get("INTEGRATION_API_KEY_ID")
API_PRIVATE_KEY = os.environ.get("INTEGRATION_API_PRIVATE_KEY")

if not all([WALLET_PRIVATE_KEY, API_KEY_ID, API_PRIVATE_KEY]):
    print("ERROR: Missing required environment variables:")
    print("  INTEGRATION_WALLET_PRIVATE_KEY")
    print("  INTEGRATION_API_KEY_ID")
    print("  INTEGRATION_API_PRIVATE_KEY")
    sys.exit(1)


def wait_for_fill(client, order_hash: str, market_id: str, timeout: int = 30) -> dict:
    """Wait for an order to be filled or reach a terminal state.

    Args:
        client: The TurbineClient instance.
        order_hash: The order hash to monitor.
        market_id: The market ID.
        timeout: Maximum seconds to wait.

    Returns:
        The final order state dict with status and fill info.
    """
    print(f"  Waiting for order {order_hash[:16]}... to fill...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            # Get all orders for this trader/market and find ours
            orders = client.get_orders(
                trader=client.address,
                market_id=market_id,
            )

            order = None
            for o in orders:
                if o.order_hash == order_hash:
                    order = o
                    break

            if order:
                filled = order.filled_size / 1_000_000
                remaining = order.remaining_size / 1_000_000
                total = order.size / 1_000_000

                if order.status == "filled":
                    print(f"  ✓ Order FILLED! {filled:.4f}/{total:.4f} shares")
                    return {
                        "status": "filled",
                        "filled_size": order.filled_size,
                        "remaining_size": order.remaining_size,
                    }
                elif order.status == "cancelled":
                    print(f"  ✗ Order CANCELLED. Filled {filled:.4f}/{total:.4f} shares")
                    return {
                        "status": "cancelled",
                        "filled_size": order.filled_size,
                        "remaining_size": order.remaining_size,
                    }
                elif order.filled_size > 0:
                    print(f"  ... Partially filled: {filled:.4f}/{total:.4f} shares (remaining: {remaining:.4f})")
                else:
                    print(f"  ... Status: {order.status}, waiting...")
            else:
                # Order not found - might be fully filled and removed
                print(f"  ... Order not found in open orders (may be filled)")
                return {
                    "status": "filled",
                    "filled_size": 0,
                    "remaining_size": 0,
                }

        except Exception as e:
            print(f"  ... Error checking order: {e}")

        time.sleep(1)

    print(f"  ⏱ Timeout waiting for fill")
    return {"status": "timeout", "filled_size": 0, "remaining_size": 0}


def main():
    # Create authenticated client
    client = TurbineClient(
        host="https://api.turbinefi.com",
        chain_id=137,  # Polygon mainnet
        private_key=WALLET_PRIVATE_KEY,
        api_key_id=API_KEY_ID,
        api_private_key=API_PRIVATE_KEY,
    )

    print(f"Wallet address: {client.address}")
    print()

    # Get the latest BTC quick market
    print("Fetching latest BTC quick market...")
    try:
        quick_market = client.get_quick_market("BTC")
        print(f"Found active BTC market: {quick_market.market_id}")

        # Now get the full market details including settlement address
        markets = client.get_markets()
        market = None
        for m in markets:
            if m.id == quick_market.market_id:
                market = m
                break

        if not market:
            print(f"Could not find market details for {quick_market.market_id}")
            # Fall back to first market
            market = markets[0] if markets else None
    except Exception as e:
        print(f"Could not fetch BTC quick market: {e}")
        print("Falling back to first available market...")
        markets = client.get_markets()
        market = markets[0] if markets else None

    if not market:
        print("No markets available")
        client.close()
        return

    print(f"=== Using market: {market.question} ===")
    print(f"Market ID: {market.id}")
    print(f"Settlement Address: {market.settlement_address}")
    print()

    # =========================================================================
    # Step 1: Place a limit order
    # =========================================================================
    print("=" * 60)
    print("STEP 1: Place a limit order")
    print("=" * 60)

    # Place a low bid that won't fill immediately
    buy_price = 50000  # 5%
    buy_size = 1_000_000  # 1 share

    print(f"Placing BUY order: {buy_size / 1_000_000:.2f} YES @ {buy_price / 10000:.2f}%")

    buy_order = client.create_limit_buy(
        market_id=market.id,
        outcome=Outcome.YES,
        price=buy_price,
        size=buy_size,
        settlement_address=market.settlement_address,
    )

    print(f"Order signed. Hash: {buy_order.order_hash}")

    result = client.post_order(buy_order)
    print(f"Order submitted: {result}")
    order_hash = result.get("orderHash", buy_order.order_hash)
    print()

    # =========================================================================
    # Step 2: Cancel the order
    # =========================================================================
    print("=" * 60)
    print("STEP 2: Cancel the order")
    print("=" * 60)

    time.sleep(1)  # Give API time to process

    try:
        cancel_result = client.cancel_order(
            order_hash=order_hash,
            market_id=market.id,
            side=Side.BUY,
        )
        print(f"Order cancelled: {cancel_result}")
    except Exception as e:
        print(f"Cancel failed (order may have been filled or already cancelled): {e}")
    print()

    # =========================================================================
    # Step 3: Scan the orderbook for existing liquidity
    # =========================================================================
    print("=" * 60)
    print("STEP 3: Scan orderbook for existing liquidity")
    print("=" * 60)

    orderbook = client.get_orderbook(market.id)
    print(f"Market: {market.id}")
    print(f"Last update: {orderbook.last_update}")

    print("\nTop 5 Bids (buyers wanting to buy YES):")
    for i, bid in enumerate(orderbook.bids[:5]):
        price_pct = bid.price / 10000
        shares = bid.size / 1_000_000
        print(f"  {i+1}. {price_pct:.2f}% - {shares:.4f} shares")

    print("\nTop 5 Asks (sellers wanting to sell YES):")
    for i, ask in enumerate(orderbook.asks[:5]):
        price_pct = ask.price / 10000
        shares = ask.size / 1_000_000
        print(f"  {i+1}. {price_pct:.2f}% - {shares:.4f} shares")
    print()

    # =========================================================================
    # Step 4: Place an order to fill against existing liquidity
    # =========================================================================
    print("=" * 60)
    print("STEP 4: BUY - Take liquidity from asks")
    print("=" * 60)

    buy_order_hash = None

    # To buy YES, we need to match against the bids (people selling YES to us)
    # The "asks" in the orderbook represent sell orders for YES
    # Actually in this CLOB, bids are buy orders for YES, asks are sell orders for YES
    # To take liquidity as a buyer, we place a buy order at or above the best ask

    if orderbook.bids:
        # Best bid = highest price someone will pay for YES
        # To SELL to them (take their liquidity), we place a sell at or below
        # But we want to BUY first, so let's look at asks
        pass

    # Refresh orderbook
    orderbook = client.get_orderbook(market.id)

    # To BUY YES shares, we match against people selling YES (asks)
    # But the asks shown are actually NO side? Let's just use the best bid
    # In a prediction market: buying YES at price P = selling NO at price (1-P)

    if orderbook.bids:
        best_bid = orderbook.bids[0]
        print(f"Best bid (someone buying YES): {best_bid.price / 10000:.2f}% for {best_bid.size / 1_000_000:.4f} shares")

        # Place a SELL order to match against the best bid
        # This sells our YES shares to the bidder
        take_size = min(100_000, best_bid.size)  # 0.1 shares or less
        take_price = best_bid.price  # Match at their price

        print(f"\nPlacing SELL to match bid: {take_size / 1_000_000:.4f} YES @ {take_price / 10000:.2f}%")

        sell_order = client.create_limit_sell(
            market_id=market.id,
            outcome=Outcome.YES,
            price=take_price,
            size=take_size,
            settlement_address=market.settlement_address,
        )

        result = client.post_order(sell_order)
        print(f"Order result: {result}")
        matches = result.get("matches", 0)
        sell_order_hash = result.get("orderHash", sell_order.order_hash)

        if matches > 0:
            print(f"  -> Immediate match with {matches} order(s)!")
            # Wait for the fill to complete
            fill_result = wait_for_fill(client, sell_order_hash, market.id, timeout=10)
        else:
            print(f"  -> Order posted to book, waiting for fill...")
            fill_result = wait_for_fill(client, sell_order_hash, market.id, timeout=15)
    else:
        print("No bids available - cannot sell")
        sell_order_hash = None
    print()

    # =========================================================================
    # Step 5: Buy back the position
    # =========================================================================
    print("=" * 60)
    print("STEP 5: BUY - Take liquidity from other side")
    print("=" * 60)

    # Refresh orderbook
    orderbook = client.get_orderbook(market.id)

    # Now let's buy YES by matching against asks (if any)
    # Or we could buy by placing a high bid

    if orderbook.bids:
        # Place a BUY order above the current best bid to try to get filled
        best_bid = orderbook.bids[0]
        print(f"Best bid: {best_bid.price / 10000:.2f}%")

        # Place buy slightly above to be at top of book
        buy_size = 100_000  # 0.1 shares
        buy_price = min(best_bid.price + 5000, 990000)  # 0.5% above best bid, max 99%

        print(f"\nPlacing BUY order: {buy_size / 1_000_000:.4f} YES @ {buy_price / 10000:.2f}%")

        buy_order = client.create_limit_buy(
            market_id=market.id,
            outcome=Outcome.YES,
            price=buy_price,
            size=buy_size,
            settlement_address=market.settlement_address,
        )

        result = client.post_order(buy_order)
        print(f"Order result: {result}")
        matches = result.get("matches", 0)
        buy_order_hash = result.get("orderHash", buy_order.order_hash)

        if matches > 0:
            print(f"  -> Immediate match with {matches} order(s)!")
            fill_result = wait_for_fill(client, buy_order_hash, market.id, timeout=10)
        else:
            print(f"  -> Order posted to book, waiting for fill...")
            # Wait a bit then check
            fill_result = wait_for_fill(client, buy_order_hash, market.id, timeout=10)
    else:
        print("No bids available - skipping buy")
        buy_order_hash = None
    print()

    # =========================================================================
    # Bonus: Check user's open orders
    # =========================================================================
    print("=" * 60)
    print("BONUS: Check user's open orders")
    print("=" * 60)

    try:
        open_orders = client.get_orders(
            trader=client.address,
            market_id=market.id,
            status="open",
        )
        print(f"Found {len(open_orders)} open orders:")
        for order in open_orders[:5]:
            side = "BUY" if order.side == 0 else "SELL"
            outcome = "YES" if order.outcome == 0 else "NO"
            price_pct = order.price / 10000
            remaining = order.remaining_size / 1_000_000
            filled = order.filled_size / 1_000_000
            print(f"  - {side} {outcome} @ {price_pct:.2f}%: filled {filled:.4f}, remaining {remaining:.4f} (hash: {order.order_hash[:16]}...)")
    except Exception as e:
        print(f"Could not fetch orders: {e}")
    print()

    # =========================================================================
    # Cleanup: Cancel any remaining open orders
    # =========================================================================
    print("=" * 60)
    print("CLEANUP: Cancel any remaining open orders")
    print("=" * 60)

    try:
        open_orders = client.get_orders(
            trader=client.address,
            market_id=market.id,
            status="open",
        )
        if open_orders:
            print(f"Cancelling {len(open_orders)} open orders...")
            for order in open_orders:
                try:
                    side = Side.BUY if order.side == 0 else Side.SELL
                    result = client.cancel_order(
                        order_hash=order.order_hash,
                        market_id=market.id,
                        side=side,
                    )
                    print(f"  Cancelled: {order.order_hash[:16]}...")
                except Exception as e:
                    print(f"  Failed to cancel {order.order_hash[:16]}...: {e}")
        else:
            print("No open orders to cancel")
    except Exception as e:
        print(f"Cleanup failed: {e}")

    client.close()
    print("\n" + "=" * 60)
    print("Integration test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
