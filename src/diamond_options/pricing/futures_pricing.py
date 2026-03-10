"""Futures pricing via cost-of-carry model.

Provides theoretical fair value, mispricing detection, implied interest rate,
and contango/backwardation classification for Indian equity futures.

The cost-of-carry model:
    F = S × e^((r - q) × T)

where:
    F = Futures price
    S = Spot price
    r = Risk-free rate (annualized)
    q = Continuous dividend yield (annualized)
    T = Time to expiry in years

References:
    - Hull, J. (2018). "Options, Futures, and Other Derivatives" (10th ed.), Ch. 5
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FuturesPricingResult:
    """Result of futures fair value calculation."""

    fair_value: float  # Theoretical futures price
    market_price: float  # Observed market price
    mispricing: float  # market_price - fair_value (₹)
    mispricing_pct: float  # Mispricing as % of spot
    implied_rate: float  # Rate implied by observed price (annualized)
    carry_cost: float  # Fair value - spot (₹), the cost of carry
    carry_cost_pct: float  # Carry cost as % of spot
    is_overpriced: bool  # Market price above fair value
    is_underpriced: bool  # Market price below fair value


def theoretical_futures_price(
    spot: float,
    r: float,
    T: float,
    q: float = 0.0,
) -> float:
    """Calculate theoretical futures price using cost-of-carry.

    F = S × e^((r - q) × T)

    Args:
        spot: Current spot price.
        r: Risk-free rate (annualized, e.g., 0.065 for 6.5%).
        T: Time to expiry in years (days / 365).
        q: Continuous dividend yield (annualized).

    Returns:
        Theoretical futures price.
    """
    if spot <= 0 or T <= 0:
        return spot
    return spot * math.exp((r - q) * T)


def fair_value(
    spot: float,
    r: float,
    T: float,
    q: float = 0.0,
) -> float:
    """Alias for theoretical_futures_price."""
    return theoretical_futures_price(spot, r, T, q)


def futures_mispricing(
    spot: float,
    futures_price: float,
    r: float,
    T: float,
    q: float = 0.0,
    threshold_pct: float = 0.1,
) -> FuturesPricingResult:
    """Compare market futures price to theoretical fair value.

    Args:
        spot: Current spot price.
        futures_price: Observed market futures price.
        r: Risk-free rate (annualized).
        T: Time to expiry in years.
        q: Continuous dividend yield (annualized).
        threshold_pct: Mispricing threshold for over/underpriced (%).

    Returns:
        FuturesPricingResult with mispricing analysis.
    """
    fv = theoretical_futures_price(spot, r, T, q)
    mispricing = futures_price - fv
    mispricing_pct = (mispricing / spot * 100) if spot > 0 else 0.0
    carry = fv - spot
    carry_pct = (carry / spot * 100) if spot > 0 else 0.0

    # Implied rate from observed price
    imp_rate = implied_interest_rate(spot, futures_price, T, q)

    return FuturesPricingResult(
        fair_value=round(fv, 2),
        market_price=futures_price,
        mispricing=round(mispricing, 2),
        mispricing_pct=round(mispricing_pct, 4),
        implied_rate=round(imp_rate, 6),
        carry_cost=round(carry, 2),
        carry_cost_pct=round(carry_pct, 4),
        is_overpriced=mispricing_pct > threshold_pct,
        is_underpriced=mispricing_pct < -threshold_pct,
    )


def implied_interest_rate(
    spot: float,
    futures_price: float,
    T: float,
    q: float = 0.0,
) -> float:
    """Back-solve the risk-free rate implied by futures pricing.

    From F = S × e^((r-q)×T):
        r = ln(F/S) / T + q

    Args:
        spot: Current spot price.
        futures_price: Observed futures price.
        T: Time to expiry in years.
        q: Continuous dividend yield.

    Returns:
        Implied annualized risk-free rate.
    """
    if spot <= 0 or futures_price <= 0 or T <= 0:
        return 0.0
    return math.log(futures_price / spot) / T + q


def implied_dividend_yield(
    spot: float,
    futures_price: float,
    r: float,
    T: float,
) -> float:
    """Back-solve the dividend yield implied by futures pricing.

    From F = S × e^((r-q)×T):
        q = r - ln(F/S) / T

    Args:
        spot: Current spot price.
        futures_price: Observed futures price.
        r: Risk-free rate (annualized).
        T: Time to expiry in years.

    Returns:
        Implied annualized continuous dividend yield.
    """
    if spot <= 0 or futures_price <= 0 or T <= 0:
        return 0.0
    return r - math.log(futures_price / spot) / T


def contango_or_backwardation(
    near_price: float,
    far_price: float,
) -> str:
    """Classify the relationship between near and far month futures.

    Args:
        near_price: Near-month futures price.
        far_price: Far-month futures price.

    Returns:
        "contango" if far > near, "backwardation" if far < near, "flat" if equal.
    """
    if far_price > near_price:
        return "contango"
    elif far_price < near_price:
        return "backwardation"
    return "flat"


def calendar_spread_fair_value(
    spot: float,
    r: float,
    T_near: float,
    T_far: float,
    q: float = 0.0,
) -> dict:
    """Calculate theoretical calendar spread value.

    Calendar spread = Far month futures - Near month futures.
    Both priced via cost-of-carry.

    Args:
        spot: Current spot price.
        r: Risk-free rate.
        T_near: Time to near-month expiry (years).
        T_far: Time to far-month expiry (years).
        q: Continuous dividend yield.

    Returns:
        Dict with near_fv, far_fv, spread, spread_pct.
    """
    near_fv = theoretical_futures_price(spot, r, T_near, q)
    far_fv = theoretical_futures_price(spot, r, T_far, q)
    spread = far_fv - near_fv
    spread_pct = (spread / spot * 100) if spot > 0 else 0.0

    return {
        "near_fair_value": round(near_fv, 2),
        "far_fair_value": round(far_fv, 2),
        "spread": round(spread, 2),
        "spread_pct": round(spread_pct, 4),
        "structure": contango_or_backwardation(near_fv, far_fv),
    }
