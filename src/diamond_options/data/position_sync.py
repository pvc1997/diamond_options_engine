"""Live position sync from Kite broker.

Parses Kite get_positions response into structured formats, builds portfolio
summaries, maps to engine's OptionTrade format, and compares broker positions
with the local ledger for reconciliation.

Usage:
    1. Call Kite MCP `get_positions` to get raw position dicts
    2. Pass list of dicts to `sync_positions()` for portfolio summary
    3. Use `compare_positions()` to reconcile with local ledger
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from diamond_options.data.futures_ledger import FuturesPosition, FuturesTrade
from diamond_options.data.kite_bridge import parse_futures_symbol, parse_kite_symbol
from diamond_options.data.ledger import OptionTrade, Position
from diamond_options.data.universe import get_index_lot_size, get_lot_size

logger = logging.getLogger(__name__)


@dataclass
class KitePosition:
    """A parsed Kite broker position."""

    symbol: str  # Underlying (e.g., "NIFTY")
    tradingsymbol: str  # Raw Kite symbol (e.g., "NIFTY2631024500CE")
    exchange: str  # NFO, BFO, etc.
    strike: float  # Strike price
    option_type: str  # CE or PE
    expiry: date | None  # Expiry date (None for monthly format without day)
    quantity: int  # Positive = long, negative = short
    avg_price: float  # Average entry price
    ltp: float  # Last traded price
    pnl: float  # Total P&L
    m2m: float  # Mark-to-market P&L
    product: str  # NRML, MIS, etc.
    instrument_token: int  # Kite instrument token

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    @property
    def unrealized_pnl(self) -> float:
        """P&L based on LTP vs avg_price."""
        return (self.ltp - self.avg_price) * self.quantity

    @property
    def lot_size(self) -> int:
        """Look up lot size from universe."""
        ls = get_lot_size(self.symbol)
        if ls == 0:
            ls = get_index_lot_size(self.symbol)
        return ls

    @property
    def lots(self) -> int:
        """Number of lots (signed). Returns quantity if lot_size unknown."""
        ls = self.lot_size
        if ls > 0:
            return self.quantity // ls
        return self.quantity


@dataclass
class PortfolioSync:
    """Summary of live Kite positions."""

    positions: list[KitePosition]
    total_pnl: float
    total_m2m: float
    num_long: int
    num_short: int
    net_quantity_by_symbol: dict[str, int] = field(default_factory=dict)
    margin_used: float = 0.0
    futures_positions: list[dict] = field(default_factory=list)
    sync_timestamp: str = ""


def parse_kite_position(raw: dict) -> KitePosition | None:
    """Parse a single Kite position dict into KitePosition.

    Args:
        raw: A position dict from Kite get_positions response.

    Returns:
        KitePosition if it's an options position, None if not parseable
        (e.g., futures or equity).
    """
    tradingsymbol = raw.get("tradingsymbol", "")
    if not tradingsymbol:
        return None

    parsed = parse_kite_symbol(tradingsymbol)
    if parsed is None:
        # Not an options symbol (could be futures, equity, etc.)
        return None

    # Determine expiry
    expiry = parsed.get("expiry")  # date object for weekly format
    # Monthly format has year/month but no day — expiry will be None

    quantity = raw.get("quantity", 0)
    if quantity == 0:
        # Closed position, skip
        return None

    return KitePosition(
        symbol=parsed["symbol"],
        tradingsymbol=tradingsymbol,
        exchange=raw.get("exchange", "NFO"),
        strike=parsed["strike"],
        option_type=parsed["option_type"],
        expiry=expiry,
        quantity=quantity,
        avg_price=raw.get("average_price", 0.0),
        ltp=raw.get("last_price", 0.0),
        pnl=raw.get("pnl", 0.0),
        m2m=raw.get("m2m", 0.0),
        product=raw.get("product", "NRML"),
        instrument_token=raw.get("instrument_token", 0),
    )


def _is_futures_position(raw: dict) -> bool:
    """Check if a raw Kite position is a futures contract (not options)."""
    ts = raw.get("tradingsymbol", "")
    # Futures don't end in CE or PE
    return bool(ts) and not ts.endswith("CE") and not ts.endswith("PE")


def sync_positions(kite_positions: list[dict]) -> PortfolioSync:
    """Build a portfolio summary from Kite positions.

    Args:
        kite_positions: List of position dicts from Kite get_positions.

    Returns:
        PortfolioSync with parsed positions and summary stats.
    """
    parsed: list[KitePosition] = []
    futures: list[dict] = []
    total_pnl = 0.0
    total_m2m = 0.0
    num_long = 0
    num_short = 0
    net_qty: dict[str, int] = {}

    for raw in kite_positions:
        quantity = raw.get("quantity", 0)
        if quantity == 0:
            continue

        # Track total P&L across all positions (options + futures)
        total_pnl += raw.get("pnl", 0.0)
        total_m2m += raw.get("m2m", 0.0)

        if _is_futures_position(raw):
            futures.append(raw)
            continue

        kp = parse_kite_position(raw)
        if kp is None:
            continue

        parsed.append(kp)

        if kp.is_long:
            num_long += 1
        elif kp.is_short:
            num_short += 1

        # Net quantity by underlying symbol
        net_qty[kp.symbol] = net_qty.get(kp.symbol, 0) + kp.quantity

    return PortfolioSync(
        positions=parsed,
        total_pnl=round(total_pnl, 2),
        total_m2m=round(total_m2m, 2),
        num_long=num_long,
        num_short=num_short,
        net_quantity_by_symbol=net_qty,
        futures_positions=futures,
        sync_timestamp=datetime.now().isoformat(),
    )


def kite_position_to_trade(
    pos: KitePosition,
    strategy_tag: str = "kite_sync",
    trade_group: str = "",
    rationale: str = "Synced from Kite broker",
) -> OptionTrade:
    """Convert a KitePosition to an OptionTrade for ledger recording.

    Args:
        pos: Parsed Kite position.
        strategy_tag: Strategy tag for the trade.
        trade_group: Trade group identifier. If empty, auto-generates from position.
        rationale: Rationale string for the ledger.

    Returns:
        OptionTrade ready for ledger recording.
    """
    # Determine action from quantity sign
    action = "BUY" if pos.quantity > 0 else "SELL"

    # Lot size from universe
    ls = pos.lot_size
    if ls == 0:
        # Fallback: use absolute quantity as 1 lot
        ls = abs(pos.quantity)

    lots = abs(pos.quantity) // ls if ls > 0 else 1

    # Expiry as ISO string
    expiry_str = pos.expiry.isoformat() if pos.expiry else ""

    # Auto-generate trade_group if not provided
    if not trade_group:
        trade_group = f"kite_{pos.symbol}_{expiry_str}_{pos.product}"

    return OptionTrade(
        timestamp=datetime.now().isoformat(),
        action=action,
        symbol=pos.symbol,
        strike=pos.strike,
        option_type=pos.option_type,
        expiry=expiry_str,
        lots=lots,
        lot_size=ls,
        price=pos.avg_price,
        total_cost=0.0,  # Costs already incurred at broker
        strategy_tag=strategy_tag,
        trade_group=trade_group,
        rationale=rationale,
    )


def _position_key(symbol: str, strike: float, option_type: str, expiry: str) -> str:
    """Create a unique key for position matching."""
    return f"{symbol}_{strike}_{option_type}_{expiry}"


def compare_positions(
    kite_positions: list[KitePosition],
    ledger_positions: list[Position],
) -> dict:
    """Compare Kite live positions with local ledger positions.

    Identifies matched positions, positions only in Kite (untracked),
    positions only in the ledger (stale), and P&L differences.

    Args:
        kite_positions: Parsed KitePosition list.
        ledger_positions: Position list from OptionsLedger.get_positions().

    Returns:
        Dict with:
            - matched: list of {kite, ledger, qty_match, qty_diff}
            - kite_only: list of KitePosition not in ledger
            - ledger_only: list of Position not in Kite
            - summary: human-readable summary string
    """
    # Build lookup maps
    kite_map: dict[str, KitePosition] = {}
    for kp in kite_positions:
        expiry_str = kp.expiry.isoformat() if kp.expiry else ""
        key = _position_key(kp.symbol, kp.strike, kp.option_type, expiry_str)
        kite_map[key] = kp

    ledger_map: dict[str, Position] = {}
    for lp in ledger_positions:
        key = _position_key(lp.symbol, lp.strike, lp.option_type, lp.expiry)
        ledger_map[key] = lp

    matched = []
    kite_only = []
    ledger_only = []

    # Check Kite positions against ledger
    for key, kp in kite_map.items():
        if key in ledger_map:
            lp = ledger_map[key]
            kite_qty = kp.quantity
            ledger_qty = lp.lots * lp.lot_size
            qty_match = kite_qty == ledger_qty
            matched.append({
                "kite": kp,
                "ledger": lp,
                "qty_match": qty_match,
                "qty_diff": kite_qty - ledger_qty,
                "kite_qty": kite_qty,
                "ledger_qty": ledger_qty,
            })
        else:
            kite_only.append(kp)

    # Check ledger positions not in Kite
    for key, lp in ledger_map.items():
        if key not in kite_map:
            ledger_only.append(lp)

    # Build summary
    parts = [f"Matched: {len(matched)}"]
    mismatched = [m for m in matched if not m["qty_match"]]
    if mismatched:
        parts.append(f"Quantity mismatches: {len(mismatched)}")
    if kite_only:
        parts.append(f"Kite-only (untracked): {len(kite_only)}")
    if ledger_only:
        parts.append(f"Ledger-only (stale): {len(ledger_only)}")
    if not mismatched and not kite_only and not ledger_only:
        parts.append("All positions in sync")

    return {
        "matched": matched,
        "kite_only": kite_only,
        "ledger_only": ledger_only,
        "summary": " | ".join(parts),
    }


def detect_spreads(positions: list[KitePosition]) -> dict[str, list[KitePosition]]:
    """Group positions into potential multi-leg spreads.

    Positions with the same underlying symbol and expiry are grouped together,
    as they likely form a spread strategy.

    Args:
        positions: List of parsed KitePositions.

    Returns:
        Dict of {group_key: [positions]} where group_key is "SYMBOL_EXPIRY".
    """
    groups: dict[str, list[KitePosition]] = {}

    for pos in positions:
        expiry_str = pos.expiry.isoformat() if pos.expiry else "unknown"
        key = f"{pos.symbol}_{expiry_str}"
        if key not in groups:
            groups[key] = []
        groups[key].append(pos)

    return groups


# --- Futures position parsing ---


@dataclass
class KiteFuturesPosition:
    """A parsed Kite broker futures position."""

    symbol: str  # Underlying (e.g., "NIFTY")
    tradingsymbol: str  # Raw Kite symbol (e.g., "NIFTY26MARFUT")
    exchange: str  # NFO, BFO, etc.
    expiry_year: int
    expiry_month: int
    quantity: int  # Positive = long, negative = short
    avg_price: float
    ltp: float
    pnl: float
    m2m: float
    product: str  # NRML, MIS, etc.
    instrument_token: int

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    @property
    def unrealized_pnl(self) -> float:
        return (self.ltp - self.avg_price) * self.quantity

    @property
    def lot_size(self) -> int:
        ls = get_lot_size(self.symbol)
        if ls == 0:
            ls = get_index_lot_size(self.symbol)
        return ls

    @property
    def lots(self) -> int:
        ls = self.lot_size
        if ls > 0:
            return self.quantity // ls
        return self.quantity

    @property
    def notional_value(self) -> float:
        return abs(self.ltp * self.quantity)


def parse_kite_futures_position(raw: dict) -> KiteFuturesPosition | None:
    """Parse a single Kite position dict into KiteFuturesPosition.

    Args:
        raw: A position dict from Kite get_positions response.

    Returns:
        KiteFuturesPosition if it's a futures position, None otherwise.
    """
    tradingsymbol = raw.get("tradingsymbol", "")
    if not tradingsymbol:
        return None

    parsed = parse_futures_symbol(tradingsymbol)
    if parsed is None:
        return None

    quantity = raw.get("quantity", 0)
    if quantity == 0:
        return None

    return KiteFuturesPosition(
        symbol=parsed["symbol"],
        tradingsymbol=tradingsymbol,
        exchange=raw.get("exchange", "NFO"),
        expiry_year=parsed["year"],
        expiry_month=parsed["month"],
        quantity=quantity,
        avg_price=raw.get("average_price", 0.0),
        ltp=raw.get("last_price", 0.0),
        pnl=raw.get("pnl", 0.0),
        m2m=raw.get("m2m", 0.0),
        product=raw.get("product", "NRML"),
        instrument_token=raw.get("instrument_token", 0),
    )


def kite_futures_position_to_trade(
    pos: KiteFuturesPosition,
    expiry: date | None = None,
    strategy_tag: str = "kite_sync",
    trade_group: str = "",
    rationale: str = "Synced from Kite broker",
) -> FuturesTrade:
    """Convert a KiteFuturesPosition to a FuturesTrade for ledger recording.

    Args:
        pos: Parsed Kite futures position.
        expiry: Expiry date. If None, uses last day of expiry_month.
        strategy_tag: Strategy tag for the trade.
        trade_group: Trade group identifier.
        rationale: Rationale string.

    Returns:
        FuturesTrade ready for ledger recording.
    """
    action = "BUY" if pos.quantity > 0 else "SELL"

    ls = pos.lot_size
    if ls == 0:
        ls = abs(pos.quantity)

    lots = abs(pos.quantity) // ls if ls > 0 else 1

    # Determine expiry date
    if expiry is None:
        # Use last day of the month as approximation
        import calendar

        _, last_day = calendar.monthrange(pos.expiry_year, pos.expiry_month)
        expiry = date(pos.expiry_year, pos.expiry_month, last_day)

    expiry_str = expiry.isoformat()

    if not trade_group:
        trade_group = f"kite_{pos.symbol}_{expiry_str}_{pos.product}"

    return FuturesTrade(
        timestamp=datetime.now().isoformat(),
        action=action,
        symbol=pos.symbol,
        expiry=expiry_str,
        lots=lots,
        lot_size=ls,
        price=pos.avg_price,
        total_cost=0.0,
        strategy_tag=strategy_tag,
        trade_group=trade_group,
        rationale=rationale,
    )


def compare_futures_positions(
    kite_positions: list[KiteFuturesPosition],
    ledger_positions: list[FuturesPosition],
) -> dict:
    """Compare Kite live futures positions with local ledger.

    Args:
        kite_positions: Parsed KiteFuturesPosition list.
        ledger_positions: FuturesPosition list from FuturesLedger.get_positions().

    Returns:
        Dict with matched, kite_only, ledger_only, and summary.
    """
    kite_map: dict[str, KiteFuturesPosition] = {}
    for kp in kite_positions:
        key = f"{kp.symbol}_{kp.expiry_year}_{kp.expiry_month}"
        kite_map[key] = kp

    ledger_map: dict[str, FuturesPosition] = {}
    for lp in ledger_positions:
        try:
            exp = date.fromisoformat(lp.expiry)
            key = f"{lp.symbol}_{exp.year}_{exp.month}"
        except ValueError:
            key = f"{lp.symbol}_{lp.expiry}"
        ledger_map[key] = lp

    matched = []
    kite_only = []
    ledger_only = []

    for key, kp in kite_map.items():
        if key in ledger_map:
            lp = ledger_map[key]
            kite_qty = kp.quantity
            ledger_qty = lp.lots * lp.lot_size
            matched.append({
                "kite": kp,
                "ledger": lp,
                "qty_match": kite_qty == ledger_qty,
                "qty_diff": kite_qty - ledger_qty,
                "kite_qty": kite_qty,
                "ledger_qty": ledger_qty,
            })
        else:
            kite_only.append(kp)

    for key, lp in ledger_map.items():
        if key not in kite_map:
            ledger_only.append(lp)

    parts = [f"Matched: {len(matched)}"]
    mismatched = [m for m in matched if not m["qty_match"]]
    if mismatched:
        parts.append(f"Quantity mismatches: {len(mismatched)}")
    if kite_only:
        parts.append(f"Kite-only (untracked): {len(kite_only)}")
    if ledger_only:
        parts.append(f"Ledger-only (stale): {len(ledger_only)}")
    if not mismatched and not kite_only and not ledger_only:
        parts.append("All positions in sync")

    return {
        "matched": matched,
        "kite_only": kite_only,
        "ledger_only": ledger_only,
        "summary": " | ".join(parts),
    }
