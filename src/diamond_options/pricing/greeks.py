"""Option Greeks — first and second order sensitivities.

All Greeks computed analytically from the Black-Scholes model.
Provides both individual Greek calculations and a combined Greeks bundle.

Greek Definitions (for the user):
- Delta: Price change per Rs. 1 move in underlying
- Gamma: Delta change per Rs. 1 move (acceleration)
- Theta: Time decay per day (in Rs., negative for long options)
- Vega: Price change per 1% move in IV
- Rho: Price change per 1% move in interest rate

Conventions:
- Theta is per calendar day (divide annual by 365)
- Vega is per 1 percentage point of volatility (not per 1 unit)
- All values are per-share (multiply by lot_size for per-lot)

References:
- Hull, J. (2018). "Options, Futures, and Other Derivatives" Ch. 19
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm

from diamond_options.pricing.black_scholes import _d1, _d2


@dataclass(frozen=True)
class Greeks:
    """Complete Greeks bundle for an option."""
    delta: float     # dV/dS
    gamma: float     # d²V/dS²
    theta: float     # dV/dt (per calendar day, in price units)
    vega: float      # dV/d(sigma) per 1% vol move
    rho: float       # dV/dr per 1% rate move
    # Second-order
    vanna: float     # d²V/(dS·d_sigma) — delta sensitivity to vol
    charm: float     # d²V/(dS·dt) — delta decay per day


def call_delta(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Call delta: e^(-qT) * N(d1). Range: [0, 1]."""
    if T <= 0:
        return 1.0 if S > K else (0.5 if S == K else 0.0)
    if sigma <= 0:
        return 1.0 if S > K else 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    return math.exp(-q * T) * norm.cdf(d1)


