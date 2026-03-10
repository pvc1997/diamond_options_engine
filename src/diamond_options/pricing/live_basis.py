"""Live basis analysis from Kite market quotes.

Computes real-time basis, mispricing, and rollover analysis
from Kite MCP quote data for futures positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class LiveBasisResult:
    """Real-time basis analysis from market quotes."""

    symbol: str
    spot: float
    futures: float
    basis: float  # futures - spot (₹)
    basis_pct: float  # basis as % of spot
    annualized_basis: float  # annualized cost of carry (%)
    fair_value: float  # theoretical futures price
    mispricing: float  # futures - fair_value (₹)
    mispricing_pct: float  # mispricing as % of spot
    days_to_expiry: int
    signal: str  # "rich", "cheap", "fair"
    contango: bool  # True if futures > spot


@dataclass(frozen=True)
class RolloverAnalysis:
    """Live rollover cost analysis from near and next month quotes."""

    symbol: str
    near_price: float
    near_expiry_dte: int
    next_price: float
    next_expiry_dte: int
    calendar_spread: float  # next - near (₹)
    calendar_spread_pct: float  # spread as % of near
    roll_cost_pct: float  # cost to roll as % of position
    annualized_roll_cost: float  # annualized roll cost (%)
    recommendation: str  # "roll_now", "wait", "close"
    rationale: str


def live_basis_from_kite(
    symbol: str,
    spot_price: float,
    futures_price: float,
    days_to_expiry: int,
    risk_free_rate: float = 0.065,
    dividend_yield: float = 0.0,
) -> LiveBasisResult:
    """Compute real-time basis analysis from spot and futures prices.

    Args:
        symbol: F&O symbol (e.g., "NIFTY", "RELIANCE").
        spot_price: Current spot/underlying price.
        futures_price: Current futures LTP.
        days_to_expiry: Days to futures expiry.
        risk_free_rate: Annualized risk-free rate.
        dividend_yield: Annualized dividend yield.

    Returns:
        LiveBasisResult with basis, mispricing, and signal.
    """
    import math

    basis = futures_price - spot_price
    basis_pct = (basis / spot_price * 100) if spot_price > 0 else 0.0
    annualized = (basis_pct / days_to_expiry * 365) if days_to_expiry > 0 else 0.0

    T = days_to_expiry / 365.0
    fair_value = spot_price * math.exp((risk_free_rate - dividend_yield) * T)
    mispricing = futures_price - fair_value
    mispricing_pct = (mispricing / spot_price * 100) if spot_price > 0 else 0.0

    # Signal: rich if annualized basis > 8%, cheap if < 4%
    if annualized > 8.0:
        signal = "rich"
    elif annualized < 4.0:
        signal = "cheap"
    else:
        signal = "fair"

    return LiveBasisResult(
        symbol=symbol.upper(),
        spot=round(spot_price, 2),
        futures=round(futures_price, 2),
        basis=round(basis, 2),
        basis_pct=round(basis_pct, 4),
        annualized_basis=round(annualized, 2),
        fair_value=round(fair_value, 2),
        mispricing=round(mispricing, 2),
        mispricing_pct=round(mispricing_pct, 4),
        days_to_expiry=days_to_expiry,
        signal=signal,
        contango=basis > 0,
    )


def live_basis_scan(
    quotes: list[dict],
    risk_free_rate: float = 0.065,
) -> list[LiveBasisResult]:
    """Batch scan multiple symbols for basis opportunities.

    Args:
        quotes: List of dicts with keys:
            symbol, spot_price, futures_price, days_to_expiry,
            dividend_yield (optional, default 0).
        risk_free_rate: Annualized risk-free rate.

    Returns:
        List of LiveBasisResult sorted by signal priority (rich/cheap first).
    """
    results = []
    for q in quotes:
        symbol = q.get("symbol", "")
        spot = q.get("spot_price", 0)
        futures = q.get("futures_price", 0)
        dte = q.get("days_to_expiry", 20)
        div_yield = q.get("dividend_yield", 0.0)

        if spot <= 0 or futures <= 0:
            continue

        result = live_basis_from_kite(
            symbol, spot, futures, dte, risk_free_rate, div_yield,
        )
        results.append(result)

    # Sort: rich and cheap first, then fair
    signal_order = {"rich": 0, "cheap": 1, "fair": 2}
    results.sort(key=lambda r: (signal_order.get(r.signal, 2), -abs(r.annualized_basis)))
    return results


def live_rollover_analysis(
    symbol: str,
    near_price: float,
    near_dte: int,
    next_price: float,
    next_dte: int,
    spot_price: float = 0.0,
) -> RolloverAnalysis:
    """Analyze rollover cost from near to next month contract.

    Args:
        symbol: F&O symbol.
        near_price: Current (near-month) futures price.
        near_dte: Days to near-month expiry.
        next_price: Next-month futures price.
        next_dte: Days to next-month expiry.
        spot_price: Current spot price (for context, optional).

    Returns:
        RolloverAnalysis with spread, cost, and recommendation.
    """
    spread = next_price - near_price
    spread_pct = (spread / near_price * 100) if near_price > 0 else 0.0

    # Roll cost: what you pay to roll (spread)
    roll_cost_pct = spread_pct

    # Annualize based on days between expiries
    days_between = next_dte - near_dte
    if days_between > 0:
        annualized_roll = (spread_pct / days_between * 365)
    else:
        annualized_roll = 0.0

    # Recommendation logic
    rationale_parts = []

    if near_dte <= 1:
        recommendation = "roll_now"
        rationale_parts.append("Expiry imminent — must roll or close today")
    elif near_dte <= 3:
        if abs(spread_pct) < 1.0:
            recommendation = "roll_now"
            rationale_parts.append(f"Expiry in {near_dte} days, spread reasonable ({spread_pct:.2f}%)")
        else:
            recommendation = "roll_now"
            rationale_parts.append(f"Expiry in {near_dte} days, spread wide ({spread_pct:.2f}%) but must roll")
    elif near_dte <= 7:
        if abs(spread_pct) < 0.5:
            recommendation = "roll_now"
            rationale_parts.append(f"Good spread ({spread_pct:.2f}%) — roll early for better fills")
        elif abs(spread_pct) < 1.0:
            recommendation = "wait"
            rationale_parts.append(f"Spread moderate ({spread_pct:.2f}%) — can wait 1-2 days for compression")
        else:
            recommendation = "wait"
            rationale_parts.append(f"Spread wide ({spread_pct:.2f}%) — wait for better entry")
    else:
        recommendation = "wait"
        rationale_parts.append(f"{near_dte} days to expiry — no urgency to roll")

    if spread < 0:
        rationale_parts.append("Backwardation — paid to roll (favorable)")
    elif annualized_roll > 10:
        rationale_parts.append(f"High roll cost ({annualized_roll:.1f}% ann.) — consider reducing position")

    return RolloverAnalysis(
        symbol=symbol.upper(),
        near_price=round(near_price, 2),
        near_expiry_dte=near_dte,
        next_price=round(next_price, 2),
        next_expiry_dte=next_dte,
        calendar_spread=round(spread, 2),
        calendar_spread_pct=round(spread_pct, 4),
        roll_cost_pct=round(roll_cost_pct, 4),
        annualized_roll_cost=round(annualized_roll, 2),
        recommendation=recommendation,
        rationale=". ".join(rationale_parts),
    )
