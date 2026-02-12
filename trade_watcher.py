"""Watch live trades on Turbine BTC markets and log them."""
import asyncio
import os
import time
import json
from pathlib import Path
from dotenv import load_dotenv
from turbine_client import TurbineClient, QuickMarket

load_dotenv()

CHAIN_ID = int(os.environ.get("CHAIN_ID", "137"))
TURBINE_HOST = os.environ.get("TURBINE_HOST", "https://api.turbinefi.com")
RUN_DURATION = 600  # 10 minutes
POLL_SECONDS = 5
LOG_FILE = Path(__file__).parent / "trade_watch_log.jsonl"

async def main():
    pk = os.environ.get("TURBINE_PRIVATE_KEY")
    client = TurbineClient(host=TURBINE_HOST, chain_id=CHAIN_ID, private_key=pk)
    
    print(f"Watching trades for 10 minutes...")
    
    seen_trade_ids = set()
    current_market_id = None
    start = time.time()
    
    with open(LOG_FILE, "w") as log:
        while time.time() - start < RUN_DURATION:
            try:
                # Get current market
                resp = client._http.get("/api/v1/quick-markets/BTC")
                qm_data = resp.get("quickMarket")
                if not qm_data:
                    await asyncio.sleep(POLL_SECONDS)
                    continue
                
                qm = QuickMarket.from_dict(qm_data)
                strike_usd = qm.start_price / 1e6
                remaining = qm.end_time - int(time.time())
                
                if qm.market_id != current_market_id:
                    current_market_id = qm.market_id
                    seen_trade_ids.clear()
                    entry = {
                        "type": "market",
                        "time": time.strftime("%H:%M:%S"),
                        "market_id": qm.market_id[:12],
                        "strike": round(strike_usd, 2),
                        "remaining": remaining
                    }
                    log.write(json.dumps(entry) + "\n")
                    log.flush()
                    print(f"NEW MARKET | strike=${strike_usd:,.2f} | {remaining}s remaining")
                
                # Get recent trades
                trades = client.get_trades(market_id=current_market_id, limit=20)
                
                new_trades = [t for t in trades if t.id not in seen_trade_ids]
                new_trades.sort(key=lambda t: t.id)
                
                for trade in new_trades:
                    seen_trade_ids.add(trade.id)
                    outcome = "YES" if trade.outcome == 0 else "NO"
                    size_usd = (trade.size * trade.price) / (1_000_000 * 1_000_000)
                    price_pct = trade.price / 10000
                    
                    entry = {
                        "type": "trade",
                        "time": time.strftime("%H:%M:%S"),
                        "trader": trade.buyer[:10] + "...",
                        "outcome": outcome,
                        "size_usd": round(size_usd, 4),
                        "shares": round(trade.size / 1_000_000, 4),
                        "price_pct": round(price_pct, 1),
                        "market_remaining": remaining
                    }
                    log.write(json.dumps(entry) + "\n")
                    log.flush()
                    
                    emoji = "🟢" if outcome == "YES" else "🔴"
                    print(f"{entry['time']} | {emoji} {trade.buyer[:10]}... bought {entry['shares']} {outcome} @ {price_pct:.1f}% (${size_usd:.4f}) | {remaining}s left")
                
            except Exception as e:
                print(f"Error: {e}")
            
            await asyncio.sleep(POLL_SECONDS)
    
    print("Watch complete.")

if __name__ == "__main__":
    asyncio.run(main())
