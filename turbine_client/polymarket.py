"""
Polymarket client for trading on Polymarket through the Turbine API proxy.

All requests are routed through Turbine's API with the `?polymarket=true` query
parameter. Turbine acts as a stateless, non-custodial proxy — order signing
happens client-side and credentials are per-request, never stored.
"""

from typing import Any, Dict, List, Optional

import httpx

from turbine_client.constants import HEADER_CONTENT_TYPE, HEADER_USER_AGENT, USER_AGENT
from turbine_client.exceptions import TurbineApiError


class PolymarketClient:
    """Client for trading on Polymarket through Turbine's API proxy.

    All traffic goes through the Turbine API with ``?polymarket=true``.
    Authenticated endpoints require Polymarket API credentials passed
    via ``X-Polymarket-*`` headers on every request.

    Example::

        client = PolymarketClient(
            host="https://api.turbine.markets",
            polymarket_key="...",
            polymarket_secret="...",
            polymarket_passphrase="...",
        )
        markets = client.get_markets()
    """

    def __init__(
        self,
        host: str,
        polymarket_key: Optional[str] = None,
        polymarket_secret: Optional[str] = None,
        polymarket_passphrase: Optional[str] = None,
        private_key: Optional[str] = None,
        chain_id: int = 137,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the Polymarket client.

        Args:
            host: The Turbine API host URL.
            polymarket_key: Polymarket API key for authenticated requests.
            polymarket_secret: Polymarket API secret for authenticated requests.
            polymarket_passphrase: Polymarket API passphrase for authenticated requests.
            private_key: Wallet private key for client-side order signing.
            chain_id: Blockchain chain ID (default: 137 for Polygon mainnet).
            timeout: HTTP request timeout in seconds.
        """
        self._host = host.rstrip("/")
        self._polymarket_key = polymarket_key
        self._polymarket_secret = polymarket_secret
        self._polymarket_passphrase = polymarket_passphrase
        self._private_key = private_key
        self._chain_id = chain_id
        self._client = httpx.Client(
            http2=True,
            timeout=timeout,
            headers={
                HEADER_USER_AGENT: USER_AGENT,
                HEADER_CONTENT_TYPE: "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
        )

    @property
    def has_credentials(self) -> bool:
        """Whether Polymarket API credentials are configured."""
        return bool(
            self._polymarket_key
            and self._polymarket_secret
            and self._polymarket_passphrase
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "PolymarketClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _build_url(self, endpoint: str) -> str:
        """Build the full URL for an endpoint."""
        return f"{self._host}{endpoint}"

    def _polymarket_params(
        self, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add ``polymarket=true`` to query parameters."""
        merged: Dict[str, Any] = {"polymarket": "true"}
        if params:
            merged.update(params)
        return merged

    def _auth_headers(self) -> Dict[str, str]:
        """Return Polymarket authentication headers."""
        headers: Dict[str, str] = {}
        if self._polymarket_key:
            headers["X-Polymarket-Key"] = self._polymarket_key
        if self._polymarket_secret:
            headers["X-Polymarket-Secret"] = self._polymarket_secret
        if self._polymarket_passphrase:
            headers["X-Polymarket-Passphrase"] = self._polymarket_passphrase
        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle an HTTP response, raising on errors."""
        if response.status_code >= 400:
            try:
                error_body = response.json()
                error_message = error_body.get(
                    "error", error_body.get("message", str(error_body))
                )
            except Exception:
                error_body = response.text
                error_message = response.text or f"HTTP {response.status_code}"

            raise TurbineApiError(
                message=error_message,
                status_code=response.status_code,
                response_body=error_body,
            )

        if response.status_code == 204:
            return None

        try:
            return response.json()
        except Exception:
            return response.text

    def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        authenticated: bool = False,
    ) -> Any:
        """Make an authenticated GET request with ``?polymarket=true``."""
        url = self._build_url(endpoint)
        headers = self._auth_headers() if authenticated else {}
        try:
            response = self._client.get(
                url, params=self._polymarket_params(params), headers=headers
            )
            return self._handle_response(response)
        except httpx.RequestError as e:
            raise TurbineApiError(f"Request failed: {e}") from e

    def _post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        authenticated: bool = False,
    ) -> Any:
        """Make an authenticated POST request with ``?polymarket=true``."""
        url = self._build_url(endpoint)
        headers = self._auth_headers() if authenticated else {}
        try:
            response = self._client.post(
                url,
                json=data,
                params=self._polymarket_params(params),
                headers=headers,
            )
            return self._handle_response(response)
        except httpx.RequestError as e:
            raise TurbineApiError(f"Request failed: {e}") from e

    def _delete(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        authenticated: bool = False,
    ) -> Any:
        """Make an authenticated DELETE request with ``?polymarket=true``."""
        url = self._build_url(endpoint)
        headers = self._auth_headers() if authenticated else {}
        try:
            response = self._client.delete(
                url, params=self._polymarket_params(params), headers=headers
            )
            return self._handle_response(response)
        except httpx.RequestError as e:
            raise TurbineApiError(f"Request failed: {e}") from e

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(
        self,
        address: str,
        signature: str,
        timestamp: int,
        nonce: str,
    ) -> Dict[str, str]:
        """Onboard to Polymarket and obtain API credentials.

        Args:
            address: Wallet address.
            signature: EIP-712 signature proving wallet ownership.
            timestamp: Unix timestamp included in the signed payload.
            nonce: Random nonce included in the signed payload.

        Returns:
            Dict with ``apiKey``, ``secret``, and ``passphrase``.
        """
        return self._post(
            "/api/v1/polymarket/auth",
            data={
                "address": address,
                "signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
            },
        )

    def derive_api_key(
        self,
        address: str,
        signature: str,
        timestamp: int,
        nonce: str,
    ) -> Dict[str, str]:
        """Derive a new Polymarket API key from an existing wallet.

        Args:
            address: Wallet address.
            signature: EIP-712 signature proving wallet ownership.
            timestamp: Unix timestamp included in the signed payload.
            nonce: Random nonce included in the signed payload.

        Returns:
            Dict with ``apiKey``, ``secret``, and ``passphrase``.
        """
        return self._post(
            "/api/v1/polymarket/auth/derive",
            data={
                "address": address,
                "signature": signature,
                "timestamp": timestamp,
                "nonce": nonce,
            },
        )

    # ------------------------------------------------------------------
    # Markets
    # ------------------------------------------------------------------

    def get_markets(
        self, next_cursor: Optional[str] = None
    ) -> Any:
        """Browse Polymarket markets.

        Args:
            next_cursor: Pagination cursor for the next page of results.

        Returns:
            Market list (paginated).
        """
        params: Dict[str, Any] = {}
        if next_cursor is not None:
            params["next_cursor"] = next_cursor
        return self._get("/api/v1/markets", params=params)

    def get_orderbook(self, token_id: str) -> Any:
        """Get the orderbook for a Polymarket token.

        Args:
            token_id: The Polymarket condition token ID.

        Returns:
            Orderbook snapshot with bids and asks.
        """
        return self._get(f"/api/v1/orderbook/{token_id}")

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def create_order(
        self,
        token_id: str,
        side: str,
        price: str,
        size: str,
        order_type: str = "GTC",
        signed_order: Optional[Any] = None,
    ) -> Any:
        """Place an order on Polymarket.

        The ``signed_order`` must be generated client-side (e.g. via
        ``py_clob_client``). Turbine never sees private keys.

        Args:
            token_id: The condition token ID to trade.
            side: ``"BUY"`` or ``"SELL"``.
            price: Limit price as a decimal string (e.g. ``"0.65"``).
            size: Number of shares as a string (e.g. ``"100"``).
            order_type: Order type — ``"GTC"``, ``"GTD"``, ``"FOK"``, etc.
            signed_order: Raw signed order object from py_clob_client.

        Returns:
            Order confirmation from the API.
        """
        payload: Dict[str, Any] = {
            "token_id": token_id,
            "side": side,
            "price": price,
            "size": size,
            "order_type": order_type,
        }
        if signed_order is not None:
            payload["signed_order"] = signed_order
        return self._post("/api/v1/orders", data=payload, authenticated=True)

    def cancel_order(self, order_id: str) -> Any:
        """Cancel an open order.

        Args:
            order_id: The order ID to cancel.

        Returns:
            Cancellation confirmation.
        """
        return self._delete(f"/api/v1/orders/{order_id}", authenticated=True)

    def get_open_orders(self) -> Any:
        """List all open orders.

        Returns:
            List of open orders.
        """
        return self._get("/api/v1/orders", authenticated=True)

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self, address: str) -> Any:
        """Get positions for a wallet address.

        Args:
            address: Wallet address to query positions for.

        Returns:
            List of positions.
        """
        return self._get(f"/api/v1/users/{address}/positions", authenticated=True)
