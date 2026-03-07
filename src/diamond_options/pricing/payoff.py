"""Payoff and P&L calculator for option positions and spreads.

Computes payoff at expiry, breakeven points, max profit/loss,
probability of profit, and expected value for any option position.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from diamond_options.pricing.greeks import probability_of_profit


@dataclass(frozen=True)
class Leg:
    """A single leg of an option position."""
    strike: float
    option_type: str         # "CE" or "PE"
    action: str              # "BUY" or "SELL"
    premium: float           # Per-share premium paid/received
    lots: int = 1
    lot_size: int = 65


@dataclass(frozen=True)
class PayoffAnalysis:
    """Complete payoff analysis for a position."""
    max_profit: float        # Maximum profit (INR, can be float('inf'))
    max_loss: float          # Maximum loss (INR, always negative)
    breakevens: list[float]  # Breakeven prices
    risk_reward: float       # |max_profit / max_loss| ratio
    net_premium: float       # Net premium paid (positive) or received (negative)
    margin_required: float   # Estimated margin requirement


def leg_payoff_at_expiry(leg: Leg, spot: float) -> float:
    """Calculate P&L for a single leg at a given spot price at expiry.

    Returns P&L per lot (including premium).
    """
    qty = leg.lots * leg.lot_size
    is_long = leg.action.upper() == "BUY"

    if leg.option_type.upper() in ("CE", "CALL", "C"):
        intrinsic = max(spot - leg.strike, 0.0)
    else:
        intrinsic = max(leg.strike - spot, 0.0)

    if is_long:
        pnl = (intrinsic - leg.premium) * qty
    else:
        pnl = (leg.premium - intrinsic) * qty

    return pnl


def position_payoff_at_expiry(legs: list[Leg], spot: float) -> float:
    """Calculate total P&L for all legs at a given spot price at expiry."""
    return sum(leg_payoff_at_expiry(leg, spot) for leg in legs)


def payoff_curve(
    legs: list[Leg],
    spot: float,
    range_pct: float = 0.10,
    num_points: int = 200,
) -> tuple[list[float], list[float]]:
    """Generate payoff curve data points.

    Args:
        legs: List of option legs.
        spot: Current spot price (for centering the range).
        range_pct: Price range as fraction of spot (e.g., 0.10 = +/-10%).
        num_points: Number of points to calculate.

    Returns:
        Tuple of (prices, payoffs) lists.
    """
    low = spot * (1 - range_pct)
    high = spot * (1 + range_pct)
    prices = list(np.linspace(low, high, num_points))
    payoffs = [position_payoff_at_expiry(legs, p) for p in prices]
    return prices, payoffs


def analyze_payoff(
    legs: list[Leg],
    spot: float,
    range_pct: float = 0.15,
) -> PayoffAnalysis:
    """Comprehensive payoff analysis for a multi-leg position.

    Finds max profit, max loss, breakevens, and risk-reward ratio.

    Args:
        legs: List of option legs.
        spot: Current spot price.
        range_pct: Analysis range as fraction of spot.

    Returns:
        PayoffAnalysis with all key metrics.
    """
    # Generate fine-grained payoff curve
    prices, payoffs = payoff_curve(legs, spot, range_pct, num_points=1000)

    max_profit = max(payoffs)
    max_loss = min(payoffs)

    # Check for unlimited profit/loss at edges
    edge_low = position_payoff_at_expiry(legs, spot * 0.5)
    edge_high = position_payoff_at_expiry(legs, spot * 1.5)
    extreme_low = position_payoff_at_expiry(legs, spot * 0.01)
    extreme_high = position_payoff_at_expiry(legs, spot * 2.0)

    # If payoff keeps growing, it's unlimited
    if extreme_high > max_profit * 2 or extreme_low > max_profit * 2:
        max_profit = float("inf")
    else:
        max_profit = max(max_profit, edge_low, edge_high)

    if extreme_high < max_loss * 2 or extreme_low < max_loss * 2:
        max_loss = float("-inf")
    else:
        max_loss = min(max_loss, edge_low, edge_high)

    # Find breakeven points (where payoff crosses zero)
    breakevens = []
    for i in range(len(payoffs) - 1):
        if (payoffs[i] <= 0 <= payoffs[i + 1]) or (payoffs[i] >= 0 >= payoffs[i + 1]):
            # Linear interpolation
            if payoffs[i + 1] != payoffs[i]:
                be = prices[i] + (0 - payoffs[i]) * (prices[i + 1] - prices[i]) / (
                    payoffs[i + 1] - payoffs[i]
                )
                breakevens.append(round(be, 2))

    # Risk-reward ratio
    if max_loss == 0 or max_loss == float("-inf"):
        risk_reward = 0.0
    elif max_profit == float("inf"):
        risk_reward = float("inf")
    else:
        risk_reward = abs(max_profit / max_loss) if max_loss != 0 else float("inf")

    # Net premium
    net_premium = 0.0
    for leg in legs:
        qty = leg.lots * leg.lot_size
        if leg.action.upper() == "BUY":
            net_premium -= leg.premium * qty  # Pay premium
        else:
            net_premium += leg.premium * qty  # Receive premium

    # Margin estimate (simplified — real SPAN margin is more complex)
    margin = _estimate_margin(legs, spot)

    return PayoffAnalysis(
        max_profit=round(max_profit, 2) if max_profit != float("inf") else float("inf"),
        max_loss=round(max_loss, 2) if max_loss != float("-inf") else float("-inf"),
        breakevens=breakevens,
        risk_reward=round(risk_reward, 2) if risk_reward != float("inf") else float("inf"),
        net_premium=round(net_premium, 2),
        margin_required=round(margin, 2),
    )


def _estimate_margin(legs: list[Leg], spot: float) -> float:
    """Simplified margin estimation for option positions.

    Real SPAN margin is computed by NSE clearing corp using a 16-scenario
    risk matrix. This is a conservative approximation.

    Rules of thumb:
    - Long options: premium paid (no additional margin)
    - Short naked options: ~15-20% of underlying value
    - Spreads: max loss of the spread
    - Short straddle/strangle: higher of the two legs + other premium
    """
    long_legs = [l for l in legs if l.action.upper() == "BUY"]
    short_legs = [l for l in legs if l.action.upper() == "SELL"]

    if not short_legs:
        # All long: margin = total premium paid
        return sum(l.premium * l.lots * l.lot_size for l in long_legs)

    # Check if it's a spread (same type, different strikes)
    if len(legs) == 2 and len(short_legs) == 1 and len(long_legs) == 1:
        short = short_legs[0]
        long = long_legs[0]
        if short.option_type == long.option_type:
            # Defined-risk spread: margin = width * lot_size * lots
            width = abs(short.strike - long.strike)
            return width * short.lots * short.lot_size

    # General case: sum of short leg margins minus hedges
    total_margin = 0.0
    for sl in short_legs:
        naked_margin = spot * 0.15 * sl.lots * sl.lot_size  # 15% of notional
        # Reduce if hedged
        for ll in long_legs:
            if ll.option_type == sl.option_type:
                width = abs(sl.strike - ll.strike)
                hedge_reduction = naked_margin - (width * sl.lots * sl.lot_size)
                if hedge_reduction > 0:
                    naked_margin = min(naked_margin, width * sl.lots * sl.lot_size)
                break
        total_margin += naked_margin

    return total_margin


def expected_value(
    legs: list[Leg],
    spot: float,
    T: float,
    r: float,
    sigma: float,
    num_simulations: int = 10000,
) -> dict:
    """Monte Carlo expected value of a position.

    Simulates log-normal price paths and calculates expected P&L.

    Args:
        legs: Option legs.
        spot: Current spot price.
        T: Time to expiry in years.
        r: Risk-free rate.
        sigma: Volatility.
        num_simulations: Number of price simulations.

    Returns:
        Dict with expected_pnl, prob_profit, median_pnl, var_95.
    """
    rng = np.random.default_rng(42)

    # Simulate terminal prices using geometric Brownian motion
    drift = (r - 0.5 * sigma**2) * T
    diffusion = sigma * np.sqrt(T) * rng.standard_normal(num_simulations)
    terminal_prices = spot * np.exp(drift + diffusion)

    # Calculate payoff at each terminal price
    pnls = np.array([position_payoff_at_expiry(legs, float(p)) for p in terminal_prices])

    profitable = np.sum(pnls > 0)
    prob_profit = profitable / num_simulations

    return {
        "expected_pnl": round(float(np.mean(pnls)), 2),
        "median_pnl": round(float(np.median(pnls)), 2),
        "prob_profit": round(prob_profit * 100, 1),
        "var_95": round(float(np.percentile(pnls, 5)), 2),  # 5th percentile
        "best_case": round(float(np.max(pnls)), 2),
        "worst_case": round(float(np.min(pnls)), 2),
        "std_pnl": round(float(np.std(pnls)), 2),
    }
