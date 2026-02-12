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
    AssetPrice,
    ClaimablePosition,
    FailedClaim,
    FailedTrade,
    Holder,
    Market,
    MarketStats,
    Order,
    OrderArgs,
    OrderBookSnapshot,
    Outcome,
    PendingClaim,
    PendingTrade,
    PermitSignature,
    PlatformStats,
    Position,
    QuickMarket,
    Resolution,
    SettlementStatus,
    Side,
    SignedOrder,
    Trade,
    UserActivity,
    UserStats,
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

        # Local permit nonce tracking for high-throughput scenarios
        # Key: (owner_address, contract_address), Value: next nonce to use
        self._permit_nonces: Dict[Tuple[str, str], int] = {}

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

    def get_market(self, market_id: str) -> MarketStats:
        """Get stats for a specific market.

        Args:
            market_id: The market ID.

        Returns:
            The market stats.
        """
        endpoint = ENDPOINTS["stats"].format(market_id=market_id)
        response = self._http.get(endpoint)
        return MarketStats.from_dict(response)

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

    def get_holders(self, market_id: str, limit: int = 100) -> List[Holder]:
        """Get top position holders for a market.

        Args:
            market_id: The market ID.
            limit: Maximum number of holders to return.

        Returns:
            List of top holders.
        """
        endpoint = ENDPOINTS["holders"].format(market_id=market_id)
        params = {"limit": limit}
        response = self._http.get(endpoint, params=params)
        holders = response.get("topHolders", []) if isinstance(response, dict) else response
        return [Holder.from_dict(h) for h in holders]

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

    def get_quick_market_price(self, asset: str) -> AssetPrice:
        """Get the current price for an asset.

        Args:
            asset: The asset symbol (e.g., "BTC", "ETH").

        Returns:
            The current asset price.
        """
        endpoint = ENDPOINTS["quick_market_price"].format(asset=asset)
        response = self._http.get(endpoint)
        return AssetPrice.from_dict(response)

    def get_quick_market_price_history(
        self, asset: str, limit: int = 100
    ) -> List[AssetPrice]:
        """Get price history for an asset.

        Args:
            asset: The asset symbol (e.g., "BTC", "ETH").
            limit: Maximum number of prices to return.

        Returns:
            List of historical prices.
        """
        endpoint = ENDPOINTS["quick_market_price_history"].format(asset=asset)
        params = {"limit": limit}
        response = self._http.get(endpoint, params=params)
        prices = response if isinstance(response, list) else response.get("prices", [])
        return [AssetPrice.from_dict(p) for p in prices]

    def get_resolution(self, market_id: str) -> Resolution:
        """Get resolution status for a market.

        Args:
            market_id: The market ID.

        Returns:
            The resolution status.
        """
        endpoint = ENDPOINTS["resolution"].format(market_id=market_id)
        response = self._http.get(endpoint)
        return Resolution.from_dict(response)

    def get_failed_trades(self) -> List[FailedTrade]:
        """Get all failed trades.

        Returns:
            List of failed trades.
        """
        response = self._http.get(ENDPOINTS["failed_trades"])
        trades = response.get("failedTrades", []) if isinstance(response, dict) else response
        return [FailedTrade.from_dict(t) for t in trades]

    def get_pending_trades(self) -> List[PendingTrade]:
        """Get all pending trades.

        Returns:
            List of pending trades.
        """
        response = self._http.get(ENDPOINTS["pending_trades"])
        trades = response.get("pendingTrades", []) if isinstance(response, dict) else response
        return [PendingTrade.from_dict(t) for t in trades]

    def get_failed_claims(self) -> List[FailedClaim]:
        """Get all failed claims.

        Returns:
            List of failed claims.
        """
        response = self._http.get(ENDPOINTS["failed_claims"])
        claims = response if isinstance(response, list) else response.get("failedClaims", [])
        return [FailedClaim.from_dict(c) for c in claims]

    def get_pending_claims(self) -> List[PendingClaim]:
        """Get all pending claims.

        Returns:
            List of pending claims.
        """
        response = self._http.get(ENDPOINTS["pending_claims"])
        claims = response if isinstance(response, list) else response.get("pendingClaims", [])
        return [PendingClaim.from_dict(c) for c in claims]

    def get_settlement_status(self, tx_hash: str) -> SettlementStatus:
        """Get settlement status for a transaction.

        Args:
            tx_hash: The transaction hash.

        Returns:
            The settlement status.
        """
        endpoint = ENDPOINTS["settlement_status"].format(tx_hash=tx_hash)
        response = self._http.get(endpoint)
        return SettlementStatus.from_dict(response)

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

    def get_user_stats(self) -> UserStats:
        """Get statistics for the authenticated user.

        Returns:
            User statistics including total cost, invested, position value, and PNL.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        response = self._http.get(ENDPOINTS["user_stats"], authenticated=True)
        return UserStats.from_dict(response)

    # =========================================================================
    # Relayer Endpoints (Gasless Operations)
    # =========================================================================

    def request_ctf_approval(
        self,
        owner: str,
        operator: str,
        approved: bool,
        deadline: int,
        v: int,
        r: str,
        s: str,
    ) -> Dict[str, Any]:
        """Request gasless CTF token approval via relayer.

        Args:
            owner: The token owner address.
            operator: The operator/settlement address to approve.
            approved: Whether to approve or revoke.
            deadline: The permit deadline timestamp.
            v: Signature v value.
            r: Signature r value (hex string with 0x prefix).
            s: Signature s value (hex string with 0x prefix).

        Returns:
            The relayer response with tx_hash on success.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        data = {
            "chainId": self._chain_id,
            "owner": owner,
            "operator": operator,
            "approved": approved,
            "deadline": str(deadline),
            "v": v,
            "r": r,
            "s": s,
        }
        return self._http.post(ENDPOINTS["ctf_approval"], data=data, authenticated=True)

    def approve_ctf_for_settlement(
        self,
        settlement_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a settlement contract to transfer CTF tokens using gasless permit.

        This signs an EIP-712 permit message and submits it to the relayer for
        gasless execution. No gas is required from the user.

        Args:
            settlement_address: The settlement contract to approve. If not provided,
                               uses the default for the chain.

        Returns:
            The relayer response with tx_hash on success.

        Raises:
            AuthenticationError: If no signer is configured.
        """
        self._require_signer()
        self._require_auth()

        import time
        from eth_account import Account
        from eth_account.messages import encode_typed_data

        # Get addresses
        owner = self._signer.address
        operator = settlement_address or self._chain_config.settlement_address
        ctf_address = self._chain_config.ctf_address

        # Get nonce from CTF contract (we'll need to query this)
        # For now, use 0 - the relayer should handle nonce management
        # In production, you'd query the contract's nonces(owner) view function
        nonce = self._get_ctf_nonce(owner, ctf_address)

        # Set deadline to 1 hour from now
        deadline = int(time.time()) + 3600

        # Build EIP-712 typed data for SetApprovalForAll
        typed_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "SetApprovalForAll": [
                    {"name": "owner", "type": "address"},
                    {"name": "operator", "type": "address"},
                    {"name": "approved", "type": "bool"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            "primaryType": "SetApprovalForAll",
            "domain": {
                "name": "ConditionalTokensWithPermit",
                "version": "1",
                "chainId": self._chain_id,
                "verifyingContract": ctf_address,
            },
            "message": {
                "owner": owner,
                "operator": operator,
                "approved": True,
                "nonce": nonce,
                "deadline": deadline,
            },
        }

        # Sign the typed data
        signed = Account.sign_typed_data(
            self._signer._account.key,
            full_message=typed_data,
        )

        # Extract v, r, s from signature
        v = signed.v
        r = hex(signed.r)
        s = hex(signed.s)

        # Pad r and s to 66 characters (0x + 64 hex chars)
        r = "0x" + r[2:].zfill(64)
        s = "0x" + s[2:].zfill(64)

        print(f"Submitting CTF approval permit...")
        print(f"  Owner: {owner}")
        print(f"  Operator: {operator}")
        print(f"  Deadline: {deadline}")

        # Submit to relayer
        return self.request_ctf_approval(
            owner=owner,
            operator=operator,
            approved=True,
            deadline=deadline,
            v=v,
            r=r,
            s=s,
        )

    def request_usdc_permit(
        self,
        owner: str,
        spender: str,
        value: int,
        deadline: int,
        v: int,
        r: str,
        s: str,
    ) -> Dict[str, Any]:
        """Submit a USDC permit to the relayer for gasless approval.

        Args:
            owner: The token owner address.
            spender: The spender (settlement contract) address.
            value: The approved amount.
            deadline: The permit deadline timestamp.
            v: Signature v value.
            r: Signature r value (hex string with 0x prefix).
            s: Signature s value (hex string with 0x prefix).

        Returns:
            The relayer response with tx_hash on success.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        data = {
            "chainId": self._chain_id,
            "owner": owner,
            "spender": spender,
            "value": str(value),
            "deadline": str(deadline),
            "v": v,
            "r": r,
            "s": s,
        }
        return self._http.post(ENDPOINTS["usdc_permit"], data=data, authenticated=True)

    def approve_usdc_for_settlement(
        self,
        settlement_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve USDC spending for a settlement contract using gasless permit.

        Signs an EIP-2612 max permit (max value, max deadline) and submits it
        to the relayer for gasless execution. No native gas is required.

        Args:
            settlement_address: The settlement contract to approve. If not provided,
                               uses the default for the chain.

        Returns:
            The relayer response with tx_hash on success.

        Raises:
            AuthenticationError: If no signer is configured.
        """
        self._require_signer()
        self._require_auth()

        from eth_account import Account

        MAX_UINT256 = 2**256 - 1

        owner = self._signer.address
        spender = settlement_address or self._chain_config.settlement_address
        usdc_address = self._chain_config.usdc_address

        # Get nonce from USDC contract
        nonce = self._get_contract_nonce(owner, usdc_address)

        # USDC EIP-712 domain varies by network
        is_testnet = self._chain_id in [84532]  # Base Sepolia
        token_name = "Mock USDC" if is_testnet else "USD Coin"
        token_version = "1" if is_testnet else "2"

        typed_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "Permit": [
                    {"name": "owner", "type": "address"},
                    {"name": "spender", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            "primaryType": "Permit",
            "domain": {
                "name": token_name,
                "version": token_version,
                "chainId": self._chain_id,
                "verifyingContract": usdc_address,
            },
            "message": {
                "owner": owner,
                "spender": spender,
                "value": MAX_UINT256,
                "nonce": nonce,
                "deadline": MAX_UINT256,
            },
        }

        # Sign the typed data
        signed = Account.sign_typed_data(
            self._signer._account.key,
            full_message=typed_data,
        )

        # Extract v, r, s
        v = signed.v
        r = "0x" + hex(signed.r)[2:].zfill(64)
        s = "0x" + hex(signed.s)[2:].zfill(64)

        print(f"Submitting USDC max permit...")
        print(f"  Owner: {owner}")
        print(f"  Spender: {spender}")

        # Submit to relayer
        return self.request_usdc_permit(
            owner=owner,
            spender=spender,
            value=MAX_UINT256,
            deadline=MAX_UINT256,
            v=v,
            r=r,
            s=s,
        )

    def _get_ctf_nonce(self, owner: str, ctf_address: str) -> int:
        """Get the current nonce for an owner from the CTF contract.

        This requires an RPC call to the CTF contract's nonces() view function.
        """
        return self._get_contract_nonce(owner, ctf_address)

    def _get_contract_nonce(self, owner: str, contract_address: str) -> int:
        """Get the current nonce for an owner from a contract's nonces() function."""
        from web3 import Web3

        # Get RPC URL based on chain
        rpc_urls = {
            137: "https://polygon-rpc.com",
            43114: "https://api.avax.network/ext/bc/C/rpc",
            84532: "https://sepolia.base.org",
        }
        rpc_url = rpc_urls.get(self._chain_id)
        if not rpc_url:
            print(f"Warning: No RPC URL for chain {self._chain_id}, using nonce 0")
            return 0

        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            # nonces(address) -> uint256
            nonce_data = w3.eth.call({
                "to": contract_address,
                "data": "0x7ecebe00" + owner[2:].lower().zfill(64),  # nonces(address)
            })
            return int(nonce_data.hex(), 16)
        except Exception as e:
            print(f"Warning: Failed to get nonce from {contract_address}: {e}, using 0")
            return 0

    def _get_and_increment_permit_nonce(self, owner: str, contract_address: str) -> int:
        """Get the next permit nonce with local tracking for high-throughput scenarios.

        On first call for an owner/contract pair, fetches from blockchain.
        Subsequent calls use local tracking and increment automatically.

        This prevents permit nonce conflicts when signing multiple permits
        for the same account before any are settled on-chain.

        Args:
            owner: The permit owner address.
            contract_address: The token contract address.

        Returns:
            The next nonce to use for the permit.
        """
        key = (owner.lower(), contract_address.lower())

        if key not in self._permit_nonces:
            # First call - fetch from blockchain
            self._permit_nonces[key] = self._get_contract_nonce(owner, contract_address)

        nonce = self._permit_nonces[key]
        self._permit_nonces[key] += 1
        return nonce

    def sync_permit_nonce(self, contract_address: Optional[str] = None) -> int:
        """Sync the local permit nonce with the blockchain.

        Use this after transactions have settled to ensure local tracking
        matches on-chain state, or after a permit failure to resync.

        Args:
            contract_address: The token contract. Defaults to USDC.

        Returns:
            The current on-chain nonce.
        """
        self._require_signer()

        owner = self._signer.address
        contract = contract_address or self._chain_config.usdc_address
        key = (owner.lower(), contract.lower())

        on_chain_nonce = self._get_contract_nonce(owner, contract)
        self._permit_nonces[key] = on_chain_nonce
        return on_chain_nonce

    def approve_usdc(
        self,
        amount: int,
        spender: Optional[str] = None,
    ) -> str:
        """Approve USDC spending for the settlement contract (on-chain transaction).

        This is an alternative to permit-based approval. Use this for high-frequency
        trading scenarios where permit nonce management becomes a bottleneck.

        Args:
            amount: The amount to approve (with 6 decimals for USDC).
            spender: The spender address. Defaults to settlement contract.

        Returns:
            The transaction hash.

        Raises:
            AuthenticationError: If no signer is configured.
        """
        self._require_signer()

        from web3 import Web3

        spender = spender or self._chain_config.settlement_address
        usdc_address = self._chain_config.usdc_address

        # Get RPC URL
        rpc_urls = {
            137: "https://polygon-rpc.com",
            43114: "https://api.avax.network/ext/bc/C/rpc",
            84532: "https://sepolia.base.org",
        }
        rpc_url = rpc_urls.get(self._chain_id)
        if not rpc_url:
            raise ValueError(f"No RPC URL for chain {self._chain_id}")

        w3 = Web3(Web3.HTTPProvider(rpc_url))

        # ERC20 approve function signature: approve(address,uint256)
        approve_selector = "0x095ea7b3"
        approve_data = (
            approve_selector
            + spender[2:].lower().zfill(64)
            + hex(amount)[2:].zfill(64)
        )

        # Build transaction
        nonce = w3.eth.get_transaction_count(self._signer.address)
        gas_price = w3.eth.gas_price

        tx = {
            "to": usdc_address,
            "data": approve_data,
            "gas": 100000,
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": self._chain_id,
        }

        # Sign and send
        signed_tx = w3.eth.account.sign_transaction(tx, self._signer._account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        return tx_hash.hex()

    def get_usdc_allowance(
        self,
        owner: Optional[str] = None,
        spender: Optional[str] = None,
    ) -> int:
        """Get the current USDC allowance for a spender.

        Args:
            owner: The token owner. Defaults to signer address.
            spender: The spender address. Defaults to settlement contract.

        Returns:
            The current allowance (with 6 decimals).
        """
        from web3 import Web3

        owner = owner or (self._signer.address if self._signer else None)
        if not owner:
            raise ValueError("Owner address required (no signer configured)")

        spender = spender or self._chain_config.settlement_address
        usdc_address = self._chain_config.usdc_address

        # Get RPC URL
        rpc_urls = {
            137: "https://polygon-rpc.com",
            43114: "https://api.avax.network/ext/bc/C/rpc",
            84532: "https://sepolia.base.org",
        }
        rpc_url = rpc_urls.get(self._chain_id)
        if not rpc_url:
            raise ValueError(f"No RPC URL for chain {self._chain_id}")

        w3 = Web3(Web3.HTTPProvider(rpc_url))

        # allowance(address,address) -> uint256
        allowance_selector = "0xdd62ed3e"
        allowance_data = (
            allowance_selector
            + owner[2:].lower().zfill(64)
            + spender[2:].lower().zfill(64)
        )

        result = w3.eth.call({
            "to": usdc_address,
            "data": allowance_data,
        })

        return int(result.hex(), 16)

    def sign_usdc_permit(
        self,
        value: int,
        settlement_address: Optional[str] = None,
        deadline: Optional[int] = None,
    ) -> PermitSignature:
        """Sign an EIP-2612 permit for USDC approval.

        This creates a signature that allows gasless USDC approval when
        included with an order submission.

        Args:
            value: The amount to approve (with 6 decimals for USDC).
            settlement_address: The spender (settlement contract). Uses chain default if not provided.
            deadline: Permit expiration timestamp. Defaults to 1 hour from now.

        Returns:
            PermitSignature that can be included with order submission.
        """
        self._require_signer()

        import time
        from eth_account import Account

        owner = self._signer.address
        spender = settlement_address or self._chain_config.settlement_address
        usdc_address = self._chain_config.usdc_address

        # Get USDC nonce with local tracking (auto-increment for batch scenarios)
        nonce = self._get_and_increment_permit_nonce(owner, usdc_address)

        # Set deadline
        if deadline is None:
            deadline = int(time.time()) + 3600  # 1 hour from now

        # USDC EIP-712 domain (Polygon mainnet uses "USD Coin" version "2")
        # Testnet uses "Mock USDC" version "1"
        is_testnet = self._chain_id in [84532]  # Base Sepolia
        token_name = "Mock USDC" if is_testnet else "USD Coin"
        token_version = "1" if is_testnet else "2"

        typed_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "Permit": [
                    {"name": "owner", "type": "address"},
                    {"name": "spender", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            "primaryType": "Permit",
            "domain": {
                "name": token_name,
                "version": token_version,
                "chainId": self._chain_id,
                "verifyingContract": usdc_address,
            },
            "message": {
                "owner": owner,
                "spender": spender,
                "value": value,
                "nonce": nonce,
                "deadline": deadline,
            },
        }

        # Sign the typed data
        signed = Account.sign_typed_data(
            self._signer._account.key,
            full_message=typed_data,
        )

        # Extract v, r, s
        v = signed.v
        r = "0x" + hex(signed.r)[2:].zfill(64)
        s = "0x" + hex(signed.s)[2:].zfill(64)

        return PermitSignature(
            nonce=nonce,
            value=value,
            deadline=deadline,
            v=v,
            r=r,
            s=s,
        )

    def request_ctf_redemption(
        self,
        owner: str,
        collateral_token: str,
        parent_collection_id: str,
        condition_id: str,
        index_sets: List[str],
        deadline: int,
        v: int,
        r: str,
        s: str,
        market_address: str = "",
    ) -> Dict[str, Any]:
        """Request gasless CTF token redemption via relayer.

        Args:
            owner: The token owner address.
            collateral_token: The USDC address.
            parent_collection_id: Parent collection ID (bytes32(0) for collateral).
            condition_id: The market's condition ID.
            index_sets: Array of index sets to redeem (["1"] for YES, ["2"] for NO).
            deadline: Permit deadline timestamp.
            v: Signature v value.
            r: Signature r value.
            s: Signature s value.
            market_address: Optional market contract address for PNL tracking.

        Returns:
            The relayer response with tx_hash on success.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        data = {
            "chainId": self._chain_id,
            "owner": owner,
            "collateralToken": collateral_token,
            "parentCollectionId": parent_collection_id,
            "conditionId": condition_id,
            "indexSets": index_sets,
            "deadline": str(deadline),
            "v": v,
            "r": r,
            "s": s,
        }
        if market_address:
            data["marketAddress"] = market_address
        return self._http.post(ENDPOINTS["ctf_redemption"], data=data, authenticated=True)

    def claim_winnings(
        self,
        market_contract_address: str,
    ) -> Dict[str, Any]:
        """Claim winnings from a resolved market using gasless permit.

        This queries the market contract for resolution status and condition data,
        signs an EIP-712 permit, and submits to the relayer for gasless execution.

        Args:
            market_contract_address: The market's contract address.

        Returns:
            The relayer response with tx_hash on success.

        Raises:
            ValueError: If market is not resolved or user has no winnings.
            AuthenticationError: If no signer is configured.
        """
        self._require_signer()
        self._require_auth()

        import time
        from eth_account import Account
        from web3 import Web3

        owner = self._signer.address

        # Get RPC URL
        rpc_urls = {
            137: "https://polygon-bor-rpc.publicnode.com",
            43114: "https://avalanche-c-chain-rpc.publicnode.com",
            84532: "https://base-sepolia-rpc.publicnode.com",
        }
        rpc_url = rpc_urls.get(self._chain_id)
        if not rpc_url:
            raise ValueError(f"No RPC URL for chain {self._chain_id}")

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        print(f"Connected to RPC: {rpc_url}")

        # Ensure address is checksummed
        market_contract_address = Web3.to_checksum_address(market_contract_address)
        print(f"Market address: {market_contract_address}")

        # Query individual getters from market contract
        # ctf() -> address
        print("Querying ctf()...")
        ctf_data = w3.eth.call({
            "to": market_contract_address,
            "data": "0x22a9339f",  # ctf()
        })
        ctf_address = Web3.to_checksum_address("0x" + ctf_data[12:32].hex())
        print(f"CTF address: {ctf_address}")

        # collateralToken() -> address
        collateral_data = w3.eth.call({
            "to": market_contract_address,
            "data": "0xb2016bd4",  # collateralToken()
        })
        collateral_token = Web3.to_checksum_address("0x" + collateral_data[12:32].hex())

        # conditionId() -> bytes32
        condition_data = w3.eth.call({
            "to": market_contract_address,
            "data": "0x2ddc7de7",  # conditionId()
        })
        condition_id = "0x" + condition_data.hex()

        # yesTokenId() -> uint256
        yes_data = w3.eth.call({
            "to": market_contract_address,
            "data": "0x76cd28a2",  # yesTokenId()
        })
        yes_token_id = int(yes_data.hex(), 16)

        # noTokenId() -> uint256
        no_data = w3.eth.call({
            "to": market_contract_address,
            "data": "0x8c2557a8",  # noTokenId()
        })
        no_token_id = int(no_data.hex(), 16)

        print(f"Market data:")
        print(f"  CTF: {ctf_address}")
        print(f"  Collateral: {collateral_token}")
        print(f"  Condition ID: {condition_id}")

        # Query getResolutionStatus() from market contract
        # Returns: (expired, resolved, assertionId, winningOutcome, canPropose, canSettle)
        resolution_selector = "0x13b63fce"  # getResolutionStatus()
        resolution_data = w3.eth.call({
            "to": market_contract_address,
            "data": resolution_selector,
        })

        # Decode: bool, bool, bytes32, uint8, bool, bool
        # Each value is padded to 32 bytes:
        # expired: bytes 0-32 (value at byte 31)
        # resolved: bytes 32-64 (value at byte 63)
        # assertionId: bytes 64-96
        # winningOutcome: bytes 96-128 (uint8 padded)
        resolved = bool(resolution_data[63])
        winning_outcome = int(resolution_data[96:128].hex(), 16)

        if not resolved:
            raise ValueError("Market is not resolved yet")

        print(f"  Resolved: {resolved}")
        print(f"  Winning outcome: {'YES' if winning_outcome == 0 else 'NO'}")

        # Check user's winning token balance
        winning_token_id = yes_token_id if winning_outcome == 0 else no_token_id

        # balanceOf(address, uint256) -> uint256
        balance_selector = "0x00fdd58e"  # balanceOf(address,uint256)
        balance_call = balance_selector + owner[2:].lower().zfill(64) + hex(winning_token_id)[2:].zfill(64)
        balance_data = w3.eth.call({
            "to": ctf_address,
            "data": balance_call,
        })
        balance = int(balance_data.hex(), 16)

        if balance == 0:
            raise ValueError("No winning tokens to redeem")

        print(f"  Winning token balance: {balance / 1_000_000:.2f}")

        # Get nonce from CTF contract
        nonce = self._get_contract_nonce(owner, ctf_address)

        # Set deadline
        deadline = int(time.time()) + 3600

        # indexSets: [1] for YES, [2] for NO
        index_sets = [1 if winning_outcome == 0 else 2]

        # Build EIP-712 typed data for RedeemPositions
        typed_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "RedeemPositions": [
                    {"name": "owner", "type": "address"},
                    {"name": "collateralToken", "type": "address"},
                    {"name": "parentCollectionId", "type": "bytes32"},
                    {"name": "conditionId", "type": "bytes32"},
                    {"name": "indexSets", "type": "uint256[]"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            "primaryType": "RedeemPositions",
            "domain": {
                "name": "ConditionalTokensWithPermit",
                "version": "1",
                "chainId": self._chain_id,
                "verifyingContract": ctf_address,
            },
            "message": {
                "owner": owner,
                "collateralToken": collateral_token,
                "parentCollectionId": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "conditionId": condition_id,
                "indexSets": index_sets,
                "nonce": nonce,
                "deadline": deadline,
            },
        }

        # Sign the typed data
        signed = Account.sign_typed_data(
            self._signer._account.key,
            full_message=typed_data,
        )

        v = signed.v
        r = "0x" + hex(signed.r)[2:].zfill(64)
        s = "0x" + hex(signed.s)[2:].zfill(64)

        print(f"Submitting redemption...")

        return self.request_ctf_redemption(
            owner=owner,
            collateral_token=collateral_token,
            parent_collection_id="0x0000000000000000000000000000000000000000000000000000000000000000",
            condition_id=condition_id,
            index_sets=[str(i) for i in index_sets],
            deadline=deadline,
            v=v,
            r=r,
            s=s,
            market_address=market_contract_address,
        )

    def request_batch_ctf_redemption(
        self,
        redemptions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Request batch gasless CTF token redemption via relayer.

        Args:
            redemptions: List of redemption requests, each containing:
                - owner: The token owner address
                - collateralToken: The USDC address
                - parentCollectionId: Parent collection ID (bytes32(0) for collateral)
                - conditionId: The market's condition ID
                - indexSets: Array of index sets to redeem
                - deadline: Permit deadline timestamp
                - v: Signature v value
                - r: Signature r value
                - s: Signature s value
                - marketAddress: Optional market contract address

        Returns:
            The relayer response with txHash on success.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()
        self._require_signer()
        data = {
            "chainId": self._chain_id,
            "owner": self._signer.address,
            "redemptions": redemptions,
        }
        return self._http.post(
            ENDPOINTS["batch_ctf_redemption"], data=data, authenticated=True
        )

    def batch_claim_winnings(
        self,
        market_contract_addresses: List[str],
    ) -> Dict[str, Any]:
        """Claim winnings from multiple resolved markets using gasless permits.

        This queries each market contract for resolution status and condition data,
        signs EIP-712 permits for each, and submits a batch to the relayer.

        Args:
            market_contract_addresses: List of market contract addresses to claim from.

        Returns:
            The relayer response with txHash on success.

        Raises:
            ValueError: If any market is not resolved or user has no winnings.
            AuthenticationError: If no signer is configured.
        """
        self._require_signer()
        self._require_auth()

        import time
        from eth_account import Account
        from web3 import Web3

        owner = self._signer.address

        # Get RPC URL
        rpc_urls = {
            137: "https://polygon-bor-rpc.publicnode.com",
            43114: "https://avalanche-c-chain-rpc.publicnode.com",
            84532: "https://base-sepolia-rpc.publicnode.com",
        }
        rpc_url = rpc_urls.get(self._chain_id)
        if not rpc_url:
            raise ValueError(f"No RPC URL for chain {self._chain_id}")

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        redemptions = []

        for market_address in market_contract_addresses:
            market_address = Web3.to_checksum_address(market_address)

            # Query market contract data
            ctf_data = w3.eth.call({
                "to": market_address,
                "data": "0x22a9339f",  # ctf()
            })
            ctf_address = Web3.to_checksum_address("0x" + ctf_data[12:32].hex())

            collateral_data = w3.eth.call({
                "to": market_address,
                "data": "0xb2016bd4",  # collateralToken()
            })
            collateral_token = Web3.to_checksum_address("0x" + collateral_data[12:32].hex())

            condition_data = w3.eth.call({
                "to": market_address,
                "data": "0x2ddc7de7",  # conditionId()
            })
            condition_id = "0x" + condition_data.hex()

            yes_data = w3.eth.call({
                "to": market_address,
                "data": "0x76cd28a2",  # yesTokenId()
            })
            yes_token_id = int(yes_data.hex(), 16)

            no_data = w3.eth.call({
                "to": market_address,
                "data": "0x8c2557a8",  # noTokenId()
            })
            no_token_id = int(no_data.hex(), 16)

            # Check resolution status
            resolution_data = w3.eth.call({
                "to": market_address,
                "data": "0x13b63fce",  # getResolutionStatus()
            })
            resolved = bool(resolution_data[63])
            winning_outcome = int(resolution_data[96:128].hex(), 16)

            if not resolved:
                print(f"Skipping {market_address}: not resolved")
                continue

            # Check balance
            winning_token_id = yes_token_id if winning_outcome == 0 else no_token_id
            balance_call = "0x00fdd58e" + owner[2:].lower().zfill(64) + hex(winning_token_id)[2:].zfill(64)
            balance_data = w3.eth.call({
                "to": ctf_address,
                "data": balance_call,
            })
            balance = int(balance_data.hex(), 16)

            if balance == 0:
                print(f"Skipping {market_address}: no winning tokens")
                continue

            # Get nonce and sign — use local tracking to increment for each
            # permit in the batch, since redeemPositionsWithPermit increments
            # nonces[owner]++ on-chain for each call in the Multicall3 batch.
            nonce = self._get_and_increment_permit_nonce(owner, ctf_address)
            deadline = int(time.time()) + 3600
            index_sets = [1 if winning_outcome == 0 else 2]

            typed_data = {
                "types": {
                    "EIP712Domain": [
                        {"name": "name", "type": "string"},
                        {"name": "version", "type": "string"},
                        {"name": "chainId", "type": "uint256"},
                        {"name": "verifyingContract", "type": "address"},
                    ],
                    "RedeemPositions": [
                        {"name": "owner", "type": "address"},
                        {"name": "collateralToken", "type": "address"},
                        {"name": "parentCollectionId", "type": "bytes32"},
                        {"name": "conditionId", "type": "bytes32"},
                        {"name": "indexSets", "type": "uint256[]"},
                        {"name": "nonce", "type": "uint256"},
                        {"name": "deadline", "type": "uint256"},
                    ],
                },
                "primaryType": "RedeemPositions",
                "domain": {
                    "name": "ConditionalTokensWithPermit",
                    "version": "1",
                    "chainId": self._chain_id,
                    "verifyingContract": ctf_address,
                },
                "message": {
                    "owner": owner,
                    "collateralToken": collateral_token,
                    "parentCollectionId": "0x0000000000000000000000000000000000000000000000000000000000000000",
                    "conditionId": condition_id,
                    "indexSets": index_sets,
                    "nonce": nonce,
                    "deadline": deadline,
                },
            }

            signed = Account.sign_typed_data(
                self._signer._account.key,
                full_message=typed_data,
            )

            v = signed.v
            r = "0x" + hex(signed.r)[2:].zfill(64)
            s = "0x" + hex(signed.s)[2:].zfill(64)

            redemptions.append({
                "owner": owner,
                "collateralToken": collateral_token,
                "parentCollectionId": "0x0000000000000000000000000000000000000000000000000000000000000000",
                "conditionId": condition_id,
                "indexSets": [str(i) for i in index_sets],
                "deadline": str(deadline),
                "v": v,
                "r": r,
                "s": s,
                "marketAddress": market_address,
            })

            print(f"Added {market_address} to batch (balance: {balance / 1_000_000:.2f})")

        if not redemptions:
            raise ValueError("No markets with winning tokens to redeem")

        print(f"Submitting batch redemption for {len(redemptions)} markets...")
        return self.request_batch_ctf_redemption(redemptions)

    # =========================================================================
    # Claimable Positions Discovery
    # =========================================================================

    def get_claimable_positions(
        self,
        address: Optional[str] = None,
        verify: bool = False,
    ) -> Dict[str, Any]:
        """Get positions in resolved markets that can be claimed.

        Queries the /claimable endpoint which returns positions where the user
        has winning shares in resolved markets, excluding markets with pending
        or confirmed redemptions.

        Args:
            address: The user address. Defaults to the signer's address.
            verify: If True, the server verifies on-chain balances and backfills
                stale data. Slower but catches already-claimed markets.

        Returns:
            Dictionary with 'positions' (list of ClaimablePosition dicts),
            'count', and 'totalPayout'.

        Raises:
            AuthenticationError: If no auth is configured.
        """
        self._require_auth()

        addr = address or (self._signer.address if self._signer else None)
        if not addr:
            raise AuthenticationError("No address provided and no signer configured")

        endpoint = ENDPOINTS["user_claimable"].format(address=addr)
        params = {"chain_id": str(self._chain_id)}
        if verify:
            params["verify"] = "true"

        result = self._http.get(endpoint, params=params, authenticated=True)

        # Parse positions into ClaimablePosition objects
        if isinstance(result, dict) and "positions" in result:
            result["positions"] = [
                ClaimablePosition.from_dict(p) if isinstance(p, dict) else p
                for p in result["positions"]
            ]

        return result

    def claim_all_winnings(self) -> Dict[str, Any]:
        """Discover and claim all winning positions in one call.

        This is a convenience method that:
        1. Queries /claimable with verify=True to find all claimable markets
        2. Calls batch_claim_winnings() with the discovered market addresses

        Returns:
            The relayer response with txHash on success.

        Raises:
            ValueError: If no claimable positions found.
            AuthenticationError: If no signer or auth is configured.
        """
        self._require_signer()
        self._require_auth()

        # Discover claimable positions with on-chain verification
        result = self.get_claimable_positions(verify=True)
        positions = result.get("positions", [])

        if not positions:
            raise ValueError("No claimable positions found")

        # Extract contract addresses
        market_addresses = []
        for pos in positions:
            addr = pos.contract_address if isinstance(pos, ClaimablePosition) else pos.get("contractAddress", "")
            if addr:
                market_addresses.append(addr)

        if not market_addresses:
            raise ValueError("No market addresses found in claimable positions")

        print(f"Found {len(market_addresses)} claimable market(s), submitting batch claim...")
        return self.batch_claim_winnings(market_addresses)

    # =========================================================================
    # API Key Registration (Self-Service Credentials)
    # =========================================================================

    @staticmethod
    def request_api_credentials(
        host: str,
        private_key: str,
        name: Optional[str] = None,
    ) -> Dict[str, str]:
        """Request API credentials by proving wallet ownership.

        This is a self-service endpoint that generates new API credentials
        for a wallet address. The wallet must sign a message to prove ownership.

        Args:
            host: The API host URL (e.g., "https://api.turbinefi.com").
            private_key: The wallet private key (for signing the auth message).
            name: Optional friendly name for the API key.

        Returns:
            Dictionary with:
                - api_key_id: The API key identifier
                - api_private_key: The Ed25519 private key (save this!)
                - message: Success message

        Raises:
            TurbineApiError: If registration fails.

        Example:
            >>> creds = TurbineClient.request_api_credentials(
            ...     host="https://api.turbinefi.com",
            ...     private_key="your_wallet_private_key",
            ... )
            >>> print(f"API Key ID: {creds['api_key_id']}")
            >>> print(f"API Private Key: {creds['api_private_key']}")
        """
        from eth_account import Account
        from eth_account.messages import encode_defunct

        # Create account from private key
        if private_key.startswith("0x"):
            private_key = private_key[2:]
        account = Account.from_key(private_key)
        address = account.address

        # Sign the registration message
        message = f"Register API key for Turbine: {address}"
        signable = encode_defunct(text=message)
        signed = account.sign_message(signable)
        signature = signed.signature.hex()

        # Make the request
        import httpx

        url = f"{host.rstrip('/')}/api/v1/api-keys"
        data = {
            "address": address,
            "signature": f"0x{signature}",
        }
        if name:
            data["name"] = name

        response = httpx.post(url, json=data, timeout=30.0)

        if response.status_code == 409:
            # Already has a key
            result = response.json()
            raise TurbineApiError(
                f"API key already exists for {address}. Key ID: {result.get('api_key_id', 'unknown')}",
                status_code=409,
            )

        if response.status_code != 200:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", response.text)
            except Exception:
                error_msg = response.text
            raise TurbineApiError(
                f"Failed to register API key: {error_msg}",
                status_code=response.status_code,
            )

        result = response.json()
        if not result.get("success"):
            raise TurbineApiError(
                f"Failed to register API key: {result.get('error', 'Unknown error')}",
                status_code=response.status_code,
            )

        return {
            "api_key_id": result["api_key_id"],
            "api_private_key": result["api_private_key"],
            "message": result.get("message", "API key created successfully"),
        }
