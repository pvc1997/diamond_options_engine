"""Portfolio-level Greeks aggregation and risk limits.

Aggregates Greeks across all open positions to monitor overall
portfolio exposure. Enforces configurable limits and generates
warnings when thresholds are breached.

Key metrics:
- Portfolio Delta: Net directional exposure (target: near zero for neutral)
- Portfolio Gamma: Rate of delta change — high gamma = volatile delta
- Portfolio Theta: Daily time decay P&L (positive for net sellers)
- Portfolio Vega: Sensitivity to IV changes across all positions
- Beta-weighted delta: Delta normalized to index equivalent
"""

from __future__ import annotations

from dataclasses import dataclass, field

from diamond_options.pricing.greeks import calculate_greeks, Greeks


@dataclass(frozen=True)
class PositionGreeks:
    """Greeks for a single position (per-lot scaled)."""
    symbol: str
    strike: float
    option_type: str       # CE or PE
    action: str            # BUY or SELL
    lots: int
    lot_size: int
    # Per-lot Greeks
    delta: float
    gamma: float
    theta: float           # Per day, in INR
    vega: float
    rho: float
    # Metadata
    iv: float
    days_to_expiry: int


@dataclass
class PortfolioGreeks:
    """Aggregate Greeks across all positions."""
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0      # INR per day
    net_vega: float = 0.0
    net_rho: float = 0.0
    position_count: int = 0
    positions: list[PositionGreeks] = field(default_factory=list)


@dataclass(frozen=True)
class RiskLimits:
    """Configurable risk thresholds."""
    max_portfolio_delta: float = 500.0       # Max absolute net delta (in shares)
    max_portfolio_gamma: float = 100.0       # Max absolute net gamma
    max_portfolio_vega: float = 5000.0       # Max absolute net vega (INR per 1% vol)
    max_daily_theta: float = -10000.0        # Max daily decay (INR, negative = loss limit)
    max_single_position_delta: float = 200.0  # Per-position delta cap
    max_concentration_pct: float = 30.0       # Max % of portfolio in one underlying


@dataclass(frozen=True)
class RiskAlert:
    """A risk limit breach or warning."""
    level: str          # "warning", "breach", "critical"
    metric: str         # Which Greek/metric
    current: float
    limit: float
    message: str


def calculate_position_greeks(
    symbol: str,
    spot: float,
    strike: float,
    option_type: str,
    action: str,
    lots: int,
    lot_size: int,
    days_to_expiry: int,
    iv: float,
    r: float = 0.065,
) -> PositionGreeks:
    """Calculate scaled Greeks for a single position.

    Greeks are scaled by quantity and direction:
    - Long positions: positive delta (calls), negative delta (puts)
    - Short positions: signs reversed

    Args:
        symbol: Underlying symbol.
        spot: Current spot price.
        strike: Strike price.
        option_type: CE or PE.
        action: BUY or SELL.
        lots: Number of lots.
        lot_size: Shares per lot.
        days_to_expiry: Calendar DTE.
        iv: Implied volatility (decimal).
        r: Risk-free rate.

    Returns:
        PositionGreeks with lot-scaled values.
    """
    T = days_to_expiry / 365.0
    g = calculate_greeks(spot, strike, T, r, iv, option_type)

    qty = lots * lot_size
    sign = 1.0 if action.upper() == "BUY" else -1.0

    return PositionGreeks(
        symbol=symbol,
        strike=strike,
        option_type=option_type.upper(),
        action=action.upper(),
        lots=lots,
        lot_size=lot_size,
        delta=round(g.delta * qty * sign, 2),
        gamma=round(g.gamma * qty * sign, 4),
        theta=round(g.theta * qty * sign, 2),
        vega=round(g.vega * qty * sign, 2),
        rho=round(g.rho * qty * sign, 2),
        iv=iv,
        days_to_expiry=days_to_expiry,
    )


def aggregate_portfolio_greeks(
    positions: list[PositionGreeks],
) -> PortfolioGreeks:
    """Aggregate Greeks across all positions.

    Simple summation — the correct way to aggregate first-order Greeks.

    Args:
        positions: List of position-level Greeks.

    Returns:
        PortfolioGreeks with net values.
    """
    if not positions:
        return PortfolioGreeks()

    return PortfolioGreeks(
        net_delta=round(sum(p.delta for p in positions), 2),
        net_gamma=round(sum(p.gamma for p in positions), 4),
        net_theta=round(sum(p.theta for p in positions), 2),
        net_vega=round(sum(p.vega for p in positions), 2),
        net_rho=round(sum(p.rho for p in positions), 2),
        position_count=len(positions),
        positions=positions,
    )


