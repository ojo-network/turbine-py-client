"""
Turbine Python Client

A Python client for market makers to interact with the Turbine CLOB prediction markets API.
"""

from turbine_client.client import TurbineClient
from turbine_client.types import (
    Market,
    OrderArgs,
    OrderBookSnapshot,
    Outcome,
    Position,
    PriceLevel,
    Side,
    SignedOrder,
    Trade,
)
from turbine_client.ws.client import TurbineWSClient
from turbine_client.exceptions import (
    AuthenticationError,
    OrderValidationError,
    SignatureError,
    TurbineApiError,
    TurbineError,
)

__version__ = "0.1.0"

__all__ = [
    # Main client
    "TurbineClient",
    "TurbineWSClient",
    # Types
    "OrderArgs",
    "SignedOrder",
    "Side",
    "Outcome",
    "Market",
    "Position",
    "Trade",
    "OrderBookSnapshot",
    "PriceLevel",
    # Exceptions
    "TurbineError",
    "TurbineApiError",
    "OrderValidationError",
    "SignatureError",
    "AuthenticationError",
]
