"""Unified portfolio view combining equity, options, and futures.

Provides a single risk dashboard across all three products with
cross-product alerts, hedge detection, and aggregate exposure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


# ── Dataclasses ────────────────────────────────────────────────


@dataclass(frozen=True)
class UnifiedPosition:
    """A position normalised across all three asset types."""

    asset_type: str  # "equity", "option", "future"
    symbol: str  # Underlying symbol (e.g., "RELIANCE")
    direction: str  # "long" or "short"
    quantity: int  # Shares / contracts
    notional_value: float  # Market value of position
    unrealized_pnl: float
    margin_used: float  # 0 for equity (fully paid)
    source: str  # "stock_engine", "options_ledger", "futures_ledger"
    detail: str  # Extra info: strike/type for options, expiry for futures


@dataclass(frozen=True)
class EquitySummary:
    """Summary of equity holdings."""

    count: int
    total_value: float
    fno_eligible_pct: float
    unrealized_pnl: float


@dataclass(frozen=True)
class OptionsSummary:
    """Summary of options positions."""

    count: int
    long_count: int
    short_count: int
    net_delta: float
    net_theta: float  # INR per day
    net_vega: float  # INR per 1% vol
    margin_used: float
    cash: float
    unrealized_pnl: float


@dataclass(frozen=True)
class FuturesSummary:
    """Summary of futures positions."""

    count: int
    long_count: int
    short_count: int
    net_notional: float  # Long - Short notional
    gross_notional: float  # Long + Short notional
    margin_used: float
    cash: float
    unrealized_pnl: float


@dataclass(frozen=True)
class UnifiedRiskAlert:
    """Cross-product risk alert."""

    level: str  # "info", "warning", "breach", "critical"
    category: str  # "margin", "concentration", "hedge", "expiry", "exposure"
    message: str


@dataclass
class UnifiedPortfolioRisk:
    """Complete cross-product portfolio risk view."""

    # Totals
    total_nav: float = 0.0
    total_margin_used: float = 0.0
    total_notional_exposure: float = 0.0  # Gross
    net_directional_exposure: float = 0.0  # Delta-adjusted

    # By product
    equity: EquitySummary = field(
        default_factory=lambda: EquitySummary(0, 0, 0, 0)
    )
    options: OptionsSummary = field(
        default_factory=lambda: OptionsSummary(0, 0, 0, 0, 0, 0, 0, 0, 0)
    )
    futures: FuturesSummary = field(
        default_factory=lambda: FuturesSummary(0, 0, 0, 0, 0, 0, 0, 0)
    )

    # Risk metrics
    portfolio_beta: float = 1.0
    hedge_ratio: float = 0.0
    margin_utilization_pct: float = 0.0
    daily_theta_income: float = 0.0
    max_daily_risk: float = 0.0

    # Alerts
    alerts: list[UnifiedRiskAlert] = field(default_factory=list)
    risk_level: str = "LOW"  # LOW / MODERATE / HIGH / CRITICAL

    # Positions
    all_positions: list[UnifiedPosition] = field(default_factory=list)
    by_symbol: dict[str, list[UnifiedPosition]] = field(default_factory=dict)


# ── Core Functions ─────────────────────────────────────────────


def build_unified_portfolio(
    stock_holdings: list[dict] | None = None,
    options_positions: list[dict] | None = None,
    futures_positions: list[dict] | None = None,
    options_cash: float = 0.0,
    options_margin: float = 0.0,
    futures_cash: float = 0.0,
    futures_margin: float = 0.0,
    capital: float = 500000.0,
) -> UnifiedPortfolioRisk:
    """Build a unified portfolio view from all three product sources.

    Accepts normalised dicts so the caller handles ledger/bridge access.
    This keeps the function pure and testable.

    Args:
        stock_holdings: List of dicts with symbol, shares, current_price,
            avg_price, market_value, unrealized_pnl, fno_eligible.
        options_positions: List of dicts with symbol, strike, option_type,
            lots, lot_size, avg_price, current_price (premium), direction,
            delta, theta, vega, margin.
        futures_positions: List of dicts with symbol, lots, lot_size,
            avg_price, current_price, direction, margin.
        options_cash: Available cash in options ledger.
        options_margin: Margin used by options positions.
        futures_cash: Available cash in futures ledger.
        futures_margin: Margin used by futures positions.
        capital: Total trading capital.

    Returns:
        UnifiedPortfolioRisk with aggregate metrics, alerts, and positions.
    """
    stock_holdings = stock_holdings or []
    options_positions = options_positions or []
    futures_positions = futures_positions or []

    all_positions: list[UnifiedPosition] = []
    by_symbol: dict[str, list[UnifiedPosition]] = {}

    # ── Equity ──────────────────────────────────────────────
    eq_value = 0.0
    eq_pnl = 0.0
    eq_fno_value = 0.0

    for h in stock_holdings:
        sym = h.get("symbol", "").upper()
        shares = h.get("shares", 0)
        mv = h.get("market_value", 0.0)
        pnl = h.get("unrealized_pnl", 0.0)
        fno = h.get("fno_eligible", False)

        eq_value += mv
        eq_pnl += pnl
        if fno:
            eq_fno_value += mv

        pos = UnifiedPosition(
            asset_type="equity",
            symbol=sym,
            direction="long",
            quantity=shares,
            notional_value=round(mv, 2),
            unrealized_pnl=round(pnl, 2),
            margin_used=0.0,
            source="stock_engine",
            detail=f"{shares} shares",
        )
        all_positions.append(pos)
        by_symbol.setdefault(sym, []).append(pos)

    fno_pct = (eq_fno_value / eq_value * 100) if eq_value > 0 else 0.0
    equity_summary = EquitySummary(
        count=len(stock_holdings),
        total_value=round(eq_value, 2),
        fno_eligible_pct=round(fno_pct, 1),
        unrealized_pnl=round(eq_pnl, 2),
    )

    # ── Options ─────────────────────────────────────────────
    opt_long = 0
    opt_short = 0
    opt_delta = 0.0
    opt_theta = 0.0
    opt_vega = 0.0
    opt_pnl = 0.0
    opt_notional = 0.0

    for o in options_positions:
        sym = o.get("symbol", "").upper()
        lots = o.get("lots", 0)
        lot_size = o.get("lot_size", 1)
        direction = o.get("direction", "long" if lots > 0 else "short")
        strike = o.get("strike", 0)
        opt_type = o.get("option_type", "CE")
        avg = o.get("avg_price", 0)
        cur = o.get("current_price", avg)
        delta = o.get("delta", 0.0)
        theta = o.get("theta", 0.0)
        vega = o.get("vega", 0.0)
        margin = o.get("margin", 0.0)

        qty = abs(lots) * lot_size
        pnl = (cur - avg) * lots * lot_size
        notional = abs(cur * qty)

        if lots > 0:
            opt_long += 1
        else:
            opt_short += 1

        opt_delta += delta
        opt_theta += theta
        opt_vega += vega
        opt_pnl += pnl
        opt_notional += notional

        pos = UnifiedPosition(
            asset_type="option",
            symbol=sym,
            direction=direction,
            quantity=abs(lots),
            notional_value=round(notional, 2),
            unrealized_pnl=round(pnl, 2),
            margin_used=round(margin, 2),
            source="options_ledger",
            detail=f"{strike} {opt_type} {'L' if lots > 0 else 'S'}{abs(lots)}",
        )
        all_positions.append(pos)
        by_symbol.setdefault(sym, []).append(pos)

    options_summary = OptionsSummary(
        count=len(options_positions),
        long_count=opt_long,
        short_count=opt_short,
        net_delta=round(opt_delta, 2),
        net_theta=round(opt_theta, 2),
        net_vega=round(opt_vega, 2),
        margin_used=round(options_margin, 2),
        cash=round(options_cash, 2),
        unrealized_pnl=round(opt_pnl, 2),
    )

    # ── Futures ─────────────────────────────────────────────
    fut_long = 0
    fut_short = 0
    fut_long_notional = 0.0
    fut_short_notional = 0.0
    fut_pnl = 0.0

    for f in futures_positions:
        sym = f.get("symbol", "").upper()
        lots = f.get("lots", 0)
        lot_size = f.get("lot_size", 65)
        avg = f.get("avg_price", 0)
        cur = f.get("current_price", avg)
        direction = f.get("direction", "long" if lots > 0 else "short")
        margin = f.get("margin", 0.0)

        qty = abs(lots) * lot_size
        notional = cur * qty

        if lots > 0:
            fut_long += 1
            fut_long_notional += notional
            pnl = (cur - avg) * qty
        else:
            fut_short += 1
            fut_short_notional += notional
            pnl = (avg - cur) * qty

        fut_pnl += pnl

        pos = UnifiedPosition(
            asset_type="future",
            symbol=sym,
            direction=direction,
            quantity=abs(lots),
            notional_value=round(notional, 2),
            unrealized_pnl=round(pnl, 2),
            margin_used=round(margin, 2),
            source="futures_ledger",
            detail=f"{'L' if lots > 0 else 'S'}{abs(lots)} lots × {lot_size}",
        )
        all_positions.append(pos)
        by_symbol.setdefault(sym, []).append(pos)

    net_notional = fut_long_notional - fut_short_notional
    gross_notional = fut_long_notional + fut_short_notional

    futures_summary = FuturesSummary(
        count=len(futures_positions),
        long_count=fut_long,
        short_count=fut_short,
        net_notional=round(net_notional, 2),
        gross_notional=round(gross_notional, 2),
        margin_used=round(futures_margin, 2),
        cash=round(futures_cash, 2),
        unrealized_pnl=round(fut_pnl, 2),
    )

    # ── Aggregate ───────────────────────────────────────────
    total_nav = eq_value + options_cash + futures_cash + opt_pnl + fut_pnl
    total_margin = options_margin + futures_margin
    total_notional = eq_value + opt_notional + gross_notional
    # Delta-adjusted: equity is delta=1, futures long=+1 short=-1, options use delta
    net_directional = eq_value + net_notional + (opt_delta * 100)  # rough delta→notional

    margin_util = (total_margin / capital * 100) if capital > 0 else 0.0

    # Hedge ratio: short exposure / long equity
    short_exposure = fut_short_notional + abs(min(opt_delta, 0)) * 100
    hedge_ratio = (short_exposure / eq_value) if eq_value > 0 else 0.0

    # Max daily risk: rough 2% move on net directional exposure
    max_daily = abs(net_directional) * 0.02

    # Risk level
    alerts = generate_unified_alerts(
        equity_summary, options_summary, futures_summary,
        total_margin, capital, by_symbol, eq_value,
    )

    critical = sum(1 for a in alerts if a.level == "critical")
    breaches = sum(1 for a in alerts if a.level == "breach")
    warnings = sum(1 for a in alerts if a.level == "warning")

    if critical > 0:
        risk_level = "CRITICAL"
    elif breaches > 0:
        risk_level = "HIGH"
    elif warnings > 0:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    return UnifiedPortfolioRisk(
        total_nav=round(total_nav, 2),
        total_margin_used=round(total_margin, 2),
        total_notional_exposure=round(total_notional, 2),
        net_directional_exposure=round(net_directional, 2),
        equity=equity_summary,
        options=options_summary,
        futures=futures_summary,
        portfolio_beta=1.0,  # Placeholder — real beta needs price history
        hedge_ratio=round(hedge_ratio, 4),
        margin_utilization_pct=round(margin_util, 2),
        daily_theta_income=round(opt_theta, 2),
        max_daily_risk=round(max_daily, 2),
        alerts=alerts,
        risk_level=risk_level,
        all_positions=all_positions,
        by_symbol=by_symbol,
    )


# ── Alert Generation ───────────────────────────────────────────


def generate_unified_alerts(
    equity: EquitySummary,
    options: OptionsSummary,
    futures: FuturesSummary,
    total_margin: float,
    capital: float,
    by_symbol: dict[str, list[UnifiedPosition]],
    equity_value: float,
) -> list[UnifiedRiskAlert]:
    """Generate cross-product risk alerts.

    Checks margin, concentration, hedge status, and exposure limits.
    """
    alerts: list[UnifiedRiskAlert] = []

    # ── Margin utilization ──────────────────────────────────
    margin_pct = (total_margin / capital * 100) if capital > 0 else 0.0
    if margin_pct > 80:
        alerts.append(UnifiedRiskAlert(
            level="critical",
            category="margin",
            message=f"Margin utilization at {margin_pct:.0f}% — reduce exposure immediately",
        ))
    elif margin_pct > 60:
        alerts.append(UnifiedRiskAlert(
            level="breach",
            category="margin",
            message=f"Margin utilization at {margin_pct:.0f}% — avoid new positions",
        ))
    elif margin_pct > 40:
        alerts.append(UnifiedRiskAlert(
            level="warning",
            category="margin",
            message=f"Margin utilization at {margin_pct:.0f}% — monitor closely",
        ))

    # ── Concentration per symbol ────────────────────────────
    total_notional = equity_value + futures.gross_notional
    if total_notional > 0:
        for sym, positions in by_symbol.items():
            sym_notional = sum(p.notional_value for p in positions)
            conc_pct = sym_notional / total_notional * 100
            if conc_pct > 50:
                alerts.append(UnifiedRiskAlert(
                    level="breach",
                    category="concentration",
                    message=f"{sym}: {conc_pct:.0f}% of total exposure — heavily concentrated",
                ))
            elif conc_pct > 30:
                alerts.append(UnifiedRiskAlert(
                    level="warning",
                    category="concentration",
                    message=f"{sym}: {conc_pct:.0f}% of total exposure — monitor concentration",
                ))

    # ── Hedge detection ─────────────────────────────────────
    for sym, positions in by_symbol.items():
        has_equity = any(p.asset_type == "equity" for p in positions)
        has_short_futures = any(
            p.asset_type == "future" and p.direction == "short" for p in positions
        )
        has_long_futures = any(
            p.asset_type == "future" and p.direction == "long" for p in positions
        )

        if has_equity and has_short_futures:
            eq_val = sum(p.notional_value for p in positions if p.asset_type == "equity")
            sf_val = sum(
                p.notional_value for p in positions
                if p.asset_type == "future" and p.direction == "short"
            )
            ratio = sf_val / eq_val if eq_val > 0 else 0
            if ratio > 1.2:
                alerts.append(UnifiedRiskAlert(
                    level="warning",
                    category="hedge",
                    message=f"{sym}: Over-hedged — short futures {ratio:.1f}× equity value",
                ))
            elif ratio > 0.8:
                alerts.append(UnifiedRiskAlert(
                    level="info",
                    category="hedge",
                    message=f"{sym}: Well-hedged — {ratio:.0%} of equity covered by short futures",
                ))
            else:
                alerts.append(UnifiedRiskAlert(
                    level="info",
                    category="hedge",
                    message=f"{sym}: Partially hedged — {ratio:.0%} of equity covered",
                ))

        elif has_equity and not has_short_futures:
            eq_val = sum(p.notional_value for p in positions if p.asset_type == "equity")
            if eq_val > 200000:
                alerts.append(UnifiedRiskAlert(
                    level="info",
                    category="hedge",
                    message=f"{sym}: Unhedged equity position worth Rs {eq_val:,.0f}",
                ))

    # ── No hedge on large equity portfolio ──────────────────
    if equity_value > 500000 and futures.short_count == 0 and options.short_count == 0:
        alerts.append(UnifiedRiskAlert(
            level="warning",
            category="hedge",
            message=f"No hedge on Rs {equity_value:,.0f} equity portfolio — consider futures or options hedge",
        ))

    # ── Total notional too large ────────────────────────────
    gross_all = equity_value + futures.gross_notional
    if capital > 0 and gross_all > capital * 3:
        alerts.append(UnifiedRiskAlert(
            level="breach",
            category="exposure",
            message=f"Gross notional {gross_all/capital:.1f}× capital — high leverage",
        ))

    return alerts


# ── Exposure Analysis ──────────────────────────────────────────


def unified_exposure_by_symbol(
    portfolio: UnifiedPortfolioRisk,
) -> list[dict]:
    """Per-symbol net exposure across equity, options, and futures.

    Returns:
        List of dicts with symbol, net exposure, breakdown, hedge status.
    """
    results = []

    for sym, positions in sorted(portfolio.by_symbol.items()):
        equity_val = sum(
            p.notional_value for p in positions if p.asset_type == "equity"
        )
        options_delta_val = sum(
            p.notional_value * (1 if p.direction == "long" else -1)
            for p in positions if p.asset_type == "option"
        )
        futures_val = sum(
            p.notional_value * (1 if p.direction == "long" else -1)
            for p in positions if p.asset_type == "future"
        )

        net_exposure = equity_val + options_delta_val + futures_val
        gross_exposure = sum(p.notional_value for p in positions)

        # Hedge status
        if equity_val > 0 and futures_val < 0:
            ratio = abs(futures_val) / equity_val if equity_val > 0 else 0
            if ratio > 1.1:
                hedge_status = "over_hedged"
            elif ratio > 0.8:
                hedge_status = "hedged"
            elif ratio > 0.3:
                hedge_status = "partially_hedged"
            else:
                hedge_status = "lightly_hedged"
        elif equity_val > 0:
            hedge_status = "unhedged"
        else:
            hedge_status = "derivatives_only"

        total_pnl = sum(p.unrealized_pnl for p in positions)

        results.append({
            "symbol": sym,
            "net_exposure": round(net_exposure, 2),
            "gross_exposure": round(gross_exposure, 2),
            "equity_value": round(equity_val, 2),
            "options_exposure": round(options_delta_val, 2),
            "futures_exposure": round(futures_val, 2),
            "hedge_status": hedge_status,
            "unrealized_pnl": round(total_pnl, 2),
            "position_count": len(positions),
            "asset_types": sorted({p.asset_type for p in positions}),
        })

    return results


# ── Daily Summary ──────────────────────────────────────────────


def unified_daily_summary(
    portfolio: UnifiedPortfolioRisk,
    capital: float = 500000.0,
) -> dict:
    """Morning briefing data across all products.

    Returns:
        Dict formatted for human consumption with NAV, margin, P&L,
        positions, and risk alerts.
    """
    total_pnl = (
        portfolio.equity.unrealized_pnl
        + portfolio.options.unrealized_pnl
        + portfolio.futures.unrealized_pnl
    )
    pnl_pct = (total_pnl / capital * 100) if capital > 0 else 0.0

    return {
        "date": date.today().isoformat(),
        "nav": portfolio.total_nav,
        "capital": capital,
        "total_unrealized_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(pnl_pct, 2),
        "margin_used": portfolio.total_margin_used,
        "margin_utilization_pct": portfolio.margin_utilization_pct,
        "available_margin": round(capital - portfolio.total_margin_used, 2),
        "equity": {
            "count": portfolio.equity.count,
            "value": portfolio.equity.total_value,
            "pnl": portfolio.equity.unrealized_pnl,
        },
        "options": {
            "count": portfolio.options.count,
            "long": portfolio.options.long_count,
            "short": portfolio.options.short_count,
            "net_delta": portfolio.options.net_delta,
            "daily_theta": portfolio.options.net_theta,
            "pnl": portfolio.options.unrealized_pnl,
        },
        "futures": {
            "count": portfolio.futures.count,
            "long": portfolio.futures.long_count,
            "short": portfolio.futures.short_count,
            "net_notional": portfolio.futures.net_notional,
            "pnl": portfolio.futures.unrealized_pnl,
        },
        "hedge_ratio": portfolio.hedge_ratio,
        "risk_level": portfolio.risk_level,
        "alerts": [
            {"level": a.level, "category": a.category, "message": a.message}
            for a in portfolio.alerts
        ],
        "positions_by_symbol": [
            {
                "symbol": sym,
                "types": sorted({p.asset_type for p in positions}),
                "count": len(positions),
                "total_pnl": round(sum(p.unrealized_pnl for p in positions), 2),
            }
            for sym, positions in sorted(portfolio.by_symbol.items())
        ],
    }
