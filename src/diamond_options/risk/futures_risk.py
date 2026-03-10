"""Futures portfolio risk management — margin, exposure, and limits.

Tracks and monitors futures-specific risk metrics:
- Notional exposure and margin utilization
- Mark-to-market P&L across positions
- Basis risk (futures vs spot divergence)
- Rollover risk (near expiry positions)
- Concentration limits (per-symbol, per-direction)

Key differences from options risk:
- Futures delta is always ±1 per share (linear payoff)
- No gamma/vega/theta Greeks — risk is purely directional + basis
- Margin is the primary capital constraint
- Basis risk replaces IV risk
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from diamond_options.data.universe import get_futures_margin_pct, get_lot_size, get_index_lot_size


class FuturesRiskLevel(str, Enum):
    """Overall portfolio risk assessment."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class FuturesPositionRisk:
    """Risk metrics for a single futures position."""
    symbol: str
    action: str  # "BUY" (long) or "SELL" (short)
    lots: int
    lot_size: int
    entry_price: float
    current_price: float
    # Computed
    notional_value: float  # current_price × lots × lot_size
    unrealized_pnl: float  # (current - entry) × lots × lot_size × direction
    unrealized_pnl_pct: float  # As % of margin
    margin_required: float
    margin_utilization_pct: float  # margin / capital
    days_to_expiry: int
    basis_pct: float  # (futures - spot) / spot × 100


@dataclass(frozen=True)
class FuturesRiskAlert:
    """A risk limit breach or warning."""
    level: str  # "warning", "breach", "critical"
    metric: str
    current: float
    limit: float
    message: str


@dataclass(frozen=True)
class FuturesRiskLimits:
    """Configurable risk thresholds for futures portfolio."""
    max_notional_exposure: float = 5000000.0  # Max total notional (₹50L default)
    max_margin_utilization_pct: float = 60.0  # Max % of capital used as margin
    max_single_position_pct: float = 30.0  # Max single position as % of total margin
    max_unrealized_loss_pct: float = 5.0  # Max unrealized loss as % of capital
    max_concentration_pct: float = 40.0  # Max exposure in one symbol
    min_days_to_expiry: int = 2  # Warn when DTE < this
    max_basis_deviation_pct: float = 2.0  # Warn when basis exceeds this


@dataclass
class FuturesPortfolioRisk:
    """Aggregate risk metrics across all futures positions."""
    total_notional_long: float = 0.0
    total_notional_short: float = 0.0
    net_notional: float = 0.0
    gross_notional: float = 0.0
    total_margin: float = 0.0
    margin_utilization_pct: float = 0.0
    total_unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0  # As % of capital
    position_count: int = 0
    long_count: int = 0
    short_count: int = 0
    directional_bias: str = "neutral"  # "bullish", "bearish", "neutral"
    risk_level: FuturesRiskLevel = FuturesRiskLevel.LOW
    positions: list[FuturesPositionRisk] = field(default_factory=list)
    alerts: list[FuturesRiskAlert] = field(default_factory=list)
    by_symbol: dict[str, dict] = field(default_factory=dict)


def calculate_futures_position_risk(
    symbol: str,
    action: str,
    lots: int,
    lot_size: int,
    entry_price: float,
    current_price: float,
    spot_price: float,
    days_to_expiry: int,
    capital: float = 500000.0,
) -> FuturesPositionRisk:
    """Calculate risk metrics for a single futures position.

    Args:
        symbol: Underlying symbol.
        action: "BUY" or "SELL".
        lots: Number of lots.
        lot_size: Shares per lot.
        entry_price: Futures entry price.
        current_price: Current futures price.
        spot_price: Current spot price.
        days_to_expiry: Calendar DTE.
        capital: Total portfolio capital.

    Returns:
        FuturesPositionRisk with all metrics.
    """
    qty = lots * lot_size
    direction = 1.0 if action.upper() == "BUY" else -1.0

    notional = current_price * qty
    pnl = (current_price - entry_price) * qty * direction

    margin_pct = get_futures_margin_pct(symbol)
    margin = entry_price * qty * margin_pct

    basis_pct = ((current_price - spot_price) / spot_price * 100) if spot_price > 0 else 0.0

    return FuturesPositionRisk(
        symbol=symbol,
        action=action.upper(),
        lots=lots,
        lot_size=lot_size,
        entry_price=entry_price,
        current_price=current_price,
        notional_value=round(notional, 2),
        unrealized_pnl=round(pnl, 2),
        unrealized_pnl_pct=round(pnl / margin * 100, 2) if margin > 0 else 0.0,
        margin_required=round(margin, 2),
        margin_utilization_pct=round(margin / capital * 100, 2) if capital > 0 else 0.0,
        days_to_expiry=days_to_expiry,
        basis_pct=round(basis_pct, 3),
    )


