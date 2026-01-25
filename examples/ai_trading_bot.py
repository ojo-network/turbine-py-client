"""
Example: AI-powered trading bot for BTC 15-minute markets.

This example shows how to:
- Get the active BTC 15-minute quick market
- Stream real-time orderbook and trade data
- Use an LLM (OpenAI/Anthropic) to make trading decisions
- Execute trades based on AI analysis

WARNING: This is a simplified example for educational purposes.
Real algorithmic trading requires careful risk management,
backtesting, and thorough understanding of market dynamics.

Requirements:
    pip install openai  # or: pip install anthropic
"""

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from turbine_client import TurbineClient, TurbineWSClient, Outcome, Side
from turbine_client.exceptions import TurbineApiError, WebSocketError

# Load environment variables
load_dotenv()


def get_or_create_api_credentials(env_path: Path = None) -> tuple[str, str]:
    """Get existing API credentials or register new ones and save to .env."""
    if env_path is None:
        env_path = Path(__file__).parent / ".env"

    api_key_id = os.environ.get("TURBINE_API_KEY_ID")
    api_private_key = os.environ.get("TURBINE_API_PRIVATE_KEY")

    if api_key_id and api_private_key:
        print("Using existing API credentials")
        return api_key_id, api_private_key

    # Need to register new credentials
    private_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if not private_key:
        raise ValueError("Set TURBINE_PRIVATE_KEY in your .env file")

    print("Registering new API credentials...")
    credentials = TurbineClient.request_api_credentials(
        host="https://api.turbinefi.com",
        private_key=private_key,
    )

    api_key_id = credentials["api_key_id"]
    api_private_key = credentials["api_private_key"]

    # Auto-save to .env file
    _save_credentials_to_env(env_path, api_key_id, api_private_key)

    # Update current environment so we can use them immediately
    os.environ["TURBINE_API_KEY_ID"] = api_key_id
    os.environ["TURBINE_API_PRIVATE_KEY"] = api_private_key

    print(f"API credentials saved to {env_path}")
    return api_key_id, api_private_key


def _save_credentials_to_env(env_path: Path, api_key_id: str, api_private_key: str):
    """Save API credentials to .env file."""
    env_path = Path(env_path)

    if env_path.exists():
        content = env_path.read_text()
        # Update existing values or append if not present
        if "TURBINE_API_KEY_ID=" in content:
            content = re.sub(
                r'^TURBINE_API_KEY_ID=.*$',
                f'TURBINE_API_KEY_ID={api_key_id}',
                content,
                flags=re.MULTILINE
            )
        else:
            content += f"\nTURBINE_API_KEY_ID={api_key_id}"

        if "TURBINE_API_PRIVATE_KEY=" in content:
            content = re.sub(
                r'^TURBINE_API_PRIVATE_KEY=.*$',
                f'TURBINE_API_PRIVATE_KEY={api_private_key}',
                content,
                flags=re.MULTILINE
            )
        else:
            content += f"\nTURBINE_API_PRIVATE_KEY={api_private_key}"

        env_path.write_text(content)
    else:
        # Create new .env file with all credentials
        content = f"""# Turbine Trading Bot Configuration
TURBINE_PRIVATE_KEY={os.environ.get('TURBINE_PRIVATE_KEY', '')}
TURBINE_API_KEY_ID={api_key_id}
TURBINE_API_PRIVATE_KEY={api_private_key}
"""
        env_path.write_text(content)

# Configuration
MAX_POSITION_SIZE = 5_000_000  # 5 shares max position
ORDER_SIZE = 1_000_000  # 1 share per trade
ANALYSIS_INTERVAL_SECONDS = 60  # How often to ask AI for analysis
CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence to place a trade


@dataclass
class MarketState:
    """Current state of the market for AI analysis."""

    market_id: str
    asset: str
    strike_price: float  # USD
    time_remaining_seconds: int
    best_bid: Optional[float] = None  # Percentage
    best_ask: Optional[float] = None  # Percentage
    spread: Optional[float] = None
    recent_trades: list = None
    current_position: int = 0  # Positive = long YES, negative = short

    def __post_init__(self):
        if self.recent_trades is None:
            self.recent_trades = []

    def to_prompt(self) -> str:
        """Convert market state to a prompt for the AI."""
        trades_summary = ""
        if self.recent_trades:
            buys = sum(1 for t in self.recent_trades if t["side"] == "BUY")
            sells = len(self.recent_trades) - buys
            avg_price = sum(t["price"] for t in self.recent_trades) / len(self.recent_trades)
            trades_summary = f"""
Recent Trading Activity:
- Total trades: {len(self.recent_trades)}
- Buys: {buys}, Sells: {sells}
- Average trade price: {avg_price:.1f}%"""

        position_desc = "None"
        if self.current_position > 0:
            position_desc = f"Long {self.current_position / 1_000_000:.2f} YES shares"
        elif self.current_position < 0:
            position_desc = f"Short {abs(self.current_position) / 1_000_000:.2f} shares"

        return f"""
BTC 15-Minute Market Analysis Request

Market Details:
- Asset: {self.asset}
- Strike Price: ${self.strike_price:,.2f}
- Time Remaining: {self.time_remaining_seconds // 60} minutes {self.time_remaining_seconds % 60} seconds

Current Orderbook:
- Best Bid: {self.best_bid:.1f}% (probability BTC ends above strike)
- Best Ask: {self.best_ask:.1f}%
- Spread: {self.spread:.2f}%
{trades_summary}

Current Position: {position_desc}

This is a binary market that resolves YES if BTC price is above ${self.strike_price:,.2f} at expiration, NO otherwise.

Based on this market state, should we:
1. BUY YES (bet BTC goes up)
2. SELL YES (bet BTC goes down)
3. HOLD (no action)

Respond with JSON only:
{{"action": "BUY" | "SELL" | "HOLD", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}
"""


