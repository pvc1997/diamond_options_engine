"""Portfolio-level hedging with index options.

Analyzes an equity portfolio's market exposure and suggests
NIFTY/BANKNIFTY options to hedge systematic risk.
"""

from __future__ import annotations

from dataclasses import dataclass

from diamond_options.integration.stock_bridge import StockPortfolio


@dataclass(frozen=True)
class PortfolioHedgeAnalysis:
    """Analysis of portfolio's hedging needs."""
    portfolio_value: float
    equity_value: float
    beta: float
    beta_adjusted_exposure: float  # equity_value * beta
    hedge_notional: float          # How much index exposure to hedge
    nifty_spot: float
    nifty_lot_size: int
    lots_to_hedge: int             # Full hedge
    lots_partial_hedge: int        # 50% hedge
    hedging_options: list[HedgeOption]
    summary: str


@dataclass(frozen=True)
class HedgeOption:
    """A specific hedging instrument/strategy."""
    name: str
    strategy: str              # protective_put, bear_put_spread, collar
    strike: float
    strike_2: float | None     # For spreads
    premium_per_share: float
    total_cost: float
    cost_as_pct: float         # Cost as % of portfolio value
    annualized_cost_pct: float
    protection_level: str      # e.g., "-5% downside floor"
    max_loss_hedged: float     # Max portfolio loss with hedge
    days_to_expiry: int
    lots: int
    notes: str


def analyze_portfolio_hedge(
    portfolio: StockPortfolio,
    nifty_spot: float = 22500.0,
    portfolio_beta: float = 1.0,
    days_to_expiry: int = 30,
    volatility: float = 0.13,
    risk_free_rate: float = 0.065,
    hedge_ratio: float = 1.0,
) -> PortfolioHedgeAnalysis:
    """Analyze portfolio and suggest index option hedges.

    Uses NIFTY options to hedge systematic (market) risk.
    The number of lots is based on portfolio beta and value.

    Args:
        portfolio: Stock portfolio from the bridge.
        nifty_spot: Current NIFTY spot.
        portfolio_beta: Portfolio beta to NIFTY (default 1.0).
        days_to_expiry: Target hedge duration.
        volatility: NIFTY IV estimate.
        risk_free_rate: Risk-free rate.
        hedge_ratio: 1.0 = full hedge, 0.5 = half hedge.

    Returns:
        PortfolioHedgeAnalysis with multiple hedge options.
    """
    from diamond_options.pricing.black_scholes import price_option
    from diamond_options.data.universe import INDEX_CONTRACTS

    lot_size = INDEX_CONTRACTS["NIFTY"]["lot_size"]
    equity_value = portfolio.total_value
    beta_adjusted = equity_value * portfolio_beta

    # Number of NIFTY lots to hedge
    notional_per_lot = nifty_spot * lot_size
    lots_full = max(1, round(beta_adjusted * hedge_ratio / notional_per_lot))
    lots_partial = max(1, round(beta_adjusted * 0.5 / notional_per_lot))

    T = days_to_expiry / 365.0

    hedging_options = []

    # 1. Protective put — buy OTM NIFTY put
    for label, otm_pct in [("5% OTM Put", 0.05), ("3% OTM Put", 0.03), ("ATM Put", 0.0)]:
        strike = round((nifty_spot * (1 - otm_pct)) / 50) * 50
        bs = price_option(nifty_spot, strike, T, risk_free_rate, volatility, "PE")

        total_cost = bs.price * lot_size * lots_full
        cost_pct = total_cost / equity_value * 100 if equity_value > 0 else 0
        annualized = cost_pct * (365 / days_to_expiry)

        protection = f"-{otm_pct*100:.0f}% downside floor" if otm_pct > 0 else "Full ATM protection"
        max_loss = equity_value * otm_pct + total_cost

        notes = []
        if annualized < 5:
            notes.append("Cost-effective hedge")
        elif annualized > 15:
            notes.append("Expensive — consider spread or collar instead")
        if otm_pct == 0:
            notes.append("Maximum protection but highest cost")

        hedging_options.append(HedgeOption(
            name=f"NIFTY {label}",
            strategy="protective_put",
            strike=strike,
            strike_2=None,
            premium_per_share=round(bs.price, 2),
            total_cost=round(total_cost, 2),
            cost_as_pct=round(cost_pct, 2),
            annualized_cost_pct=round(annualized, 2),
            protection_level=protection,
            max_loss_hedged=round(max_loss, 2),
            days_to_expiry=days_to_expiry,
            lots=lots_full,
            notes=". ".join(notes) if notes else "",
        ))

    # 2. Bear put spread — buy near put, sell far put
    near_strike = round((nifty_spot * 0.97) / 50) * 50
    far_strike = round((nifty_spot * 0.90) / 50) * 50

    near_bs = price_option(nifty_spot, near_strike, T, risk_free_rate, volatility, "PE")
    far_bs = price_option(nifty_spot, far_strike, T, risk_free_rate, volatility, "PE")

    spread_cost = (near_bs.price - far_bs.price) * lot_size * lots_full
    spread_cost_pct = spread_cost / equity_value * 100 if equity_value > 0 else 0
    spread_annualized = spread_cost_pct * (365 / days_to_expiry)

    hedging_options.append(HedgeOption(
        name=f"NIFTY Bear Put Spread {near_strike}/{far_strike}",
        strategy="bear_put_spread",
        strike=near_strike,
        strike_2=far_strike,
        premium_per_share=round(near_bs.price - far_bs.price, 2),
        total_cost=round(spread_cost, 2),
        cost_as_pct=round(spread_cost_pct, 2),
        annualized_cost_pct=round(spread_annualized, 2),
        protection_level=f"Protects {far_strike}-{near_strike} range (-3% to -10%)",
        max_loss_hedged=round(equity_value * 0.10 + spread_cost, 2),
        days_to_expiry=days_to_expiry,
        lots=lots_full,
        notes="Cheaper than outright put. Capped protection but defined cost.",
    ))

    # 3. Zero-cost collar — sell OTM call + buy OTM put
    call_strike = round((nifty_spot * 1.05) / 50) * 50
    put_strike = round((nifty_spot * 0.95) / 50) * 50

    call_bs = price_option(nifty_spot, call_strike, T, risk_free_rate, volatility, "CE")
    put_bs_collar = price_option(nifty_spot, put_strike, T, risk_free_rate, volatility, "PE")

    collar_net = (call_bs.price - put_bs_collar.price) * lot_size * lots_full
    collar_cost_pct = abs(collar_net) / equity_value * 100 if equity_value > 0 else 0

    hedging_options.append(HedgeOption(
        name=f"NIFTY Collar {put_strike}/{call_strike}",
        strategy="collar",
        strike=put_strike,
        strike_2=call_strike,
        premium_per_share=round(call_bs.price - put_bs_collar.price, 2),
        total_cost=round(collar_net, 2),
        cost_as_pct=round(collar_cost_pct, 2),
        annualized_cost_pct=round(collar_cost_pct * (365 / days_to_expiry), 2),
        protection_level=f"-5% floor, +5% cap",
        max_loss_hedged=round(equity_value * 0.05 + abs(collar_net), 2),
        days_to_expiry=days_to_expiry,
        lots=lots_full,
        notes="Near zero-cost. Caps upside at +5% in exchange for -5% floor." if abs(collar_net) < equity_value * 0.01 else f"Net {'credit' if collar_net > 0 else 'debit'}: ₹{abs(collar_net):.0f}",
    ))

    # Summary
    summary_parts = [
        f"Portfolio: ₹{equity_value:,.0f} | Beta: {portfolio_beta:.2f}",
        f"Beta-adjusted exposure: ₹{beta_adjusted:,.0f}",
        f"NIFTY lots for full hedge: {lots_full} (₹{notional_per_lot * lots_full:,.0f} notional)",
    ]

    if equity_value > 0:
        cheapest = min(hedging_options, key=lambda h: h.annualized_cost_pct)
        summary_parts.append(
            f"Cheapest hedge: {cheapest.name} at {cheapest.annualized_cost_pct:.1f}% annualized"
        )

    return PortfolioHedgeAnalysis(
        portfolio_value=round(equity_value, 2),
        equity_value=round(equity_value, 2),
        beta=portfolio_beta,
        beta_adjusted_exposure=round(beta_adjusted, 2),
        hedge_notional=round(notional_per_lot * lots_full, 2),
        nifty_spot=nifty_spot,
        nifty_lot_size=lot_size,
        lots_to_hedge=lots_full,
        lots_partial_hedge=lots_partial,
        hedging_options=hedging_options,
        summary="\n".join(summary_parts),
    )