def aggregate_futures_risk(
    positions: list[FuturesPositionRisk],
    capital: float = 500000.0,
    limits: FuturesRiskLimits | None = None,
) -> FuturesPortfolioRisk:
    """Aggregate risk across all futures positions and check limits.

    Args:
        positions: List of position-level risk metrics.
        capital: Total portfolio capital.
        limits: Risk thresholds (uses defaults if None).

    Returns:
        FuturesPortfolioRisk with aggregate metrics and alerts.
    """
    if limits is None:
        limits = FuturesRiskLimits()

    if not positions:
        return FuturesPortfolioRisk()

    total_long = sum(p.notional_value for p in positions if p.action == "BUY")
    total_short = sum(p.notional_value for p in positions if p.action == "SELL")
    net_notional = total_long - total_short
    gross_notional = total_long + total_short
    total_margin = sum(p.margin_required for p in positions)
    total_pnl = sum(p.unrealized_pnl for p in positions)
    long_count = sum(1 for p in positions if p.action == "BUY")
    short_count = sum(1 for p in positions if p.action == "SELL")

    margin_util = (total_margin / capital * 100) if capital > 0 else 0.0
    pnl_pct = (total_pnl / capital * 100) if capital > 0 else 0.0

    # Directional bias
    if net_notional > gross_notional * 0.2:
        bias = "bullish"
    elif net_notional < -gross_notional * 0.2:
        bias = "bearish"
    else:
        bias = "neutral"

    # By symbol
    by_symbol: dict[str, dict] = {}
    for p in positions:
        if p.symbol not in by_symbol:
            by_symbol[p.symbol] = {
                "notional_long": 0.0, "notional_short": 0.0,
                "margin": 0.0, "pnl": 0.0, "positions": 0,
            }
        if p.action == "BUY":
            by_symbol[p.symbol]["notional_long"] += p.notional_value
        else:
            by_symbol[p.symbol]["notional_short"] += p.notional_value
        by_symbol[p.symbol]["margin"] += p.margin_required
        by_symbol[p.symbol]["pnl"] += p.unrealized_pnl
        by_symbol[p.symbol]["positions"] += 1

    # Check limits
    alerts = _check_futures_limits(positions, capital, limits, gross_notional, total_margin, total_pnl, by_symbol)

    # Risk level
    if any(a.level == "critical" for a in alerts):
        risk_level = FuturesRiskLevel.CRITICAL
    elif any(a.level == "breach" for a in alerts):
        risk_level = FuturesRiskLevel.HIGH
    elif any(a.level == "warning" for a in alerts):
        risk_level = FuturesRiskLevel.MODERATE
    else:
        risk_level = FuturesRiskLevel.LOW

    return FuturesPortfolioRisk(
        total_notional_long=round(total_long, 2),
        total_notional_short=round(total_short, 2),
        net_notional=round(net_notional, 2),
        gross_notional=round(gross_notional, 2),
        total_margin=round(total_margin, 2),
        margin_utilization_pct=round(margin_util, 2),
        total_unrealized_pnl=round(total_pnl, 2),
        unrealized_pnl_pct=round(pnl_pct, 2),
        position_count=len(positions),
        long_count=long_count,
        short_count=short_count,
        directional_bias=bias,
        risk_level=risk_level,
        positions=positions,
        alerts=alerts,
        by_symbol={sym: {k: round(v, 2) for k, v in data.items()} for sym, data in by_symbol.items()},
    )