def put_delta(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Put delta: e^(-qT) * [N(d1) - 1]. Range: [-1, 0]."""
    if T <= 0:
        return -1.0 if S < K else (-0.5 if S == K else 0.0)
    if sigma <= 0:
        return -1.0 if S < K else 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    return math.exp(-q * T) * (norm.cdf(d1) - 1.0)


def gamma(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Gamma (same for call and put): e^(-qT) * n(d1) / (S * sigma * sqrt(T)).

    Gamma measures the rate of change of delta. Highest for ATM options near expiry.
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    return math.exp(-q * T) * norm.pdf(d1) / (S * sigma * math.sqrt(T))


def call_theta(
    S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0,
) -> float:
    """Call theta per calendar day.

    Theta = -(S * sigma * e^(-qT) * n(d1)) / (2 * sqrt(T))
            + q * S * e^(-qT) * N(d1) - r * K * e^(-rT) * N(d2)

    Returned as per-day (divided by 365). Negative for long calls.
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    d2 = _d2(d1, sigma, T)

    term1 = -(S * sigma * math.exp(-q * T) * norm.pdf(d1)) / (2 * math.sqrt(T))
    term2 = q * S * math.exp(-q * T) * norm.cdf(d1)
    term3 = -r * K * math.exp(-r * T) * norm.cdf(d2)

    return (term1 + term2 + term3) / 365.0


def put_theta(
    S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0,
) -> float:
    """Put theta per calendar day.

    Theta = -(S * sigma * e^(-qT) * n(d1)) / (2 * sqrt(T))
            - q * S * e^(-qT) * N(-d1) + r * K * e^(-rT) * N(-d2)

    Returned as per-day. Negative for long puts.
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    d2 = _d2(d1, sigma, T)

    term1 = -(S * sigma * math.exp(-q * T) * norm.pdf(d1)) / (2 * math.sqrt(T))
    term2 = -q * S * math.exp(-q * T) * norm.cdf(-d1)
    term3 = r * K * math.exp(-r * T) * norm.cdf(-d2)

    return (term1 + term2 + term3) / 365.0


def vega(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Vega (same for call and put) per 1 percentage point of volatility.

    Vega = S * e^(-qT) * sqrt(T) * n(d1) / 100

    The /100 converts from per-unit to per-1%-point.
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    return S * math.exp(-q * T) * math.sqrt(T) * norm.pdf(d1) / 100.0


def call_rho(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Call rho per 1 percentage point of interest rate.

    Rho = K * T * e^(-rT) * N(d2) / 100
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    d2 = _d2(d1, sigma, T)
    return K * T * math.exp(-r * T) * norm.cdf(d2) / 100.0


def put_rho(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Put rho per 1 percentage point of interest rate.

    Rho = -K * T * e^(-rT) * N(-d2) / 100
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    d2 = _d2(d1, sigma, T)
    return -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100.0


def vanna(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Vanna: d(delta)/d(sigma) = d(vega)/d(S).

    Vanna = -e^(-qT) * n(d1) * d2 / sigma

    Measures how delta changes with volatility. Important for vol traders.
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    d2 = _d2(d1, sigma, T)
    return -math.exp(-q * T) * norm.pdf(d1) * d2 / sigma


def charm(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Charm (delta decay): d(delta)/d(t) per calendar day.

    How much delta changes as time passes (1 day). Important for managing
    delta-neutral positions.
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    d2 = _d2(d1, sigma, T)

    part1 = q * math.exp(-q * T) * norm.cdf(d1)
    part2 = math.exp(-q * T) * norm.pdf(d1) * (
        2 * (r - q) * T - d2 * sigma * math.sqrt(T)
    ) / (2 * T * sigma * math.sqrt(T))

    return -(part1 - part2) / 365.0


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0,
) -> Greeks:
    """Calculate all Greeks for an option.

    Args:
        S: Spot price.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free rate (annualized).
        sigma: Volatility (annualized).
        option_type: "CE"/"call" or "PE"/"put".
        q: Dividend yield (annualized).

    Returns:
        Greeks dataclass with delta, gamma, theta, vega, rho, vanna, charm.
    """
    ot = option_type.upper()
    is_call = ot in ("CE", "CALL", "C")

    if is_call:
        d = call_delta(S, K, T, r, sigma, q)
        th = call_theta(S, K, T, r, sigma, q)
        rh = call_rho(S, K, T, r, sigma, q)
    else:
        d = put_delta(S, K, T, r, sigma, q)
        th = put_theta(S, K, T, r, sigma, q)
        rh = put_rho(S, K, T, r, sigma, q)

    g = gamma(S, K, T, r, sigma, q)
    v = vega(S, K, T, r, sigma, q)
    va = vanna(S, K, T, r, sigma, q)
    ch = charm(S, K, T, r, sigma, q)

    return Greeks(
        delta=round(d, 6),
        gamma=round(g, 6),
        theta=round(th, 4),
        vega=round(v, 4),
        rho=round(rh, 4),
        vanna=round(va, 6),
        charm=round(ch, 6),
    )


def probability_itm(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: str, q: float = 0.0,
) -> float:
    """Probability of finishing in-the-money at expiry.

    For calls: N(d2)
    For puts: N(-d2)

    This is the risk-neutral probability, not the real-world probability.
    """
    if T <= 0 or sigma <= 0:
        if option_type.upper() in ("CE", "CALL", "C"):
            return 1.0 if S > K else 0.0
        return 1.0 if S < K else 0.0

    d1 = _d1(S, K, T, r, sigma, q)
    d2 = _d2(d1, sigma, T)

    if option_type.upper() in ("CE", "CALL", "C"):
        return norm.cdf(d2)
    return norm.cdf(-d2)


def probability_of_profit(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: str, premium: float, q: float = 0.0,
) -> float:
    """Probability of the trade being profitable at expiry.

    For long call: P(S > K + premium)
    For long put: P(S < K - premium)
    For short call: P(S < K + premium) = 1 - P(long call profit)
    For short put: P(S > K - premium) = 1 - P(long put profit)

    Args:
        premium: Premium paid (positive) or received (negative).
    """
    if T <= 0 or sigma <= 0:
        return 0.0

    ot = option_type.upper()
    is_call = ot in ("CE", "CALL", "C")
    is_long = premium > 0  # Paid premium = long position

    if is_call:
        breakeven = K + abs(premium)
    else:
        breakeven = K - abs(premium)

    # Use BS model to find probability of being beyond breakeven
    d1_be = _d1(S, breakeven, T, r, sigma, q)
    d2_be = _d2(d1_be, sigma, T)

    if is_call:
        prob_beyond = norm.cdf(d2_be)  # P(S > breakeven)
    else:
        prob_beyond = norm.cdf(-d2_be)  # P(S < breakeven)

    if is_long:
        return prob_beyond
    else:
        return 1.0 - prob_beyond