class AITradingBot:
    """AI-powered trading bot for BTC 15-minute markets."""

    def __init__(
        self,
        client: TurbineClient,
        ai_provider: str = "openai",
        model: str = None,
    ):
        self.client = client
        self.ai_provider = ai_provider
        self.model = model or self._default_model()
        self.ai_client = self._init_ai_client()

        self.market_state: Optional[MarketState] = None
        self.active_orders: dict[str, str] = {}

    def _default_model(self) -> str:
        if self.ai_provider == "anthropic":
            return "claude-sonnet-4-20250514"
        return "gpt-4o"

    def _init_ai_client(self):
        """Initialize the AI client based on provider."""
        if self.ai_provider == "anthropic":
            try:
                import anthropic

                return anthropic.Anthropic()
            except ImportError:
                raise ImportError("pip install anthropic")
        else:
            try:
                import openai

                return openai.OpenAI()
            except ImportError:
                raise ImportError("pip install openai")

    def get_ai_decision(self, market_state: MarketState) -> dict:
        """Get trading decision from AI."""
        prompt = market_state.to_prompt()

        try:
            if self.ai_provider == "anthropic":
                response = self.ai_client.messages.create(
                    model=self.model,
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}],
                )
                content = response.content[0].text
            else:
                response = self.ai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a trading analyst. Respond only with valid JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=256,
                )
                content = response.choices[0].message.content

            # Parse JSON from response
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)

        except Exception as e:
            print(f"AI error: {e}")
            return {"action": "HOLD", "confidence": 0.0, "reasoning": f"Error: {e}"}

    async def execute_decision(self, decision: dict) -> None:
        """Execute the AI's trading decision."""
        action = decision.get("action", "HOLD")
        confidence = decision.get("confidence", 0.0)
        reasoning = decision.get("reasoning", "")

        print(f"\nAI Decision: {action} (confidence: {confidence:.0%})")
        print(f"Reasoning: {reasoning}")

        if action == "HOLD" or confidence < CONFIDENCE_THRESHOLD:
            print("No trade executed (HOLD or low confidence)")
            return

        # Check position limits
        if action == "BUY" and self.market_state.current_position >= MAX_POSITION_SIZE:
            print("Position limit reached, cannot buy more")
            return
        if action == "SELL" and self.market_state.current_position <= -MAX_POSITION_SIZE:
            print("Position limit reached, cannot sell more")
            return

        # Calculate order price (use best price with small improvement)
        if action == "BUY":
            price = int((self.market_state.best_bid + 0.5) * 10000)  # Bid + 0.5%
            price = min(price, 990000)  # Cap at 99%
        else:
            price = int((self.market_state.best_ask - 0.5) * 10000)  # Ask - 0.5%
            price = max(price, 10000)  # Floor at 1%

        try:
            if action == "BUY":
                order = self.client.create_limit_buy(
                    market_id=self.market_state.market_id,
                    outcome=Outcome.YES,
                    price=price,
                    size=ORDER_SIZE,
                    expiration=int(time.time()) + 300,  # 5 min expiry
                )
            else:
                order = self.client.create_limit_sell(
                    market_id=self.market_state.market_id,
                    outcome=Outcome.YES,
                    price=price,
                    size=ORDER_SIZE,
                    expiration=int(time.time()) + 300,
                )

            result = self.client.post_order(order)
            self.active_orders[order.order_hash] = action
            print(f"Order placed: {action} @ {price / 10000:.1f}%")
            print(f"Order hash: {order.order_hash[:16]}...")

            # Update position tracking (simplified - assumes fill)
            if action == "BUY":
                self.market_state.current_position += ORDER_SIZE
            else:
                self.market_state.current_position -= ORDER_SIZE

        except TurbineApiError as e:
            print(f"Order failed: {e}")

    def update_from_orderbook(self, orderbook) -> None:
        """Update market state from orderbook."""
        if not self.market_state:
            return

        if orderbook.bids:
            self.market_state.best_bid = orderbook.bids[0].price / 10000
        if orderbook.asks:
            self.market_state.best_ask = orderbook.asks[0].price / 10000

        if self.market_state.best_bid and self.market_state.best_ask:
            self.market_state.spread = self.market_state.best_ask - self.market_state.best_bid

    def update_from_trade(self, trade) -> None:
        """Record recent trade."""
        if not self.market_state:
            return

        self.market_state.recent_trades.append(
            {
                "price": trade.price / 10000,
                "size": trade.size / 1_000_000,
                "side": "BUY" if trade.side == 0 else "SELL",
                "time": trade.timestamp,
            }
        )
        # Keep only last 20 trades
        self.market_state.recent_trades = self.market_state.recent_trades[-20:]

    async def cancel_all_orders(self) -> None:
        """Cancel all active orders."""
        for order_hash in list(self.active_orders.keys()):
            try:
                self.client.cancel_order(order_hash)
                print(f"Canceled: {order_hash[:16]}...")
                del self.active_orders[order_hash]
            except TurbineApiError:
                pass

    async def run(self, ws_host: str) -> None:
        """Main bot loop."""
        print("=" * 60)
        print("AI Trading Bot for BTC 15-Minute Markets")
        print("=" * 60)
        print(f"AI Provider: {self.ai_provider} ({self.model})")
        print(f"Order Size: {ORDER_SIZE / 1_000_000:.2f} shares")
        print(f"Confidence Threshold: {CONFIDENCE_THRESHOLD:.0%}")
        print()

        ws = TurbineWSClient(host=ws_host)

        while True:
            try:
                # Get current quick market
                print("Fetching active BTC quick market...")
                quick_market = self.client.get_quick_market("BTC")
                market = self.client.get_market(quick_market.market_id)

                time_remaining = max(0, quick_market.end_time - int(time.time()))

                self.market_state = MarketState(
                    market_id=quick_market.market_id,
                    asset=quick_market.asset,
                    strike_price=quick_market.start_price / 1e8,
                    time_remaining_seconds=time_remaining,
                )

                print(f"Market: {market.question}")
                print(f"Strike: ${self.market_state.strike_price:,.2f}")
                print(f"Expires in: {time_remaining // 60}m {time_remaining % 60}s")
                print()

                # Subscribe and trade
                async with ws.connect() as stream:
                    await stream.subscribe_orderbook(quick_market.market_id)
                    await stream.subscribe_trades(quick_market.market_id)
                    print("Subscribed to market data")

                    last_analysis = 0

                    async for message in stream:
                        # Update time remaining
                        self.market_state.time_remaining_seconds = max(
                            0, quick_market.end_time - int(time.time())
                        )

                        # Check if market expired
                        if self.market_state.time_remaining_seconds <= 30:
                            print("\nMarket expiring soon, canceling orders...")
                            await self.cancel_all_orders()
                            break

                        # Process market data
                        if message.type == "orderbook":
                            if hasattr(message, "orderbook") and message.orderbook:
                                self.update_from_orderbook(message.orderbook)

                        elif message.type == "trade":
                            if hasattr(message, "trade") and message.trade:
                                self.update_from_trade(message.trade)
                                trade = message.trade
                                side = "BUY" if trade.side == 0 else "SELL"
                                print(
                                    f"  Trade: {side} {trade.size / 1_000_000:.2f} "
                                    f"@ {trade.price / 10000:.1f}%"
                                )

                        # Periodic AI analysis
                        if (
                            time.time() - last_analysis > ANALYSIS_INTERVAL_SECONDS
                            and self.market_state.best_bid is not None
                            and self.market_state.time_remaining_seconds > 60
                        ):
                            print("\n" + "-" * 40)
                            print("Running AI analysis...")
                            decision = self.get_ai_decision(self.market_state)
                            await self.execute_decision(decision)
                            last_analysis = time.time()
                            print("-" * 40)

                # Market ended, wait for next one
                print("\nWaiting for next market...")
                await asyncio.sleep(30)

            except WebSocketError as e:
                print(f"WebSocket error: {e}")
                await asyncio.sleep(5)
            except KeyboardInterrupt:
                print("\nShutting down...")
                await self.cancel_all_orders()
                break
            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(5)


async def main():
    # Get credentials
    private_key = os.environ.get("TURBINE_PRIVATE_KEY")
    if not private_key:
        print("Error: Set TURBINE_PRIVATE_KEY in your .env file")
        return

    # Check for AI provider
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: Set one of these for AI:")
        print("  OPENAI_API_KEY (for OpenAI)")
        print("  ANTHROPIC_API_KEY (for Anthropic)")
        return

    # Get or create API credentials (auto-saves to .env)
    try:
        api_key_id, api_private_key = get_or_create_api_credentials()
    except TurbineApiError as e:
        print(f"Error getting API credentials: {e}")
        return

    # Determine AI provider
    ai_provider = "openai"
    if os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        ai_provider = "anthropic"

    # Create client
    host = "https://api.turbinefi.com"
    client = TurbineClient(
        host=host,
        chain_id=137,
        private_key=private_key,
        api_key_id=api_key_id,
        api_private_key=api_private_key,
    )

    print(f"Bot Address: {client.address}")

    # Run bot
    bot = AITradingBot(client, ai_provider=ai_provider)

    try:
        await bot.run(host)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