def _check_futures_limits(
    positions: list[FuturesPositionRisk],
    capital: float,
    limits: FuturesRiskLimits,
    gross_notional: float,
    total_margin: float,
    total_pnl: float,
    by_symbol: dict,
) -> list[FuturesRiskAlert]:
    """Check all risk limits and generate alerts."""
    alerts: list[FuturesRiskAlert] = []

    # Notional exposure
    if gross_notional > limits.max_notional_exposure:
        alerts.append(FuturesRiskAlert(
            level="breach",
            metric="notional_exposure",
            current=gross_notional,
            limit=limits.max_notional_exposure,
            message=f"Gross notional ₹{gross_notional:,.0f} exceeds limit ₹{limits.max_notional_exposure:,.0f}",
        ))
    elif gross_notional > limits.max_notional_exposure * 0.8:
        alerts.append(FuturesRiskAlert(
            level="warning",
            metric="notional_exposure",
            current=gross_notional,
            limit=limits.max_notional_exposure,
            message=f"Gross notional ₹{gross_notional:,.0f} approaching limit",
        ))

    # Margin utilization
    margin_util = (total_margin / capital * 100) if capital > 0 else 0
    if margin_util > limits.max_margin_utilization_pct:
        alerts.append(FuturesRiskAlert(
            level="breach",
            metric="margin_utilization",
            current=margin_util,
            limit=limits.max_margin_utilization_pct,
            message=f"Margin utilization {margin_util:.1f}% exceeds limit {limits.max_margin_utilization_pct:.0f}%",
        ))
    elif margin_util > limits.max_margin_utilization_pct * 0.8:
        alerts.append(FuturesRiskAlert(
            level="warning",
            metric="margin_utilization",
            current=margin_util,
            limit=limits.max_margin_utilization_pct,
            message=f"Margin utilization {margin_util:.1f}% approaching limit",
        ))

    # Unrealized loss
    if capital > 0 and total_pnl < 0:
        loss_pct = abs(total_pnl) / capital * 100
        if loss_pct > limits.max_unrealized_loss_pct:
            alerts.append(FuturesRiskAlert(
                level="critical",
                metric="unrealized_loss",
                current=loss_pct,
                limit=limits.max_unrealized_loss_pct,
                message=f"Unrealized loss {loss_pct:.1f}% of capital exceeds limit {limits.max_unrealized_loss_pct:.0f}%",
            ))

    # Concentration
    if gross_notional > 0:
        for sym, data in by_symbol.items():
            sym_notional = data.get("notional_long", 0) + data.get("notional_short", 0)
            conc_pct = sym_notional / gross_notional * 100
            if conc_pct > limits.max_concentration_pct:
                alerts.append(FuturesRiskAlert(
                    level="warning",
                    metric="concentration",
                    current=conc_pct,
                    limit=limits.max_concentration_pct,
                    message=f"{sym} concentration {conc_pct:.0f}% exceeds limit {limits.max_concentration_pct:.0f}%",
                ))

    # Single position margin
    if total_margin > 0:
        for p in positions:
            pos_pct = p.margin_required / total_margin * 100
            if pos_pct > limits.max_single_position_pct:
                alerts.append(FuturesRiskAlert(
                    level="warning",
                    metric="single_position",
                    current=pos_pct,
                    limit=limits.max_single_position_pct,
                    message=f"{p.symbol} {p.action} uses {pos_pct:.0f}% of total margin",
                ))

    # DTE warnings
    for p in positions:
        if p.days_to_expiry < limits.min_days_to_expiry:
            alerts.append(FuturesRiskAlert(
                level="warning",
                metric="expiry_proximity",
                current=p.days_to_expiry,
                limit=limits.min_days_to_expiry,
                message=f"{p.symbol} {p.action} expires in {p.days_to_expiry} days — consider rolling",
            ))

    # Basis deviation
    for p in positions:
        if abs(p.basis_pct) > limits.max_basis_deviation_pct:
            alerts.append(FuturesRiskAlert(
                level="warning",
                metric="basis_deviation",
                current=p.basis_pct,
                limit=limits.max_basis_deviation_pct,
                message=f"{p.symbol} basis {p.basis_pct:.3f}% deviates beyond ±{limits.max_basis_deviation_pct:.1f}%",
            ))

    return alerts


def futures_exposure_summary(
    portfolio: FuturesPortfolioRisk,
    capital: float,
) -> dict:
    """Generate a human-readable futures exposure summary.

    Args:
        portfolio: Aggregate portfolio risk.
        capital: Total capital.

    Returns:
        Summary dict with exposure metrics.
    """
    return {
        "total_notional_long": portfolio.total_notional_long,
        "total_notional_short": portfolio.total_notional_short,
        "net_notional": portfolio.net_notional,
        "gross_notional": portfolio.gross_notional,
        "total_margin": portfolio.total_margin,
        "margin_utilization_pct": portfolio.margin_utilization_pct,
        "available_margin": round(capital - portfolio.total_margin, 2),
        "unrealized_pnl": portfolio.total_unrealized_pnl,
        "unrealized_pnl_pct": portfolio.unrealized_pnl_pct,
        "directional_bias": portfolio.directional_bias,
        "risk_level": portfolio.risk_level.value,
        "position_count": portfolio.position_count,
        "long_positions": portfolio.long_count,
        "short_positions": portfolio.short_count,
        "by_symbol": portfolio.by_symbol,
        "alerts": [
            {"level": a.level, "metric": a.metric, "message": a.message}
            for a in portfolio.alerts
        ],
    }
