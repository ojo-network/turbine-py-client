"""
Data types and models for the Turbine Python client.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional


class Side(IntEnum):
    """Order side: BUY or SELL."""

    BUY = 0
    SELL = 1


class Outcome(IntEnum):
    """Market outcome: YES or NO."""

    YES = 0
    NO = 1


@dataclass
class OrderArgs:
    """Arguments for creating a new order."""

    market_id: str
    side: Side
    outcome: Outcome
    price: int  # Price scaled by 1e6 (0 to 1,000,000)
    size: int  # Size in 6 decimals
    expiration: int  # Unix timestamp
    nonce: int = 0  # Auto-generated if 0
    maker_fee_recipient: str = "0x0000000000000000000000000000000000000000"

    def __post_init__(self) -> None:
        """Validate order arguments."""
        if not (1 <= self.price <= 999_999):
            raise ValueError(f"Price must be between 1 and 999999, got {self.price}")
        if self.size <= 0:
            raise ValueError(f"Size must be positive, got {self.size}")
        if self.expiration <= 0:
            raise ValueError(f"Expiration must be positive, got {self.expiration}")


@dataclass
class SignedOrder:
    """A signed order ready for submission."""

    market_id: str
    trader: str
    side: int
    outcome: int
    price: int
    size: int
    nonce: int
    expiration: int
    maker_fee_recipient: str
    signature: str
    order_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API submission."""
        # Ensure signature has 0x prefix
        sig = self.signature if self.signature.startswith("0x") else f"0x{self.signature}"
        return {
            "order": {
                "marketId": self.market_id,
                "trader": self.trader,
                "side": self.side,
                "outcome": self.outcome,
                "price": self.price,
                "size": self.size,
                "nonce": self.nonce,
                "expiration": self.expiration,
                "makerFeeRecipient": self.maker_fee_recipient,
            },
            "signature": sig,
        }


@dataclass
class PriceLevel:
    """A price level in the orderbook."""

    price: int
    size: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PriceLevel":
        """Create from API response dictionary."""
        return cls(
            price=int(data["price"]),
            size=int(data["size"]),
        )


@dataclass
class OrderBookSnapshot:
    """A snapshot of the orderbook for a market."""

    market_id: str
    bids: List[PriceLevel]
    asks: List[PriceLevel]
    last_update: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderBookSnapshot":
        """Create from API response dictionary."""
        return cls(
            market_id=data.get("marketId", ""),
            bids=[PriceLevel.from_dict(b) for b in data.get("bids", [])],
            asks=[PriceLevel.from_dict(a) for a in data.get("asks", [])],
            last_update=data.get("lastUpdate", 0),
        )


@dataclass
class Trade:
    """A trade execution."""

    market_id: str
    price: int
    size: int
    outcome: int
    side: int
    maker: str
    taker: str
    timestamp: int
    trade_hash: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trade":
        """Create from API response dictionary."""
        return cls(
            market_id=data.get("marketId", ""),
            price=int(data.get("price", 0)),
            size=int(data.get("size", 0)),
            outcome=int(data.get("outcome", 0)),
            side=int(data.get("side", 0)),
            maker=data.get("maker", ""),
            taker=data.get("taker", ""),
            timestamp=int(data.get("timestamp", 0)),
            trade_hash=data.get("tradeHash", ""),
        )


@dataclass
class Position:
    """A user's position in a market."""

    market_id: str
    user_address: str
    yes_shares: int
    no_shares: int
    invested: int
    last_trade_price: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """Create from API response dictionary."""
        return cls(
            market_id=data.get("marketId", ""),
            user_address=data.get("userAddress", ""),
            yes_shares=int(data.get("yesShares", 0)),
            no_shares=int(data.get("noShares", 0)),
            invested=int(data.get("invested", 0)),
            last_trade_price=int(data.get("lastTradePrice", 0)),
        )


@dataclass
class Market:
    """A prediction market."""

    id: str
    question: str
    description: str
    category: str
    expiration_time: int
    contract_address: str
    chain_id: int
    resolved: bool
    settlement_address: str = ""
    winning_outcome: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Market":
        """Create from API response dictionary."""
        return cls(
            id=data.get("id", ""),
            question=data.get("question", ""),
            description=data.get("description", ""),
            category=data.get("category", ""),
            expiration_time=int(data.get("expirationTime", data.get("expiration", 0))),
            contract_address=data.get("contractAddress", ""),
            chain_id=int(data.get("chainId", 0)),
            resolved=data.get("resolved", False),
            settlement_address=data.get("settlementAddress", ""),
            winning_outcome=data.get("winningOutcome"),
        )


