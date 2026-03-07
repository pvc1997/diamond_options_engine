"""Options overlay strategies for equity holdings.

Generates covered call, protective put, and collar recommendations
for stocks held in the diamond_stock_engine portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass

from diamond_options.integration.stock_bridge import StockHolding


@dataclass(frozen=True)
class CoveredCallSetup:
    """Covered call recommendation for a stock holding."""
    ticker: str
    fno_symbol: str
    shares_held: int
    lot_size: int
    lots_coverable: int         # Max lots from shares held
    strike: float
    premium: float              # Per share
    total_premium: float        # premium * lot_size * lots
    annualized_yield_pct: float # Annualized premium yield
    downside_protection_pct: float  # Premium as % of stock price
    upside_cap: float           # Max gain per share (strike - current + premium)
    breakeven: float            # current_price - premium
    delta: float
    days_to_expiry: int
    moneyness: str              # OTM, ATM, ITM
    notes: str


@dataclass(frozen=True)
class ProtectivePutSetup:
    """Protective put recommendation for a stock holding."""
    ticker: str
    fno_symbol: str
    shares_held: int
    lot_size: int
    lots_needed: int
    strike: float
    premium: float              # Per share
    total_cost: float           # premium * lot_size * lots
    cost_as_pct_of_holding: float
    annualized_cost_pct: float
    max_loss_per_share: float   # current_price - strike + premium
    max_loss_total: float
    protection_level_pct: float # How far OTM the put is
    delta: float
    days_to_expiry: int
    notes: str


@dataclass(frozen=True)
class CollarSetup:
    """Collar (covered call + protective put) for a stock holding."""
    ticker: str
    fno_symbol: str
    shares_held: int
    lot_size: int
    lots: int
    call_strike: float
    call_premium: float
    put_strike: float
    put_premium: float
    net_premium: float          # call_premium - put_premium (positive = credit)
    net_cost: float             # Total cost/credit for the collar
    max_gain_per_share: float   # call_strike - current + net_premium
    max_loss_per_share: float   # current - put_strike - net_premium
    upside_cap_pct: float       # Max gain as %
    downside_floor_pct: float   # Max loss as %
    days_to_expiry: int
    notes: str


def suggest_covered_calls(
    holding: StockHolding,
    spot: float | None = None,
    days_to_expiry: int = 30,
    volatility: float = 0.25,
    risk_free_rate: float = 0.065,
    num_suggestions: int = 3,
) -> list[CoveredCallSetup]:
    """Suggest covered call strikes for a stock holding.

    Generates OTM covered call options at different strike distances.
    Requires holding enough shares to cover at least 1 lot.

    Args:
        holding: Stock holding from the portfolio.
        spot: Current spot price (uses holding.current_price if None).
        days_to_expiry: Target DTE.
        volatility: Estimated IV for the stock.
        risk_free_rate: Risk-free rate.
        num_suggestions: Number of strikes to suggest.

    Returns:
        List of CoveredCallSetup sorted by yield (conservative to aggressive).
    """
    from diamond_options.data.universe import get_lot_size
    from diamond_options.pricing.black_scholes import price_option
    from diamond_options.pricing.greeks import calculate_greeks

    spot_price = spot or holding.current_price
    lot_size = get_lot_size(holding.fno_symbol)
    if lot_size == 0:
        return []

    lots_coverable = holding.shares // lot_size
    if lots_coverable == 0:
        return []

    T = days_to_expiry / 365.0

    # Generate OTM strikes at 2%, 5%, 8% above spot
    otm_pcts = [0.02, 0.05, 0.08, 0.10, 0.12][:num_suggestions]

    setups = []
    for pct in otm_pcts:
        strike_raw = spot_price * (1 + pct)
        # Round to nearest tick (most stock options have 2.5 or 5 rupee ticks)
        tick = 2.5 if spot_price < 500 else 5.0 if spot_price < 2000 else 10.0
        strike = round(strike_raw / tick) * tick

        bs = price_option(spot_price, strike, T, risk_free_rate, volatility, "CE")
        greeks = calculate_greeks(spot_price, strike, T, risk_free_rate, volatility, "CE")

        total_premium = bs.price * lot_size * lots_coverable
        annualized_yield = (bs.price / spot_price) * (365 / days_to_expiry) * 100
        downside_protection = bs.price / spot_price * 100
        upside_cap = strike - spot_price + bs.price
        breakeven = spot_price - bs.price

        moneyness = "ATM" if abs(strike - spot_price) / spot_price < 0.01 else (
            "OTM" if strike > spot_price else "ITM"
        )

        notes_parts = []
        if pct <= 0.03:
            notes_parts.append("Aggressive — high premium but caps upside early")
        elif pct <= 0.06:
            notes_parts.append("Balanced — good premium with room for appreciation")
        else:
            notes_parts.append("Conservative — low premium but preserves most upside")

        if annualized_yield > 20:
            notes_parts.append(f"Excellent yield ({annualized_yield:.1f}% annualized)")

        setups.append(CoveredCallSetup(
            ticker=holding.ticker,
            fno_symbol=holding.fno_symbol,
            shares_held=holding.shares,
            lot_size=lot_size,
            lots_coverable=lots_coverable,
            strike=strike,
            premium=round(bs.price, 2),
            total_premium=round(total_premium, 2),
            annualized_yield_pct=round(annualized_yield, 2),
            downside_protection_pct=round(downside_protection, 2),
            upside_cap=round(upside_cap, 2),
            breakeven=round(breakeven, 2),
            delta=greeks.delta,
            days_to_expiry=days_to_expiry,
            moneyness=moneyness,
            notes=". ".join(notes_parts),
        ))

    return setups


def suggest_protective_puts(
    holding: StockHolding,
    spot: float | None = None,
    days_to_expiry: int = 30,
    volatility: float = 0.25,
    risk_free_rate: float = 0.065,
    num_suggestions: int = 3,
) -> list[ProtectivePutSetup]:
    """Suggest protective put strikes for a stock holding.

    Args:
        holding: Stock holding.
        spot: Current price.
        days_to_expiry: Target DTE.
        volatility: IV estimate.
        risk_free_rate: Risk-free rate.
        num_suggestions: Number of strikes.

    Returns:
        List of ProtectivePutSetup sorted by cost (cheap to expensive).
    """
    from diamond_options.data.universe import get_lot_size
    from diamond_options.pricing.black_scholes import price_option
    from diamond_options.pricing.greeks import calculate_greeks

    spot_price = spot or holding.current_price
    lot_size = get_lot_size(holding.fno_symbol)
    if lot_size == 0:
        return []

    lots_needed = max(1, holding.shares // lot_size)
    T = days_to_expiry / 365.0

    # OTM put strikes at 3%, 5%, 10% below spot
    otm_pcts = [0.03, 0.05, 0.08, 0.10, 0.15][:num_suggestions]

    setups = []
    for pct in otm_pcts:
        strike_raw = spot_price * (1 - pct)
        tick = 2.5 if spot_price < 500 else 5.0 if spot_price < 2000 else 10.0
        strike = round(strike_raw / tick) * tick

        bs = price_option(spot_price, strike, T, risk_free_rate, volatility, "PE")
        greeks = calculate_greeks(spot_price, strike, T, risk_free_rate, volatility, "PE")

        total_cost = bs.price * lot_size * lots_needed
        cost_pct = total_cost / holding.market_value * 100 if holding.market_value > 0 else 0
        annualized_cost = cost_pct * (365 / days_to_expiry)
        max_loss_per_share = spot_price - strike + bs.price
        max_loss_total = max_loss_per_share * lot_size * lots_needed

        notes_parts = []
        if pct <= 0.05:
            notes_parts.append("Near protection — expensive but tight floor")
        elif pct <= 0.10:
            notes_parts.append("Moderate protection — balanced cost and coverage")
        else:
            notes_parts.append("Disaster insurance — cheap but only for large crashes")

        if annualized_cost < 5:
            notes_parts.append(f"Low cost ({annualized_cost:.1f}% annualized)")
        elif annualized_cost > 15:
            notes_parts.append(f"Expensive ({annualized_cost:.1f}% annualized) — consider collar")

        setups.append(ProtectivePutSetup(
            ticker=holding.ticker,
            fno_symbol=holding.fno_symbol,
            shares_held=holding.shares,
            lot_size=lot_size,
            lots_needed=lots_needed,
            strike=strike,
            premium=round(bs.price, 2),
            total_cost=round(total_cost, 2),
            cost_as_pct_of_holding=round(cost_pct, 2),
            annualized_cost_pct=round(annualized_cost, 2),
            max_loss_per_share=round(max_loss_per_share, 2),
            max_loss_total=round(max_loss_total, 2),
            protection_level_pct=round(pct * 100, 1),
            delta=greeks.delta,
            days_to_expiry=days_to_expiry,
            notes=". ".join(notes_parts),
        ))

    return setups


def suggest_collar(
    holding: StockHolding,
    spot: float | None = None,
    days_to_expiry: int = 30,
    volatility: float = 0.25,
    risk_free_rate: float = 0.065,
    call_otm_pct: float = 0.05,
    put_otm_pct: float = 0.05,
) -> CollarSetup | None:
    """Suggest a collar (sell call + buy put) for a stock holding.

    A zero-cost or near-zero-cost collar caps upside and floors downside.

    Args:
        holding: Stock holding.
        spot: Current price.
        days_to_expiry: Target DTE.
        volatility: IV estimate.
        risk_free_rate: Risk-free rate.
        call_otm_pct: How far OTM for the call (default 5%).
        put_otm_pct: How far OTM for the put (default 5%).

    Returns:
        CollarSetup or None if not enough shares.
    """
    from diamond_options.data.universe import get_lot_size
    from diamond_options.pricing.black_scholes import price_option

    spot_price = spot or holding.current_price
    lot_size = get_lot_size(holding.fno_symbol)
    if lot_size == 0:
        return None

    lots = holding.shares // lot_size
    if lots == 0:
        return None

    T = days_to_expiry / 365.0
    tick = 2.5 if spot_price < 500 else 5.0 if spot_price < 2000 else 10.0

    call_strike = round(spot_price * (1 + call_otm_pct) / tick) * tick
    put_strike = round(spot_price * (1 - put_otm_pct) / tick) * tick

    call_bs = price_option(spot_price, call_strike, T, risk_free_rate, volatility, "CE")
    put_bs = price_option(spot_price, put_strike, T, risk_free_rate, volatility, "PE")

    net_premium = call_bs.price - put_bs.price  # Positive = credit
    net_cost = net_premium * lot_size * lots  # Positive = receive cash

    max_gain = call_strike - spot_price + net_premium
    max_loss = spot_price - put_strike - net_premium

    upside_cap_pct = max_gain / spot_price * 100
    downside_floor_pct = max_loss / spot_price * 100

    notes_parts = []
    if net_premium > 0:
        notes_parts.append(f"Credit collar — receive ₹{abs(net_cost):.0f}")
    elif abs(net_premium) < 0.5:
        notes_parts.append("Near zero-cost collar")
    else:
        notes_parts.append(f"Debit collar — pay ₹{abs(net_cost):.0f}")

    notes_parts.append(
        f"Range: {put_strike:.0f}–{call_strike:.0f} "
        f"(max loss {downside_floor_pct:.1f}%, max gain {upside_cap_pct:.1f}%)"
    )

    return CollarSetup(
        ticker=holding.ticker,
        fno_symbol=holding.fno_symbol,
        shares_held=holding.shares,
        lot_size=lot_size,
        lots=lots,
        call_strike=call_strike,
        call_premium=round(call_bs.price, 2),
        put_strike=put_strike,
        put_premium=round(put_bs.price, 2),
        net_premium=round(net_premium, 2),
        net_cost=round(net_cost, 2),
        max_gain_per_share=round(max_gain, 2),
        max_loss_per_share=round(max_loss, 2),
        upside_cap_pct=round(upside_cap_pct, 2),
        downside_floor_pct=round(downside_floor_pct, 2),
        days_to_expiry=days_to_expiry,
        notes=". ".join(notes_parts),
    )
