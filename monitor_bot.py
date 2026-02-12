"""
Turbine Price Action Monitor — runs for 10 minutes, logs signals to a file.
"""
import asyncio
import os
import time
import json
from pathlib import Path
from dotenv import load_dotenv
import httpx

from turbine_client import TurbineClient, QuickMarket

load_dotenv()

CHAIN_ID = int(os.environ.get("CHAIN_ID", "137"))
TURBINE_HOST = os.environ.get("TURBINE_HOST", "https://api.turbinefi.com")
PYTH_HERMES_URL = "https://hermes.pyth.network/v2/updates/price/latest"
PYTH_BTC_FEED_ID = "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43"

PRICE_THRESHOLD_BPS = 10
POLL_SECONDS = 10
RUN_DURATION = 600  # 10 minutes

LOG_FILE = Path(__file__).parent / "monitor_log.jsonl"

async def get_btc_price(http_client):
    try:
        resp = await http_client.get(PYTH_HERMES_URL, params={"ids[]": PYTH_BTC_FEED_ID})
        resp.raise_for_status()
        data = resp.json()
        if not data.get("parsed"):
            return 0.0
        pd = data["parsed"][0]["price"]
        return int(pd["price"]) * (10 ** pd["expo"])
    except Exception as e:
        print(f"Price fetch error: {e}")
        return 0.0

async def main():
    pk = os.environ.get("TURBINE_PRIVATE_KEY")
    client = TurbineClient(host=TURBINE_HOST, chain_id=CHAIN_ID, private_key=pk)
    
    print(f"Wallet: {client.address}")
    print(f"Monitoring for {RUN_DURATION}s...")
    
    start = time.time()
    current_market_id = None
    http_client = httpx.AsyncClient(timeout=5.0)
    
    with open(LOG_FILE, "a") as log:
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
                    entry = {
                        "type": "market_change",
                        "time": time.strftime("%H:%M:%S"),
                        "market_id": qm.market_id[:12],
                        "strike": strike_usd,
                        "remaining": remaining
                    }
                    log.write(json.dumps(entry) + "\n")
                    log.flush()
                    print(f"NEW MARKET: strike=${strike_usd:,.2f} remaining={remaining}s")
                
                # Get BTC price
                btc_price = await get_btc_price(http_client)
                if btc_price <= 0:
                    await asyncio.sleep(POLL_SECONDS)
                    continue
                
                diff_pct = ((btc_price - strike_usd) / strike_usd) * 100
                threshold = PRICE_THRESHOLD_BPS / 100
                
                if abs(diff_pct) >= threshold:
                    if diff_pct > 0:
                        action = "BUY_YES"
                    else:
                        action = "BUY_NO"
                    confidence = min(abs(diff_pct) / 2, 0.9)
                else:
                    action = "HOLD"
                    confidence = 0.0
                
                entry = {
                    "type": "signal",
                    "time": time.strftime("%H:%M:%S"),
                    "btc": round(btc_price, 2),
                    "strike": round(strike_usd, 2),
                    "diff_pct": round(diff_pct, 3),
                    "action": action,
                    "confidence": round(confidence, 3),
                    "market_remaining": remaining
                }
                log.write(json.dumps(entry) + "\n")
                log.flush()
                
                emoji = "🟢" if action == "BUY_YES" else ("🔴" if action == "BUY_NO" else "⏸️")
                print(f"{entry['time']} | BTC ${btc_price:,.2f} | Strike ${strike_usd:,.2f} | {diff_pct:+.3f}% | {emoji} {action} ({confidence:.0%}) | {remaining}s left")
                
            except Exception as e:
                print(f"Error: {e}")
            
            await asyncio.sleep(POLL_SECONDS)
    
    await http_client.aclose()
    print("Monitor complete. Log: monitor_log.jsonl")

if __name__ == "__main__":
    asyncio.run(main())
