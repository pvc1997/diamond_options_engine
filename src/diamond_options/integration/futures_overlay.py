"""Futures overlay strategies for equity holdings.

Generates futures-based hedge, income, and comparison recommendations
for stocks held in the diamond_stock_engine portfolio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from diamond_options.integration.stock_bridge import StockHolding, StockPortfolio


@dataclass(frozen=True)
class StockFuturesHedge:
    """Hedge recommendation: short stock futures against long equity."""

    symbol: str
    fno_symbol: str
    shares: int
    lot_size: int
    lots_hedged: int
    shares_hedged: int  # lots_hedged * lot_size
    hedge_ratio: float  # shares_hedged / shares (1.0 = fully hedged)
    entry_price: float  # Current spot / futures price
    margin_required: float
    basis_cost: float  # Futures premium paid (cost of carry)
    annualized_carry_cost_pct: float
    breakeven_days: int  # Days the stock must fall to recover basis cost
    effectiveness_pct: float  # % of holdings hedged
    notes: str


@dataclass(frozen=True)
class IndexFuturesHedge:
    """Hedge recommendation: short index futures against equity portfolio."""

    portfolio_value: float
    beta: float
    beta_adjusted_exposure: float
    nifty_futures_price: float
    nifty_spot: float
    nifty_lot_size: int
    lots_full_hedge: int
    lots_partial_hedge: int
    margin_full: float
    margin_partial: float
    basis_cost: float
    annualized_carry_cost_pct: float
    hedge_effectiveness: float  # % of beta-adjusted exposure hedged
    notes: str


@dataclass(frozen=True)
class HedgeMethodComparison:
    """Comparison of a single hedging method."""

    name: str
    method: str  # "futures", "protective_put", "bear_spread", "collar"
    cost: float  # Total cost for the hedge
    annualized_cost_pct: float
    max_protection_pct: float  # Max downside protection (% of portfolio)
    margin_required: float
    complexity: str  # "simple", "moderate", "complex"
    rolling_cost_annual: float  # Estimated annual cost if rolled monthly
    pros: list[str]
    cons: list[str]


@dataclass(frozen=True)
class HedgeComparison:
    """Full comparison across futures and options hedging methods."""

    portfolio_value: float
    methods: list[HedgeMethodComparison]
    recommended: str  # Name of the recommended method
    rationale: str


@dataclass(frozen=True)
class FuturesIncomeEntry:
    """Cash-futures arbitrage income for a single stock."""

    symbol: str
    fno_symbol: str
    shares: int
    lot_size: int
    lots_available: int
    spot_price: float
    futures_price: float
    basis: float
    basis_pct: float
    annualized_yield_pct: float
    margin_required: float
    income_per_lot: float
    total_income: float
    days_to_expiry: int
    risk_level: str  # "low", "medium", "high"
    notes: str


@dataclass(frozen=True)
class FuturesIncomeReport:
    """Aggregate cash-futures arbitrage income report."""

    portfolio_value: float
    fno_eligible_value: float
    eligible_count: int
    entries: list[FuturesIncomeEntry]
    total_income: float
    avg_annualized_yield_pct: float
    total_margin_required: float
    summary: str


def suggest_stock_futures_hedge(
    holding: StockHolding,
    futures_price: float | None = None,
    spot: float | None = None,
    days_to_expiry: int = 20,
    margin_pct: float | None = None,
) -> StockFuturesHedge | None:
    """Suggest shorting stock futures to hedge a long equity position.

    Args:
        holding: Stock holding from the portfolio.
        futures_price: Current futures price (defaults to spot + 0.5% carry).
        spot: Current spot price (defaults to holding.current_price).
        days_to_expiry: DTE for the futures contract.
        margin_pct: SPAN margin % (auto-detected from universe if None).

    Returns:
        StockFuturesHedge or None if not enough shares for 1 lot.
    """
    from diamond_options.data.universe import get_lot_size, get_futures_margin_pct

    spot_price = spot or holding.current_price
    lot_size = get_lot_size(holding.fno_symbol)
    if lot_size == 0:
        return None

    lots = holding.shares // lot_size
    if lots == 0:
        return None

    if margin_pct is None:
        margin_pct = get_futures_margin_pct(holding.fno_symbol)

    # Default futures price: spot + estimated carry
    if futures_price is None:
        carry_pct = 0.065 * days_to_expiry / 365  # ~6.5% risk-free
        futures_price = spot_price * (1 + carry_pct)

    shares_hedged = lots * lot_size
    hedge_ratio = shares_hedged / holding.shares if holding.shares > 0 else 0
    effectiveness = hedge_ratio * 100

    notional = futures_price * shares_hedged
    margin_required = notional * margin_pct

    basis = futures_price - spot_price
    basis_pct = (basis / spot_price * 100) if spot_price > 0 else 0
    annualized_carry = (basis_pct / days_to_expiry * 365) if days_to_expiry > 0 else 0

    # Breakeven: how many days stock must fall by basis amount
    daily_carry = basis / days_to_expiry if days_to_expiry > 0 else 0
    breakeven_days = days_to_expiry  # Full carry period to break even

    notes_parts = []
    if hedge_ratio >= 0.95:
        notes_parts.append("Fully hedged — delta neutral")
    elif hedge_ratio >= 0.5:
        notes_parts.append(f"Partially hedged ({effectiveness:.0f}%)")
    else:
        notes_parts.append(f"Lightly hedged ({effectiveness:.0f}%) — consider adding more lots")

    if annualized_carry > 8:
        notes_parts.append(f"High carry cost ({annualized_carry:.1f}% ann.) — basis is rich")
    elif annualized_carry < 4:
        notes_parts.append(f"Low carry cost ({annualized_carry:.1f}% ann.) — favorable hedge")

    return StockFuturesHedge(
        symbol=holding.ticker,
        fno_symbol=holding.fno_symbol,
        shares=holding.shares,
        lot_size=lot_size,
        lots_hedged=lots,
        shares_hedged=shares_hedged,
        hedge_ratio=round(hedge_ratio, 4),
        entry_price=round(futures_price, 2),
        margin_required=round(margin_required, 2),
        basis_cost=round(basis * shares_hedged, 2),
        annualized_carry_cost_pct=round(annualized_carry, 2),
        breakeven_days=breakeven_days,
        effectiveness_pct=round(effectiveness, 2),
        notes=". ".join(notes_parts),
    )


def suggest_index_futures_hedge(
    portfolio: StockPortfolio,
    nifty_futures: float,
    nifty_spot: float = 22500.0,
    portfolio_beta: float = 1.0,
    days_to_expiry: int = 20,
    hedge_ratio: float = 1.0,
) -> IndexFuturesHedge:
    """Suggest shorting NIFTY futures to hedge systematic equity risk.

    Args:
        portfolio: Stock portfolio from the bridge.
        nifty_futures: Current NIFTY futures price.
        nifty_spot: Current NIFTY spot.
        portfolio_beta: Portfolio beta to NIFTY.
        days_to_expiry: DTE for futures.
        hedge_ratio: 1.0 = full hedge, 0.5 = half hedge.

    Returns:
        IndexFuturesHedge with lots and margin analysis.
    """
    from diamond_options.data.universe import INDEX_CONTRACTS, get_futures_margin_pct

    lot_size = INDEX_CONTRACTS["NIFTY"]["lot_size"]
    equity_value = portfolio.total_value
    beta_adjusted = equity_value * portfolio_beta

    notional_per_lot = nifty_futures * lot_size
    lots_full = max(1, round(beta_adjusted * hedge_ratio / notional_per_lot))
    lots_partial = max(1, round(beta_adjusted * 0.5 / notional_per_lot))

    margin_pct = get_futures_margin_pct("NIFTY")
    margin_full = lots_full * notional_per_lot * margin_pct
    margin_partial = lots_partial * notional_per_lot * margin_pct

    basis = nifty_futures - nifty_spot
    basis_pct = (basis / nifty_spot * 100) if nifty_spot > 0 else 0
    annualized_carry = (basis_pct / days_to_expiry * 365) if days_to_expiry > 0 else 0
    basis_cost = basis * lot_size * lots_full

    hedge_notional = lots_full * notional_per_lot
    hedge_effectiveness = (
        (hedge_notional / beta_adjusted * 100) if beta_adjusted > 0 else 0
    )

    notes_parts = [
        f"Portfolio: ₹{equity_value:,.0f} | Beta: {portfolio_beta:.2f}",
        f"Beta-adjusted exposure: ₹{beta_adjusted:,.0f}",
        f"Hedge: {lots_full} lots NIFTY futures (₹{hedge_notional:,.0f} notional)",
    ]
    if annualized_carry > 8:
        notes_parts.append(f"High carry cost ({annualized_carry:.1f}% ann.) — consider options instead")
    else:
        notes_parts.append(f"Carry cost: {annualized_carry:.1f}% annualized")

    return IndexFuturesHedge(
        portfolio_value=round(equity_value, 2),
        beta=portfolio_beta,
        beta_adjusted_exposure=round(beta_adjusted, 2),
        nifty_futures_price=round(nifty_futures, 2),
        nifty_spot=round(nifty_spot, 2),
        nifty_lot_size=lot_size,
        lots_full_hedge=lots_full,
        lots_partial_hedge=lots_partial,
        margin_full=round(margin_full, 2),
        margin_partial=round(margin_partial, 2),
        basis_cost=round(basis_cost, 2),
        annualized_carry_cost_pct=round(annualized_carry, 2),
        hedge_effectiveness=round(hedge_effectiveness, 2),
        notes="\n".join(notes_parts),
    )


def compare_hedge_methods(
    portfolio: StockPortfolio,
    nifty_spot: float = 22500.0,
    nifty_futures: float = 22600.0,
    portfolio_beta: float = 1.0,
    days_to_expiry: int = 30,
    volatility: float = 0.13,
    risk_free_rate: float = 0.065,
) -> HedgeComparison:
    """Compare futures vs options hedging for the portfolio.

    Args:
        portfolio: Stock portfolio.
        nifty_spot: Current NIFTY spot.
        nifty_futures: Current NIFTY futures price.
        portfolio_beta: Portfolio beta.
        days_to_expiry: Target hedge DTE.
        volatility: NIFTY IV estimate.
        risk_free_rate: Risk-free rate.

    Returns:
        HedgeComparison with ranked methods.
    """
    from diamond_options.pricing.black_scholes import price_option
    from diamond_options.data.universe import INDEX_CONTRACTS, get_futures_margin_pct

    lot_size = INDEX_CONTRACTS["NIFTY"]["lot_size"]
    equity_value = portfolio.total_value
    beta_adjusted = equity_value * portfolio_beta

    notional_per_lot = nifty_futures * lot_size
    lots = max(1, round(beta_adjusted / notional_per_lot))
    T = days_to_expiry / 365.0

    margin_pct = get_futures_margin_pct("NIFTY")
    methods: list[HedgeMethodComparison] = []

    # 1. Short NIFTY Futures
    basis = nifty_futures - nifty_spot
    futures_carry = basis * lot_size * lots
    futures_annualized = (
        (basis / nifty_spot * 365 / days_to_expiry * 100) if days_to_expiry > 0 else 0
    )
    futures_margin = lots * notional_per_lot * margin_pct
    futures_rolling = futures_carry * (365 / days_to_expiry) if days_to_expiry > 0 else 0

    methods.append(HedgeMethodComparison(
        name="Short NIFTY Futures",
        method="futures",
        cost=round(futures_carry, 2),
        annualized_cost_pct=round(futures_annualized, 2),
        max_protection_pct=100.0,
        margin_required=round(futures_margin, 2),
        complexity="simple",
        rolling_cost_annual=round(futures_rolling, 2),
        pros=["Full downside protection", "Simple single instrument", "No premium decay"],
        cons=["Caps all upside", "Margin intensive", "Basis risk on rolls"],
    ))

    # 2. Protective Put (5% OTM)
    put_strike = round(nifty_spot * 0.95 / 50) * 50
    put_bs = price_option(nifty_spot, put_strike, T, risk_free_rate, volatility, "PE")
    put_cost = put_bs.price * lot_size * lots
    put_annualized = (put_cost / equity_value * 365 / days_to_expiry * 100) if equity_value > 0 and days_to_expiry > 0 else 0
    put_rolling = put_cost * (365 / days_to_expiry) if days_to_expiry > 0 else 0

    methods.append(HedgeMethodComparison(
        name=f"NIFTY {put_strike} Put",
        method="protective_put",
        cost=round(put_cost, 2),
        annualized_cost_pct=round(put_annualized, 2),
        max_protection_pct=round((1 - put_strike / nifty_spot) * 100, 1),
        margin_required=round(put_cost, 2),  # Buy-side only
        complexity="simple",
        rolling_cost_annual=round(put_rolling, 2),
        pros=["Unlimited upside preserved", "Defined max cost", "No margin pressure"],
        cons=["Premium lost if market stays flat/up", "Expensive if IV high", "Decays with time"],
    ))

    # 3. Bear Put Spread (97% / 90%)
    near_strike = round(nifty_spot * 0.97 / 50) * 50
    far_strike = round(nifty_spot * 0.90 / 50) * 50
    near_bs = price_option(nifty_spot, near_strike, T, risk_free_rate, volatility, "PE")
    far_bs = price_option(nifty_spot, far_strike, T, risk_free_rate, volatility, "PE")
    spread_cost = (near_bs.price - far_bs.price) * lot_size * lots
    spread_annualized = (spread_cost / equity_value * 365 / days_to_expiry * 100) if equity_value > 0 and days_to_expiry > 0 else 0

    methods.append(HedgeMethodComparison(
        name=f"NIFTY Bear Spread {near_strike}/{far_strike}",
        method="bear_spread",
        cost=round(spread_cost, 2),
        annualized_cost_pct=round(spread_annualized, 2),
        max_protection_pct=round((1 - far_strike / nifty_spot) * 100, 1),
        margin_required=round(spread_cost, 2),
        complexity="moderate",
        rolling_cost_annual=round(spread_cost * (365 / days_to_expiry), 2) if days_to_expiry > 0 else 0,
        pros=["Cheaper than outright put", "Defined risk", "No margin pressure"],
        cons=["Capped protection (floor at far strike)", "Two legs to manage", "Wider bid-ask"],
    ))

    # 4. Collar (sell 5% OTM call, buy 5% OTM put)
    call_strike = round(nifty_spot * 1.05 / 50) * 50
    collar_put_strike = put_strike  # Same as protective put
    call_bs = price_option(nifty_spot, call_strike, T, risk_free_rate, volatility, "CE")
    collar_put_bs = price_option(nifty_spot, collar_put_strike, T, risk_free_rate, volatility, "PE")
    collar_net = (collar_put_bs.price - call_bs.price) * lot_size * lots
    collar_annualized = (abs(collar_net) / equity_value * 365 / days_to_expiry * 100) if equity_value > 0 and days_to_expiry > 0 else 0

    methods.append(HedgeMethodComparison(
        name=f"NIFTY Collar {collar_put_strike}/{call_strike}",
        method="collar",
        cost=round(collar_net, 2),
        annualized_cost_pct=round(collar_annualized, 2),
        max_protection_pct=round((1 - collar_put_strike / nifty_spot) * 100, 1),
        margin_required=round(abs(collar_net), 2),
        complexity="moderate",
        rolling_cost_annual=round(abs(collar_net) * (365 / days_to_expiry), 2) if days_to_expiry > 0 else 0,
        pros=["Near zero cost", "Defined risk range", "Good for sideways markets"],
        cons=["Caps upside", "Two legs to manage", "Miss out on rallies"],
    ))

    # Recommendation logic
    if equity_value < 500000:
        recommended = methods[0].name  # Futures simplest for small portfolios
        rationale = "Futures hedge is simplest for smaller portfolios — single instrument, no premium decay."
    elif volatility > 0.20:
        recommended = methods[0].name  # Futures when IV is high
        rationale = "Options are expensive with elevated IV. Futures hedge avoids premium decay."
    elif volatility < 0.12:
        recommended = methods[1].name  # Puts when IV is low
        rationale = "Low IV makes puts cheap. Protective put preserves unlimited upside."
    else:
        recommended = methods[3].name  # Collar for normal conditions
        rationale = "Collar provides near zero-cost protection in normal volatility."

    return HedgeComparison(
        portfolio_value=round(equity_value, 2),
        methods=methods,
        recommended=recommended,
        rationale=rationale,
    )


def futures_income_from_holdings(
    portfolio: StockPortfolio,
    days_to_expiry: int = 20,
    futures_premiums: dict[str, float] | None = None,
    margin_pct_override: float | None = None,
) -> FuturesIncomeReport:
    """Generate cash-futures arbitrage income report for F&O-eligible holdings.

    For stocks in contango (futures > spot), selling stock futures while
    holding the stock earns the basis as risk-free income.

    Args:
        portfolio: Stock portfolio from the bridge.
        days_to_expiry: DTE for futures contracts.
        futures_premiums: {symbol: futures_price} dict. If None, estimates carry.
        margin_pct_override: Override margin % for all symbols.

    Returns:
        FuturesIncomeReport with per-stock income analysis.
    """
    from diamond_options.data.universe import get_lot_size, get_futures_margin_pct

    premiums = futures_premiums or {}
    entries: list[FuturesIncomeEntry] = []
    total_income = 0.0
    total_margin = 0.0
    total_eligible_value = 0.0

    for holding in portfolio.fno_eligible:
        lot_size = get_lot_size(holding.fno_symbol)
        if lot_size == 0:
            continue

        lots = holding.shares // lot_size
        if lots == 0:
            continue

        spot = holding.current_price
        if spot <= 0:
            continue

        # Futures price: use provided or estimate with carry
        if holding.fno_symbol in premiums:
            futures_price = premiums[holding.fno_symbol]
        else:
            carry_pct = 0.065 * days_to_expiry / 365
            futures_price = spot * (1 + carry_pct)

        basis = futures_price - spot
        basis_pct = (basis / spot * 100) if spot > 0 else 0
        annualized_yield = (basis_pct / days_to_expiry * 365) if days_to_expiry > 0 else 0

        if margin_pct_override is not None:
            margin_pct = margin_pct_override
        else:
            margin_pct = get_futures_margin_pct(holding.fno_symbol)

        shares_used = lots * lot_size
        income_per_lot = basis * lot_size
        income_total = basis * shares_used
        margin_required = futures_price * shares_used * margin_pct

        # Risk assessment
        if annualized_yield < 4:
            risk_level = "low"
        elif annualized_yield < 8:
            risk_level = "medium"
        else:
            risk_level = "high"  # Basis may revert

        notes_parts = []
        if basis < 0:
            notes_parts.append("Backwardation — no arb income (negative basis)")
            risk_level = "high"
        elif annualized_yield > 10:
            notes_parts.append(f"Rich basis ({annualized_yield:.1f}% ann.) — may compress")
        else:
            notes_parts.append(f"Normal carry ({annualized_yield:.1f}% ann.)")

        entries.append(FuturesIncomeEntry(
            symbol=holding.ticker,
            fno_symbol=holding.fno_symbol,
            shares=holding.shares,
            lot_size=lot_size,
            lots_available=lots,
            spot_price=round(spot, 2),
            futures_price=round(futures_price, 2),
            basis=round(basis, 2),
            basis_pct=round(basis_pct, 4),
            annualized_yield_pct=round(annualized_yield, 2),
            margin_required=round(margin_required, 2),
            income_per_lot=round(income_per_lot, 2),
            total_income=round(income_total, 2),
            days_to_expiry=days_to_expiry,
            risk_level=risk_level,
            notes=". ".join(notes_parts),
        ))

        if basis > 0:
            total_income += income_total
            total_margin += margin_required
            total_eligible_value += holding.market_value

    avg_yield = 0.0
    if total_eligible_value > 0 and days_to_expiry > 0:
        avg_yield = (total_income / total_eligible_value * 365 / days_to_expiry * 100)

    summary_parts = [
        f"Eligible holdings: {len(entries)} stocks",
        f"Total income: ₹{total_income:,.0f} for {days_to_expiry} days",
        f"Avg annualized yield: {avg_yield:.1f}%",
        f"Margin needed: ₹{total_margin:,.0f}",
    ]

    return FuturesIncomeReport(
        portfolio_value=round(portfolio.total_value, 2),
        fno_eligible_value=round(portfolio.fno_eligible_value, 2),
        eligible_count=len(entries),
        entries=entries,
        total_income=round(total_income, 2),
        avg_annualized_yield_pct=round(avg_yield, 2),
        total_margin_required=round(total_margin, 2),
        summary="\n".join(summary_parts),
    )
