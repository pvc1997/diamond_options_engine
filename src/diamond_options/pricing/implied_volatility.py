"""Implied Volatility solver using Newton-Raphson method.

Extracts implied volatility from observed option prices by finding the sigma
that makes the Black-Scholes price equal to the market price.

Uses Newton-Raphson (quadratic convergence) with Brenner-Subrahmanyam
initial estimate for fast convergence.

Performance: Typically converges in 3-5 iterations for ATM options.
"""

from __future__ import annotations

import math

from diamond_options.pricing.black_scholes import call_price, put_price
from diamond_options.pricing.greeks import vega


def _initial_estimate(S: float, K: float, T: float, market_price: float) -> float:
    """Brenner-Subrahmanyam initial IV estimate.

    sigma_0 = sqrt(2*pi/T) * (C/S) for ATM options.
    For OTM/ITM, use a more robust starting point.
    """
    if T <= 0 or S <= 0:
        return 0.20  # Default fallback

    # Brenner-Subrahmanyam for near-ATM
    moneyness = S / K
    if 0.8 < moneyness < 1.2:
        estimate = math.sqrt(2 * math.pi / T) * (market_price / S)
        return max(0.01, min(estimate, 5.0))

    # For far OTM/ITM, start with 30%
    return 0.30


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str,
    q: float = 0.0,
    max_iterations: int = 100,
    tolerance: float = 1e-8,
) -> float | None:
    """Calculate implied volatility using Newton-Raphson.

    Finds sigma such that BS_price(sigma) = market_price.

    Args:
        market_price: Observed market premium.
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate.
        option_type: "CE" or "PE".
        q: Dividend yield.
        max_iterations: Max Newton-Raphson iterations.
        tolerance: Convergence threshold.

    Returns:
        Implied volatility as decimal (e.g., 0.20 for 20%), or None if no convergence.
    """
    if market_price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return None

    is_call = option_type.upper() in ("CE", "CALL", "C")

    # Check intrinsic value bounds
    if is_call:
        intrinsic = max(S * math.exp(-q * T) - K * math.exp(-r * T), 0.0)
    else:
        intrinsic = max(K * math.exp(-r * T) - S * math.exp(-q * T), 0.0)

    if market_price < intrinsic - 0.01:
        # Price below intrinsic — likely bad data
        return None

    sigma = _initial_estimate(S, K, T, market_price)

    for _ in range(max_iterations):
        # Calculate BS price at current sigma
        if is_call:
            bs = call_price(S, K, T, r, sigma, q)
        else:
            bs = put_price(S, K, T, r, sigma, q)

        price_diff = bs.price - market_price

        # Check convergence
        if abs(price_diff) < tolerance:
            return sigma

        # Vega for Newton-Raphson step (per-unit, not per-1%)
        v = vega(S, K, T, r, sigma, q) * 100  # Convert back to per-unit

        if abs(v) < 1e-12:
            # Vega too small — can't converge (deep ITM/OTM near expiry)
            break

        # Newton-Raphson update
        sigma = sigma - price_diff / v

        # Bound sigma to reasonable range
        if sigma <= 0.001:
            sigma = 0.001
        elif sigma > 10.0:
            sigma = 10.0

    # Try bisection as fallback
    return _bisection_iv(market_price, S, K, T, r, is_call, q)


def _bisection_iv(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    is_call: bool,
    q: float = 0.0,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> float | None:
    """Bisection method as fallback for IV when Newton-Raphson fails."""
    low, high = 0.001, 5.0

    for _ in range(max_iterations):
        mid = (low + high) / 2.0

        if is_call:
            bs = call_price(S, K, T, r, mid, q)
        else:
            bs = put_price(S, K, T, r, mid, q)

        if abs(bs.price - market_price) < tolerance:
            return mid

        if bs.price > market_price:
            high = mid
        else:
            low = mid

        if high - low < tolerance / 10:
            return mid

    return None


def implied_volatility_safe(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str,
    q: float = 0.0,
) -> float:
    """IV solver that returns 0.0 instead of None on failure.

    Convenient for batch processing where failures should be silently skipped.
    """
    result = implied_volatility(market_price, S, K, T, r, option_type, q)
    return result if result is not None else 0.0
