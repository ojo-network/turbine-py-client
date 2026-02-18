"""
Multicall3-based position discovery for reliable on-chain reads.

Uses batched Multicall3 calls to discover claimable and mergeable positions
across thousands of markets efficiently.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from web3 import Web3

logger = logging.getLogger(__name__)

# Contract addresses (Polygon)
MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"

# Quick market assets to scan
QUICK_MARKET_ASSETS = ["BTC", "ETH", "SOL"]

# Batch size for multicall (markets per batch)
MULTICALL_BATCH_SIZE = 40

# RPC URLs per chain
RPC_URLS = {
    137: "https://rpc.ankr.com/polygon/556256e69e5e244c3438d6a51748e56aefa65ae94a583bcde0d2c8f98571c652",
    43114: "https://api.avax.network/ext/bc/C/rpc",
    84532: "https://sepolia.base.org",
}

# Function selectors
SELECTORS = {
    "conditionId": "0x2ddc7de7",        # conditionId()
    "yesTokenId": "0x76cd28a2",         # yesTokenId()
    "noTokenId": "0x8c2557a8",          # noTokenId()
    "getResolutionStatus": "0x13b63fce", # getResolutionStatus()
    "balanceOf": "0x00fdd58e",          # balanceOf(address,uint256)
    "payoutDenominator": "0xc52aa88e",  # payoutDenominator(bytes32)
}

# Multicall3 aggregate ABI
MULTICALL3_ABI = [
    {
        "inputs": [
            {
                "components": [
                    {"name": "target", "type": "address"},
                    {"name": "callData", "type": "bytes"},
                ],
                "name": "calls",
                "type": "tuple[]",
            }
        ],
        "name": "aggregate",
        "outputs": [
            {"name": "blockNumber", "type": "uint256"},
            {"name": "returnData", "type": "bytes[]"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]


@dataclass
class MarketCandidate:
    """A market with a known contract address, ready for on-chain reads."""
    market_id: str
    contract_address: str
    source: str  # "static" or "quick-BTC" etc.


@dataclass
class ClaimablePosition:
    """A resolved market position that can be redeemed for USDC."""
    market_id: str
    contract_address: str
    source: str
    condition_id: str
    winning_outcome: int  # 0=YES, 1=NO
    winning_balance: int  # raw amount (6 decimals)
    payout_usdc: float    # human-readable USDC value

    @property
    def outcome_label(self) -> str:
        return "YES" if self.winning_outcome == 0 else "NO"


@dataclass
class MergeablePosition:
    """A market where paired YES+NO tokens can be merged back to USDC."""
    market_id: str
    contract_address: str
    source: str
    condition_id: str
    yes_balance: int
    no_balance: int
    mergeable_amount: int  # min(yes, no)
    merge_usdc: float      # human-readable USDC value


@dataclass
class DiscoveryResult:
    """Result of position discovery."""
    claimable: List[ClaimablePosition] = field(default_factory=list)
    mergeable: List[MergeablePosition] = field(default_factory=list)
    markets_scanned: int = 0
    total_claimable_usdc: float = 0.0
    total_mergeable_usdc: float = 0.0

    @property
    def total_usdc(self) -> float:
        return self.total_claimable_usdc + self.total_mergeable_usdc


def _do_multicall(w3: Web3, calls: List[Tuple[str, bytes]]) -> List[bytes]:
    """Execute a batch of calls via Multicall3.aggregate().

    Args:
        w3: Web3 instance.
        calls: List of (target_address, calldata) tuples.

    Returns:
        List of return data bytes for each call.
    """
    if not calls:
        return []

    multicall = w3.eth.contract(
        address=Web3.to_checksum_address(MULTICALL3_ADDRESS),
        abi=MULTICALL3_ABI,
    )

    formatted_calls = [
        (Web3.to_checksum_address(target), calldata)
        for target, calldata in calls
    ]

    result = multicall.functions.aggregate(formatted_calls).call()
    return result[1]  # returnData[]


def _fetch_all_quick_markets(
    api_base_url: str,
    http_client: Any,
) -> List[MarketCandidate]:
    """Fetch all quick markets from the paginated API endpoint.

    Args:
        api_base_url: Base API URL.
        http_client: HTTP client with .get() method.

    Returns:
        List of MarketCandidate for quick markets with contract addresses.
    """
    import httpx

    candidates = []

    for asset in QUICK_MARKET_ASSETS:
        cursor = None
        page = 0

        while True:
            page += 1
            url = f"/api/v1/quick-markets/{asset}/all?limit=500"
            if cursor is not None:
                url += f"&cursor={cursor}"

            try:
                response = http_client.get(url)
            except Exception as e:
                logger.warning("Failed to fetch quick %s markets (page %d): %s", asset, page, e)
                break

            markets = response.get("markets", [])
            next_cursor = response.get("nextCursor")

            for m in markets:
                contract_addr = m.get("contractAddress", "")
                if not contract_addr:
                    continue
                candidates.append(MarketCandidate(
                    market_id=m.get("marketId", ""),
                    contract_address=contract_addr,
                    source=f"quick-{asset}",
                ))

            if next_cursor is None:
                break
            cursor = next_cursor

        logger.info("Fetched %d quick %s markets across %d pages", 
                    sum(1 for c in candidates if c.source == f"quick-{asset}"), asset, page)

    return candidates


def _batch_read_market_data(
    w3: Web3,
    candidates: List[MarketCandidate],
) -> List[Dict[str, Any]]:
    """Batch read market data (conditionId, yesTokenId, noTokenId, getResolutionStatus).

    Args:
        w3: Web3 instance.
        candidates: List of market candidates.

    Returns:
        List of market data dicts with on-chain info.
    """
    markets = []

    for start in range(0, len(candidates), MULTICALL_BATCH_SIZE):
        batch = candidates[start:start + MULTICALL_BATCH_SIZE]
        calls = []

        for c in batch:
            addr = c.contract_address
            calls.append((addr, bytes.fromhex(SELECTORS["conditionId"][2:])))
            calls.append((addr, bytes.fromhex(SELECTORS["yesTokenId"][2:])))
            calls.append((addr, bytes.fromhex(SELECTORS["noTokenId"][2:])))
            calls.append((addr, bytes.fromhex(SELECTORS["getResolutionStatus"][2:])))

        try:
            results = _do_multicall(w3, calls)
        except Exception as e:
            logger.warning("Market data batch %d-%d failed: %s", start, start + len(batch), e)
            continue

        for i, c in enumerate(batch):
            base = i * 4
            try:
                condition_id = "0x" + results[base].hex()
                yes_token_id = int(results[base + 1].hex(), 16)
                no_token_id = int(results[base + 2].hex(), 16)

                res_data = results[base + 3]
                # Decode: bool expired(0-32), bool resolved(32-64), bytes32 assertionId(64-96),
                #         uint256 winningOutcome(96-128), bool canPropose(128-160), bool canSettle(160-192)
                resolved = bool(res_data[63])
                winning_outcome = int(res_data[96:128].hex(), 16)

                markets.append({
                    "market_id": c.market_id,
                    "contract_address": c.contract_address,
                    "source": c.source,
                    "condition_id": condition_id,
                    "yes_token_id": yes_token_id,
                    "no_token_id": no_token_id,
                    "resolved": resolved,
                    "winning_outcome": winning_outcome,
                })
            except Exception as e:
                logger.debug("Failed to parse market %s: %s", c.contract_address, e)
                continue

        logger.info("Parsed market data batch %d-%d (%d markets)", 
                    start, start + len(batch), len(batch))

    return markets


def _batch_read_balances(
    w3: Web3,
    markets: List[Dict[str, Any]],
    wallet_address: str,
    ctf_address: str,
) -> List[Dict[str, Any]]:
    """Batch read CTF balances and payout denominators.

    Args:
        w3: Web3 instance.
        markets: List of market data dicts.
        wallet_address: The wallet address to check balances for.
        ctf_address: The CTF contract address.

    Returns:
        Markets list with yes_balance, no_balance, payout_denominator added.
    """
    addr_bytes = bytes.fromhex(wallet_address[2:].lower()).rjust(32, b'\x00')
    balance_sel = bytes.fromhex(SELECTORS["balanceOf"][2:])
    denom_sel = bytes.fromhex(SELECTORS["payoutDenominator"][2:])

    for start in range(0, len(markets), MULTICALL_BATCH_SIZE):
        batch = markets[start:start + MULTICALL_BATCH_SIZE]
        calls = []

        for m in batch:
            # balanceOf(address, yesTokenId)
            yes_id_bytes = m["yes_token_id"].to_bytes(32, "big")
            calls.append((ctf_address, balance_sel + addr_bytes + yes_id_bytes))

            # balanceOf(address, noTokenId)
            no_id_bytes = m["no_token_id"].to_bytes(32, "big")
            calls.append((ctf_address, balance_sel + addr_bytes + no_id_bytes))

            # payoutDenominator(conditionId)
            cond_bytes = bytes.fromhex(m["condition_id"][2:])
            calls.append((ctf_address, denom_sel + cond_bytes.ljust(32, b'\x00')))

        try:
            results = _do_multicall(w3, calls)
        except Exception as e:
            logger.warning("Balance batch %d-%d failed: %s", start, start + len(batch), e)
            continue

        for i, m in enumerate(batch):
            base = i * 3
            try:
                m["yes_balance"] = int(results[base].hex(), 16)
                m["no_balance"] = int(results[base + 1].hex(), 16)
                m["payout_denominator"] = int(results[base + 2].hex(), 16)
            except Exception as e:
                logger.debug("Failed to parse balances for %s: %s", m["contract_address"], e)
                m["yes_balance"] = 0
                m["no_balance"] = 0
                m["payout_denominator"] = 0

    return markets


def discover_positions(
    w3: Web3,
    wallet_address: str,
    ctf_address: str,
    settlement_address: str,
    api_base_url: str,
    http_client: Any,
) -> DiscoveryResult:
    """Discover all claimable and mergeable positions using Multicall3.

    This is the main entry point for position discovery. It:
    1. Fetches all quick markets (BTC, ETH, SOL) from the paginated API
    2. Batch reads market data (conditionId, tokenIds, resolution status)
    3. Batch reads CTF balances and payout denominators
    4. Identifies claimable (resolved, winning tokens) and mergeable (paired YES+NO) positions

    Args:
        w3: Web3 instance connected to the chain RPC.
        wallet_address: The wallet address to check.
        ctf_address: The CTF contract address.
        settlement_address: Unused (kept for API compatibility).
        api_base_url: The API base URL.
        http_client: HTTP client for API calls.

    Returns:
        DiscoveryResult with claimable and mergeable positions.
    """
    wallet_address = Web3.to_checksum_address(wallet_address)
    result = DiscoveryResult()

    # Step 1: Collect all quick market candidates
    logger.info("Collecting quick market candidates...")

    candidates = _fetch_all_quick_markets(api_base_url, http_client)

    if not candidates:
        logger.info("No market candidates found")
        return result

    result.markets_scanned = len(candidates)
    logger.info("Found %d market candidates", len(candidates))

    # Step 2: Batch read market data
    logger.info("Reading market data via Multicall3...")
    markets = _batch_read_market_data(w3, candidates)

    # Step 3: Batch read balances
    logger.info("Reading balances via Multicall3...")
    markets = _batch_read_balances(w3, markets, wallet_address, ctf_address)

    # Step 4: Classify positions
    for m in markets:
        yes_bal = m.get("yes_balance", 0)
        no_bal = m.get("no_balance", 0)

        if yes_bal == 0 and no_bal == 0:
            continue

        # Check for claimable (resolved market with winning tokens and payouts reported)
        is_claimable = False
        if m["resolved"] and m.get("payout_denominator", 0) > 0:
            winning_bal = yes_bal if m["winning_outcome"] == 0 else no_bal
            if winning_bal > 0:
                payout_usdc = winning_bal / 1_000_000
                result.claimable.append(ClaimablePosition(
                    market_id=m["market_id"],
                    contract_address=m["contract_address"],
                    source=m["source"],
                    condition_id=m["condition_id"],
                    winning_outcome=m["winning_outcome"],
                    winning_balance=winning_bal,
                    payout_usdc=payout_usdc,
                ))
                result.total_claimable_usdc += payout_usdc
                is_claimable = True

        # Check for mergeable (paired YES+NO tokens, not being redeemed)
        if yes_bal > 0 and no_bal > 0 and not is_claimable:
            mergeable_amount = min(yes_bal, no_bal)
            merge_usdc = mergeable_amount / 1_000_000
            result.mergeable.append(MergeablePosition(
                market_id=m["market_id"],
                contract_address=m["contract_address"],
                source=m["source"],
                condition_id=m["condition_id"],
                yes_balance=yes_bal,
                no_balance=no_bal,
                mergeable_amount=mergeable_amount,
                merge_usdc=merge_usdc,
            ))
            result.total_mergeable_usdc += merge_usdc

    logger.info(
        "Discovery complete: %d claimable ($%.2f), %d mergeable ($%.2f), %d markets scanned",
        len(result.claimable), result.total_claimable_usdc,
        len(result.mergeable), result.total_mergeable_usdc,
        result.markets_scanned,
    )

    return result
