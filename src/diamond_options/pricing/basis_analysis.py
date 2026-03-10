"""Futures basis tracking and convergence analysis.

The basis is the difference between futures price and spot price.
It converges to zero at expiry. Tracking basis helps identify:
- Rich/cheap futures (relative to fair value)
- Roll yield for carry trades
- Convergence rate for timing
- Historical basis statistics for signal generation

Key concepts:
    Basis = Futures - Spot
    Annualized basis = (basis / spot) × (365 / DTE) × 100
    Roll yield = annualized spread between near and next month
    Basis convergence = expected daily shrinkage of basis toward zero
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BasisAnalysis:
    """Complete basis analysis for a futures contract."""

    current_basis: float  # Futures - spot (₹)
    current_basis_pct: float  # Basis as % of spot
    annualized_basis: float  # Annualized cost of carry (%)
    basis_z_score: float  # Current basis vs. historical (std deviations)
    basis_percentile: float  # Where current basis sits historically (0-100)
    signal: str  # "rich" / "cheap" / "fair"
    convergence_rate: float  # Expected daily basis decay (₹/day)
    roll_yield: float  # Annualized roll yield from near→next (%)
    days_to_expiry: int


def calculate_basis(futures_price: float, spot_price: float) -> dict:
    """Calculate basic basis metrics.

    Args:
        futures_price: Current futures price.
        spot_price: Current spot price.

    Returns:
        Dict with basis (₹), basis_pct (%), is_contango, is_backwardation.
    """
    basis = futures_price - spot_price
    basis_pct = (basis / spot_price * 100) if spot_price > 0 else 0.0

    return {
        "basis": round(basis, 2),
        "basis_pct": round(basis_pct, 4),
        "is_contango": basis > 0,
        "is_backwardation": basis < 0,
    }


def annualized_basis(basis_pct: float, days_to_expiry: int) -> float:
    """Annualize the basis percentage.

    Converts the basis (% of spot over remaining DTE) to an annualized rate.
    This is comparable to the risk-free rate as cost of carry.

    Args:
        basis_pct: Basis as percentage of spot.
        days_to_expiry: Calendar days remaining.

    Returns:
        Annualized basis in percentage.
    """
    if days_to_expiry <= 0:
        return 0.0
    return (basis_pct / days_to_expiry) * 365


def basis_convergence_rate(
    basis: float,
    days_to_expiry: int,
) -> float:
    """Expected daily basis decay toward zero.

    At expiry, basis = 0. Assuming linear convergence:
        daily_decay = basis / days_to_expiry

    In practice convergence accelerates near expiry, but linear is
    a reasonable first approximation.

    Args:
        basis: Current basis in ₹.
        days_to_expiry: Calendar days remaining.

    Returns:
        Expected daily basis reduction (₹/day). Positive means
        basis is shrinking toward zero.
    """
    if days_to_expiry <= 0:
        return 0.0
    return basis / days_to_expiry


def roll_yield(
    near_price: float,
    next_price: float,
    days_between: int,
) -> float:
    """Annualized roll yield from rolling near to next month.

    Roll yield = annualized spread between consecutive months.
    Positive in contango (you pay more for next month).
    Negative in backwardation (next month is cheaper).

    For a long position rolling forward in contango, roll yield
    is a cost. In backwardation, it's a benefit.

    Args:
        near_price: Near-month futures price.
        next_price: Next-month futures price.
        days_between: Calendar days between the two expiries.

    Returns:
        Annualized roll yield in percentage.
    """
    if near_price <= 0 or days_between <= 0:
        return 0.0
    spread_pct = (next_price - near_price) / near_price * 100
    return (spread_pct / days_between) * 365


def historical_basis_stats(basis_series: list[float]) -> dict:
    """Calculate statistics on a historical basis series.

    Used to determine if current basis is historically rich or cheap.

    Args:
        basis_series: List of historical basis values (₹ or %).

    Returns:
        Dict with mean, std, min, max, current_z_score (if last value is current).
    """
    if not basis_series:
        return {
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "max": 0.0,
            "count": 0,
        }

    n = len(basis_series)
    mean = sum(basis_series) / n
    variance = sum((x - mean) ** 2 for x in basis_series) / n if n > 1 else 0.0
    std = math.sqrt(variance)

    return {
        "mean": round(mean, 4),
        "std": round(std, 4),
        "min": round(min(basis_series), 4),
        "max": round(max(basis_series), 4),
        "count": n,
    }


def basis_z_score(
    current_basis: float,
    historical_mean: float,
    historical_std: float,
) -> float:
    """Z-score of current basis vs. historical distribution.

    Args:
        current_basis: Current basis value.
        historical_mean: Mean of historical basis.
        historical_std: Std dev of historical basis.

    Returns:
        Z-score. >2 = rich, <-2 = cheap, else fair.
    """
    if historical_std <= 0:
        return 0.0
    return (current_basis - historical_mean) / historical_std


def basis_percentile(
    current_basis: float,
    basis_series: list[float],
) -> float:
    """Percentile rank of current basis in historical distribution.

    Args:
        current_basis: Current basis value.
        basis_series: Historical basis values.

    Returns:
        Percentile (0-100). 90+ = very rich, 10- = very cheap.
    """
    if not basis_series:
        return 50.0
    count_below = sum(1 for x in basis_series if x <= current_basis)
    return (count_below / len(basis_series)) * 100


def basis_trade_signal(
    current_basis_pct: float,
    historical_mean: float,
    historical_std: float,
    rich_threshold: float = 1.5,
    cheap_threshold: float = -1.5,
) -> str:
    """Generate a trading signal based on basis z-score.

    Args:
        current_basis_pct: Current basis as % of spot.
        historical_mean: Mean basis %.
        historical_std: Std dev of basis %.
        rich_threshold: Z-score above which basis is "rich" (sell futures).
        cheap_threshold: Z-score below which basis is "cheap" (buy futures).

    Returns:
        "rich" (sell signal), "cheap" (buy signal), or "fair" (no signal).
    """
    z = basis_z_score(current_basis_pct, historical_mean, historical_std)
    if z > rich_threshold:
        return "rich"
    if z < cheap_threshold:
        return "cheap"
    return "fair"


def analyze_basis(
    futures_price: float,
    spot_price: float,
    days_to_expiry: int,
    basis_history: list[float] | None = None,
    next_month_price: float | None = None,
    next_month_days: int | None = None,
) -> BasisAnalysis:
    """Full basis analysis for a futures contract.

    Args:
        futures_price: Current futures price.
        spot_price: Current spot price.
        days_to_expiry: Calendar days to expiry.
        basis_history: Historical basis_pct values for z-score/percentile.
        next_month_price: Next month futures price (for roll yield).
        next_month_days: Days between near and next month expiry.

    Returns:
        BasisAnalysis with all metrics.
    """
    b = calculate_basis(futures_price, spot_price)
    current = b["basis"]
    current_pct = b["basis_pct"]

    ann_basis = annualized_basis(current_pct, days_to_expiry)
    conv_rate = basis_convergence_rate(current, days_to_expiry)

    # Historical stats
    if basis_history and len(basis_history) >= 5:
        stats = historical_basis_stats(basis_history)
        z = basis_z_score(current_pct, stats["mean"], stats["std"])
        pctile = basis_percentile(current_pct, basis_history)
        signal = basis_trade_signal(current_pct, stats["mean"], stats["std"])
    else:
        z = 0.0
        pctile = 50.0
        signal = "fair"

    # Roll yield
    ry = 0.0
    if next_month_price is not None and next_month_days is not None:
        ry = roll_yield(futures_price, next_month_price, next_month_days)

    return BasisAnalysis(
        current_basis=round(current, 2),
        current_basis_pct=round(current_pct, 4),
        annualized_basis=round(ann_basis, 4),
        basis_z_score=round(z, 4),
        basis_percentile=round(pctile, 2),
        signal=signal,
        convergence_rate=round(conv_rate, 4),
        roll_yield=round(ry, 4),
        days_to_expiry=days_to_expiry,
    )