@dataclass
class MarketStats:
    """Statistics for a market."""

    market_id: str
    volume_24h: int
    volume_total: int
    last_price: int
    price_change_24h: int
    open_interest: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketStats":
        """Create from API response dictionary."""
        return cls(
            market_id=data.get("marketId", ""),
            volume_24h=int(data.get("volume24h", 0)),
            volume_total=int(data.get("volumeTotal", 0)),
            last_price=int(data.get("lastPrice", 0)),
            price_change_24h=int(data.get("priceChange24h", 0)),
            open_interest=int(data.get("openInterest", 0)),
        )


@dataclass
class PlatformStats:
    """Platform-wide statistics."""

    market_count: int
    total_volume: int
    total_traders: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlatformStats":
        """Create from API response dictionary."""
        return cls(
            market_count=int(data.get("marketCount", 0)),
            total_volume=int(data.get("totalVolume", 0)),
            total_traders=int(data.get("totalTraders", 0)),
        )


@dataclass
class QuickMarket:
    """A quick market (15-minute BTC/ETH markets)."""

    market_id: str
    asset: str
    start_price: int  # Price in 8 decimals
    end_time: int
    resolved: bool
    winning_outcome: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuickMarket":
        """Create from API response dictionary."""
        return cls(
            market_id=data.get("marketId", ""),
            asset=data.get("asset", ""),
            start_price=int(data.get("startPrice", 0)),
            end_time=int(data.get("endTime", 0)),
            resolved=data.get("resolved", False),
            winning_outcome=data.get("winningOutcome"),
        )


@dataclass
class Order:
    """An order on the orderbook."""

    order_hash: str
    market_id: str
    trader: str
    side: int
    outcome: int
    price: int
    size: int
    filled_size: int
    remaining_size: int
    nonce: int
    expiration: int
    status: str
    created_at: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        """Create from API response dictionary."""
        return cls(
            order_hash=data.get("orderHash", ""),
            market_id=data.get("marketId", ""),
            trader=data.get("trader", ""),
            side=int(data.get("side", 0)),
            outcome=int(data.get("outcome", 0)),
            price=int(data.get("price", 0)),
            size=int(data.get("size", 0)),
            filled_size=int(data.get("filledSize", 0)),
            remaining_size=int(data.get("remainingSize", 0)),
            nonce=int(data.get("nonce", 0)),
            expiration=int(data.get("expiration", 0)),
            status=data.get("status", ""),
            created_at=int(data.get("createdAt", 0)),
        )


@dataclass
class UserActivity:
    """User trading activity."""

    address: str
    total_trades: int
    total_volume: int
    pnl: int
    markets_traded: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserActivity":
        """Create from API response dictionary."""
        return cls(
            address=data.get("address", ""),
            total_trades=int(data.get("totalTrades", 0)),
            total_volume=int(data.get("totalVolume", 0)),
            pnl=int(data.get("pnl", 0)),
            markets_traded=int(data.get("marketsTraded", 0)),
        )


# WebSocket message types
@dataclass
class WSMessage:
    """Base WebSocket message."""

    type: str
    market_id: Optional[str] = None
    data: Any = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WSMessage":
        """Create from WebSocket message dictionary."""
        return cls(
            type=data.get("type", ""),
            market_id=data.get("marketId"),
            data=data.get("data"),
        )


@dataclass
class OrderBookUpdate(WSMessage):
    """WebSocket orderbook update message."""

    @property
    def orderbook(self) -> Optional[OrderBookSnapshot]:
        """Get the orderbook snapshot from the message."""
        if self.data and isinstance(self.data, dict):
            return OrderBookSnapshot.from_dict({**self.data, "marketId": self.market_id})
        return None


@dataclass
class TradeUpdate(WSMessage):
    """WebSocket trade update message."""

    @property
    def trade(self) -> Optional[Trade]:
        """Get the trade from the message."""
        if self.data and isinstance(self.data, dict):
            return Trade.from_dict({**self.data, "marketId": self.market_id})
        return None


@dataclass
class QuickMarketUpdate(WSMessage):
    """WebSocket quick market update message."""

    @property
    def quick_market(self) -> Optional[QuickMarket]:
        """Get the quick market from the message."""
        if self.data and isinstance(self.data, dict):
            return QuickMarket.from_dict(self.data)
        return None
