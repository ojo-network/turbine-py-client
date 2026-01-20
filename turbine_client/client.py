"""
Main Turbine client for interacting with the CLOB API.
"""

from typing import Any, Dict, List, Optional, Tuple

from turbine_client.auth import BearerTokenAuth, create_bearer_auth
from turbine_client.config import get_chain_config
from turbine_client.constants import ENDPOINTS
from turbine_client.exceptions import AuthenticationError, TurbineApiError
from turbine_client.http import HttpClient
from turbine_client.order_builder import OrderBuilder
from turbine_client.signer import Signer, create_signer
from turbine_client.types import (
    Market,
    MarketStats,
    Order,
    OrderArgs,
    OrderBookSnapshot,
    Outcome,
    PlatformStats,
    Position,
    QuickMarket,
    Side,
    SignedOrder,
    Trade,
    UserActivity,
)


class TurbineClient:
    """Client for interacting with the Turbine CLOB API.

    The client supports three access levels:
    - Level 0 (Public): No authentication, read-only market data
    - Level 1 (Signing): Private key for order signing
    - Level 2 (Full): Private key + API credentials for all endpoints
    """

    def __init__(
        self,
        host: str,
        chain_id: int,
        private_key: Optional[str] = None,
        api_key_id: Optional[str] = None,
        api_private_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the Turbine client.

        Args:
            host: The API host URL.
            chain_id: The blockchain chain ID.
            private_key: Optional wallet private key for order signing.
            api_key_id: Optional API key ID for bearer token auth.
            api_private_key: Optional Ed25519 private key for bearer tokens.
            timeout: HTTP request timeout in seconds.
        """
        self._host = host.rstrip("/")
        self._chain_id = chain_id
        self._chain_config = get_chain_config(chain_id)

        # Initialize signer if private key provided
        self._signer: Optional[Signer] = None
        self._order_builder: Optional[OrderBuilder] = None
        if private_key:
            self._signer = create_signer(private_key, chain_id)
            self._order_builder = OrderBuilder(self._signer)

        # Initialize bearer auth if API credentials provided
        self._auth: Optional[BearerTokenAuth] = None
        if api_key_id and api_private_key:
            self._auth = create_bearer_auth(api_key_id, api_private_key)

        # Initialize HTTP client
        self._http = HttpClient(host, auth=self._auth, timeout=timeout)

    def close(self) -> None:
        """Close the client and release resources."""
        self._http.close()

    def __enter__(self) -> "TurbineClient":
        """Enter context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager."""
        self.close()

    @property
    def host(self) -> str:
        """Get the API host URL."""
        return self._host

    @property
    def chain_id(self) -> int:
        """Get the chain ID."""
        return self._chain_id

    @property
    def address(self) -> Optional[str]:
        """Get the wallet address if a signer is configured."""
        return self._signer.address if self._signer else None

    @property
    def can_sign(self) -> bool:
        """Check if the client can sign orders."""
        return self._signer is not None

    @property
    def has_auth(self) -> bool:
        """Check if the client has bearer token authentication."""
        return self._auth is not None

    def _require_signer(self) -> None:
        """Ensure a signer is configured.

        Raises:
            AuthenticationError: If no signer is configured.
        """
        if not self._signer:
            raise AuthenticationError(
                "Private key required for this operation",
                required_level="signing",
            )

    def _require_auth(self) -> None:
        """Ensure bearer token auth is configured.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        if not self._auth:
            raise AuthenticationError(
                "API credentials required for this operation",
                required_level="bearer token",
            )

    # =========================================================================
    # Public Endpoints (No Auth Required)
    # =========================================================================

    def get_health(self) -> Dict[str, Any]:
        """Check API health.

        Returns:
            Health status response.
        """
        return self._http.get(ENDPOINTS["health"])

    def get_markets(self, chain_id: Optional[int] = None) -> List[Market]:
        """Get all markets.

        Args:
            chain_id: Optional chain ID to filter markets.

        Returns:
            List of markets.
        """
        params = {}
        if chain_id is not None:
            params["chain_id"] = chain_id

        response = self._http.get(ENDPOINTS["markets"], params=params or None)
        markets = response.get("markets", []) if isinstance(response, dict) else response
        return [Market.from_dict(m) for m in markets]

    def get_market(self, market_id: str) -> Market:
        """Get a specific market.

        Args:
            market_id: The market ID.

        Returns:
            The market.
        """
        endpoint = ENDPOINTS["market"].format(market_id=market_id)
        response = self._http.get(endpoint)
        return Market.from_dict(response)

    def get_orderbook(
        self,
        market_id: str,
        outcome: Optional[Outcome] = None,
    ) -> OrderBookSnapshot:
        """Get the orderbook for a market.

        Args:
            market_id: The market ID.
            outcome: Optional outcome to filter (YES or NO).

        Returns:
            The orderbook snapshot.
        """
        endpoint = ENDPOINTS["orderbook"].format(market_id=market_id)
        params = {}
        if outcome is not None:
            params["outcome"] = int(outcome)

        response = self._http.get(endpoint, params=params or None)
        return OrderBookSnapshot.from_dict(response)

    def get_trades(self, market_id: str, limit: int = 100) -> List[Trade]:
        """Get recent trades for a market.

        Args:
            market_id: The market ID.
            limit: Maximum number of trades to return.

        Returns:
            List of trades.
        """
        endpoint = ENDPOINTS["trades"].format(market_id=market_id)
        params = {"limit": limit}
        response = self._http.get(endpoint, params=params)
        trades = response.get("trades", []) if isinstance(response, dict) else response
        return [Trade.from_dict(t) for t in (trades or [])]

    def get_stats(self, market_id: str) -> MarketStats:
        """Get statistics for a market.

        Args:
            market_id: The market ID.

        Returns:
            Market statistics.
        """
        endpoint = ENDPOINTS["stats"].format(market_id=market_id)
        response = self._http.get(endpoint)
        return MarketStats.from_dict(response)

    def get_platform_stats(self) -> PlatformStats:
        """Get platform-wide statistics.

        Returns:
            Platform statistics.
        """
        response = self._http.get(ENDPOINTS["platform_stats"])
        return PlatformStats.from_dict(response)

    def get_holders(self, market_id: str, limit: int = 100) -> List[Position]:
        """Get top position holders for a market.

        Args:
            market_id: The market ID.
            limit: Maximum number of holders to return.

        Returns:
            List of positions.
        """
        endpoint = ENDPOINTS["holders"].format(market_id=market_id)
        params = {"limit": limit}
        response = self._http.get(endpoint, params=params)
        holders = response.get("holders", []) if isinstance(response, dict) else response
        return [Position.from_dict(h) for h in holders]

    def get_quick_market(self, asset: str) -> QuickMarket:
        """Get the active quick market for an asset.

        Args:
            asset: The asset symbol (e.g., "BTC", "ETH").

        Returns:
            The active quick market.
        """
        endpoint = ENDPOINTS["quick_market"].format(asset=asset)
        response = self._http.get(endpoint)
        # API returns {"quickMarket": {...}} nested structure
        quick_market_data = response.get("quickMarket", response)
        return QuickMarket.from_dict(quick_market_data)

    def get_quick_market_history(self, asset: str, limit: int = 100) -> List[QuickMarket]:
        """Get quick market history for an asset.

        Args:
            asset: The asset symbol.
            limit: Maximum number of markets to return.

        Returns:
            List of historical quick markets.
        """
        endpoint = ENDPOINTS["quick_market_history"].format(asset=asset)
        params = {"limit": limit}
        response = self._http.get(endpoint, params=params)
        markets = response.get("markets", []) if isinstance(response, dict) else response
        return [QuickMarket.from_dict(m) for m in markets]

    # =========================================================================
    # Order Management (Requires Signing)
    # =========================================================================

    def create_order(
        self, order_args: OrderArgs, settlement_address: Optional[str] = None
    ) -> SignedOrder:
        """Create and sign an order.

        Args:
            order_args: The order arguments.
            settlement_address: Optional settlement contract address. If not provided,
                               will be fetched from the market.

        Returns:
            A signed order ready for submission.

        Raises:
            AuthenticationError: If no private key is configured.
        """
        self._require_signer()
        assert self._order_builder is not None

        # Fetch settlement address from market if not provided
        if not settlement_address:
            market = self.get_market(order_args.market_id)
            settlement_address = market.settlement_address

        return self._order_builder.create_order_from_args(
            order_args, settlement_address=settlement_address
        )

    def create_limit_buy(
        self,
        market_id: str,
        outcome: Outcome,
        price: int,
        size: int,
        expiration: Optional[int] = None,
        settlement_address: Optional[str] = None,
    ) -> SignedOrder:
        """Create a limit buy order.

        Args:
            market_id: The market ID.
            outcome: YES or NO.
            price: Price scaled by 1e6.
            size: Size with 6 decimals.
            expiration: Optional expiration timestamp.
            settlement_address: Optional settlement contract address. If not provided,
                               will be fetched from the market.

        Returns:
            A signed buy order.
        """
        self._require_signer()
        assert self._order_builder is not None

        # Fetch settlement address from market if not provided
        if not settlement_address:
            market = self.get_market(market_id)
            settlement_address = market.settlement_address

        return self._order_builder.create_limit_buy(
            market_id=market_id,
            outcome=outcome,
            price=price,
            size=size,
            expiration=expiration,
            settlement_address=settlement_address,
        )

    def create_limit_sell(
        self,
        market_id: str,
        outcome: Outcome,
        price: int,
        size: int,
        expiration: Optional[int] = None,
        settlement_address: Optional[str] = None,
    ) -> SignedOrder:
        """Create a limit sell order.

        Args:
            market_id: The market ID.
            outcome: YES or NO.
            price: Price scaled by 1e6.
            size: Size with 6 decimals.
            expiration: Optional expiration timestamp.
            settlement_address: Optional settlement contract address. If not provided,
                               will be fetched from the market.

        Returns:
            A signed sell order.
        """
        self._require_signer()
        assert self._order_builder is not None

        # Fetch settlement address from market if not provided
        if not settlement_address:
            market = self.get_market(market_id)
            settlement_address = market.settlement_address

        return self._order_builder.create_limit_sell(
            market_id=market_id,
            outcome=outcome,
            price=price,
            size=size,
            expiration=expiration,
            settlement_address=settlement_address,
        )

    # =========================================================================
    # Authenticated Endpoints (Requires Bearer Token)
    # =========================================================================

    def post_order(self, signed_order: SignedOrder) -> Dict[str, Any]:
        """Submit a signed order to the orderbook.

        Args:
            signed_order: The signed order.

        Returns:
            The order submission response.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        return self._http.post(
            ENDPOINTS["orders"],
            data=signed_order.to_dict(),
            authenticated=True,
        )

    def get_orders(
        self,
        trader: Optional[str] = None,
        market_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Order]:
        """Get orders.

        Args:
            trader: Optional trader address to filter.
            market_id: Optional market ID to filter.
            status: Optional status to filter ("open", "filled", "cancelled").

        Returns:
            List of orders.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        params = {}
        if trader:
            params["trader"] = trader
        if market_id:
            params["market_id"] = market_id
        if status:
            params["status"] = status

        response = self._http.get(
            ENDPOINTS["orders"],
            params=params or None,
            authenticated=True,
        )
        orders = response.get("orders", []) if isinstance(response, dict) else response
        return [Order.from_dict(o) for o in orders]

    def get_order(self, order_hash: str) -> Order:
        """Get a specific order by hash.

        Args:
            order_hash: The order hash.

        Returns:
            The order.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        endpoint = ENDPOINTS["order"].format(order_hash=order_hash)
        response = self._http.get(endpoint, authenticated=True)
        return Order.from_dict(response)

    def cancel_order(
        self,
        order_hash: str,
        market_id: Optional[str] = None,
        side: Optional[Side] = None,
    ) -> Dict[str, Any]:
        """Cancel an order.

        Args:
            order_hash: The order hash.
            market_id: Optional market ID (for validation).
            side: Optional side (for validation).

        Returns:
            The cancellation response.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        endpoint = ENDPOINTS["order"].format(order_hash=order_hash)
        params = {}
        if market_id:
            params["marketId"] = market_id
        if side is not None:
            # API expects "buy" or "sell" as string
            params["side"] = "buy" if side == Side.BUY else "sell"

        return self._http.delete(endpoint, params=params or None, authenticated=True)

    def cancel_market_orders(self, market_id: str) -> Dict[str, Any]:
        """Cancel all orders for a market.

        Args:
            market_id: The market ID.

        Returns:
            The cancellation response.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        return self._http.delete(
            ENDPOINTS["orders"],
            params={"marketId": market_id},
            authenticated=True,
        )

    def get_positions(
        self,
        market_id: str,
        user_address: Optional[str] = None,
    ) -> List[Position]:
        """Get positions for a market.

        Args:
            market_id: The market ID.
            user_address: Optional user address to filter.

        Returns:
            List of positions.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        endpoint = ENDPOINTS["positions"].format(market_id=market_id)
        params = {}
        if user_address:
            params["user"] = user_address

        response = self._http.get(endpoint, params=params or None, authenticated=True)
        positions = response.get("positions", []) if isinstance(response, dict) else response
        return [Position.from_dict(p) for p in positions]

    def get_user_positions(
        self,
        address: str,
        chain_id: Optional[int] = None,
    ) -> List[Position]:
        """Get all positions for a user.

        Args:
            address: The user's address.
            chain_id: Optional chain ID to filter.

        Returns:
            List of positions.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        endpoint = ENDPOINTS["user_positions"].format(address=address)
        params = {}
        if chain_id is not None:
            params["chain_id"] = chain_id

        response = self._http.get(endpoint, params=params or None, authenticated=True)
        positions = response.get("positions", []) if isinstance(response, dict) else response
        return [Position.from_dict(p) for p in positions]

    def get_user_orders(
        self,
        address: str,
        status: Optional[str] = None,
    ) -> List[Order]:
        """Get all orders for a user.

        Args:
            address: The user's address.
            status: Optional status to filter.

        Returns:
            List of orders.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        endpoint = ENDPOINTS["user_orders"].format(address=address)
        params = {}
        if status:
            params["status"] = status

        response = self._http.get(endpoint, params=params or None, authenticated=True)
        orders = response.get("orders", []) if isinstance(response, dict) else response
        return [Order.from_dict(o) for o in orders]

    def get_user_activity(self, address: str) -> UserActivity:
        """Get trading activity for a user.

        Args:
            address: The user's address.

        Returns:
            User activity summary.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        endpoint = ENDPOINTS["user_activity"].format(address=address)
        response = self._http.get(endpoint, authenticated=True)
        return UserActivity.from_dict(response)

    # =========================================================================
    # Relayer Endpoints (Gasless Operations)
    # =========================================================================

    def request_ctf_approval(
        self,
        owner: str,
        spender: str,
        value: int,
        deadline: int,
        v: int,
        r: str,
        s: str,
    ) -> Dict[str, Any]:
        """Request gasless CTF token approval via relayer.

        Args:
            owner: The token owner address.
            spender: The spender address.
            value: The approval amount.
            deadline: The permit deadline.
            v: Signature v value.
            r: Signature r value.
            s: Signature s value.

        Returns:
            The relayer response.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        data = {
            "owner": owner,
            "spender": spender,
            "value": str(value),
            "deadline": str(deadline),
            "v": v,
            "r": r,
            "s": s,
        }
        return self._http.post(ENDPOINTS["ctf_approval"], data=data, authenticated=True)

    def request_ctf_redemption(
        self,
        market_id: str,
        amount: int,
    ) -> Dict[str, Any]:
        """Request gasless CTF token redemption via relayer.

        Args:
            market_id: The market ID.
            amount: The amount to redeem.

        Returns:
            The relayer response.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        data = {
            "marketId": market_id,
            "amount": str(amount),
        }
        return self._http.post(ENDPOINTS["ctf_redemption"], data=data, authenticated=True)