def covered_call_income_report(
    portfolio: StockPortfolio,
    days_to_expiry: int = 30,
    volatility: float = 0.25,
    risk_free_rate: float = 0.065,
    call_otm_pct: float = 0.05,
) -> dict:
    """Generate covered call income report for all F&O-eligible holdings.

    Shows potential monthly income from selling covered calls on each holding.

    Args:
        portfolio: Stock portfolio.
        days_to_expiry: Target DTE for calls.
        volatility: Assumed IV.
        risk_free_rate: Risk-free rate.
        call_otm_pct: How far OTM for calls.

    Returns:
        Report with per-stock and total income potential.
    """
    from diamond_options.integration.overlay import suggest_covered_calls

    stock_reports = []
    total_monthly_income = 0.0
    total_coverable_value = 0.0

    for holding in portfolio.fno_eligible:
        calls = suggest_covered_calls(
            holding,
            days_to_expiry=days_to_expiry,
            volatility=volatility,
            risk_free_rate=risk_free_rate,
            num_suggestions=1,
        )
        if not calls:
            continue

        best = calls[0]  # Most conservative (first OTM)
        total_monthly_income += best.total_premium
        total_coverable_value += holding.market_value

        stock_reports.append({
            "ticker": holding.ticker,
            "fno_symbol": holding.fno_symbol,
            "shares": holding.shares,
            "lot_size": best.lot_size,
            "lots_coverable": best.lots_coverable,
            "call_strike": best.strike,
            "premium_per_share": best.premium,
            "total_premium": best.total_premium,
            "annualized_yield_pct": best.annualized_yield_pct,
            "downside_protection_pct": best.downside_protection_pct,
        })

    monthly_yield = (
        total_monthly_income / total_coverable_value * 100
        if total_coverable_value > 0 else 0
    )
    annualized_yield = monthly_yield * (365 / days_to_expiry)

    return {
        "portfolio_value": portfolio.total_value,
        "fno_eligible_value": portfolio.fno_eligible_value,
        "fno_eligible_pct": portfolio.fno_eligible_pct,
        "total_monthly_income": round(total_monthly_income, 2),
        "monthly_yield_pct": round(monthly_yield, 2),
        "annualized_yield_pct": round(annualized_yield, 2),
        "stocks_with_calls": len(stock_reports),
        "details": stock_reports,
    }