def check_risk_limits(
    portfolio: PortfolioGreeks,
    limits: RiskLimits | None = None,
) -> list[RiskAlert]:
    """Check portfolio Greeks against risk limits.

    Returns alerts for any breached or near-breached limits.
    Warning at 80% of limit, breach at 100%.

    Args:
        portfolio: Aggregate portfolio Greeks.
        limits: Risk thresholds (uses defaults if None).

    Returns:
        List of RiskAlert for any issues found.
    """
    if limits is None:
        limits = RiskLimits()

    alerts: list[RiskAlert] = []

    # Delta check
    abs_delta = abs(portfolio.net_delta)
    if abs_delta > limits.max_portfolio_delta:
        alerts.append(RiskAlert(
            level="breach",
            metric="portfolio_delta",
            current=portfolio.net_delta,
            limit=limits.max_portfolio_delta,
            message=f"Portfolio delta {portfolio.net_delta:.0f} exceeds limit ±{limits.max_portfolio_delta:.0f}",
        ))
    elif abs_delta > limits.max_portfolio_delta * 0.8:
        alerts.append(RiskAlert(
            level="warning",
            metric="portfolio_delta",
            current=portfolio.net_delta,
            limit=limits.max_portfolio_delta,
            message=f"Portfolio delta {portfolio.net_delta:.0f} approaching limit ±{limits.max_portfolio_delta:.0f}",
        ))

    # Gamma check
    abs_gamma = abs(portfolio.net_gamma)
    if abs_gamma > limits.max_portfolio_gamma:
        alerts.append(RiskAlert(
            level="breach",
            metric="portfolio_gamma",
            current=portfolio.net_gamma,
            limit=limits.max_portfolio_gamma,
            message=f"Portfolio gamma {portfolio.net_gamma:.2f} exceeds limit ±{limits.max_portfolio_gamma:.0f}",
        ))
    elif abs_gamma > limits.max_portfolio_gamma * 0.8:
        alerts.append(RiskAlert(
            level="warning",
            metric="portfolio_gamma",
            current=portfolio.net_gamma,
            limit=limits.max_portfolio_gamma,
            message=f"Portfolio gamma {portfolio.net_gamma:.2f} approaching limit",
        ))

    # Vega check
    abs_vega = abs(portfolio.net_vega)
    if abs_vega > limits.max_portfolio_vega:
        alerts.append(RiskAlert(
            level="breach",
            metric="portfolio_vega",
            current=portfolio.net_vega,
            limit=limits.max_portfolio_vega,
            message=f"Portfolio vega ₹{portfolio.net_vega:,.0f} exceeds limit ±₹{limits.max_portfolio_vega:,.0f}",
        ))
    elif abs_vega > limits.max_portfolio_vega * 0.8:
        alerts.append(RiskAlert(
            level="warning",
            metric="portfolio_vega",
            current=portfolio.net_vega,
            limit=limits.max_portfolio_vega,
            message=f"Portfolio vega ₹{portfolio.net_vega:,.0f} approaching limit",
        ))

    # Theta check (negative theta = losing money daily)
    if portfolio.net_theta < limits.max_daily_theta:
        alerts.append(RiskAlert(
            level="breach",
            metric="daily_theta",
            current=portfolio.net_theta,
            limit=limits.max_daily_theta,
            message=f"Daily theta ₹{portfolio.net_theta:,.0f} exceeds loss limit ₹{limits.max_daily_theta:,.0f}",
        ))

    # Per-position delta check
    for pos in portfolio.positions:
        if abs(pos.delta) > limits.max_single_position_delta:
            alerts.append(RiskAlert(
                level="warning",
                metric="position_delta",
                current=pos.delta,
                limit=limits.max_single_position_delta,
                message=(
                    f"{pos.symbol} {pos.strike}{pos.option_type} delta {pos.delta:.0f} "
                    f"exceeds per-position limit ±{limits.max_single_position_delta:.0f}"
                ),
            ))

    return alerts


def portfolio_exposure_summary(
    portfolio: PortfolioGreeks,
    spot: float,
) -> dict:
    """Generate a human-readable portfolio exposure summary.

    Args:
        portfolio: Aggregate portfolio Greeks.
        spot: Current underlying price (for notional calculations).

    Returns:
        Summary dict with exposure metrics.
    """
    # Notional delta exposure
    notional_delta = portfolio.net_delta * spot

    # Greeks by underlying
    by_symbol: dict[str, dict] = {}
    for pos in portfolio.positions:
        if pos.symbol not in by_symbol:
            by_symbol[pos.symbol] = {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "positions": 0}
        by_symbol[pos.symbol]["delta"] += pos.delta
        by_symbol[pos.symbol]["gamma"] += pos.gamma
        by_symbol[pos.symbol]["theta"] += pos.theta
        by_symbol[pos.symbol]["vega"] += pos.vega
        by_symbol[pos.symbol]["positions"] += 1

    # Directional bias
    if portfolio.net_delta > 50:
        bias = "bullish"
    elif portfolio.net_delta < -50:
        bias = "bearish"
    else:
        bias = "neutral"

    return {
        "net_delta": portfolio.net_delta,
        "net_gamma": portfolio.net_gamma,
        "net_theta": portfolio.net_theta,
        "net_vega": portfolio.net_vega,
        "notional_delta_exposure": round(notional_delta, 0),
        "directional_bias": bias,
        "position_count": portfolio.position_count,
        "by_symbol": {
            sym: {k: round(v, 2) for k, v in data.items()}
            for sym, data in by_symbol.items()
        },
        "daily_theta_pnl": portfolio.net_theta,
        "weekly_theta_pnl": round(portfolio.net_theta * 5, 2),
    }
