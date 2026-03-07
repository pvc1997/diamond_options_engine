"""Black-Scholes option pricing model.

European option pricing with continuous dividend yield adjustment.
Used for Indian index options (NIFTY, BANKNIFTY) which are European-style
and cash-settled. Stock options in India are also European-style since 2011.

All inputs use annualized values:
- S: Spot price
- K: Strike price
- T: Time to expiry in years (calendar days / 365)
- r: Risk-free rate (annualized, e.g., 0.065 for 6.5%)
- sigma: Volatility (annualized, e.g., 0.20 for 20%)
- q: Continuous dividend yield (annualized, e.g., 0.012 for 1.2%)

References:
- Black, F. & Scholes, M. (1973). "The Pricing of Options and Corporate Liabilities"
- Hull, J. (2018). "Options, Futures, and Other Derivatives" (10th ed.)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm


@dataclass(frozen=True)
class BSResult:
    """Black-Scholes pricing result."""
    price: float           # Option premium
    d1: float              # d1 parameter
    d2: float              # d2 parameter
    intrinsic: float       # Intrinsic value
    time_value: float      # Extrinsic / time value


def _d1(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Calculate d1 parameter of Black-Scholes formula.

    d1 = [ln(S/K) + (r - q + sigma^2/2) * T] / (sigma * sqrt(T))
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    return (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))


def _d2(d1_val: float, sigma: float, T: float) -> float:
    """Calculate d2 parameter: d2 = d1 - sigma * sqrt(T)."""
    if T <= 0 or sigma <= 0:
        return 0.0
    return d1_val - sigma * math.sqrt(T)


def call_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> BSResult:
    """Price a European call option using Black-Scholes.

    C = S * e^(-qT) * N(d1) - K * e^(-rT) * N(d2)

    Args:
        S: Spot price of underlying.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        sigma: Volatility (annualized).
        q: Continuous dividend yield (annualized).

    Returns:
        BSResult with price, d1, d2, intrinsic, and time value.
    """
    if T <= 0:
        # At expiry: intrinsic value only
        intrinsic = max(S - K, 0.0)
        return BSResult(price=intrinsic, d1=0, d2=0, intrinsic=intrinsic, time_value=0)

    if sigma <= 0:
        # Zero vol: present value of intrinsic
        pv = max(S * math.exp(-q * T) - K * math.exp(-r * T), 0.0)
        intrinsic = max(S - K, 0.0)
        return BSResult(price=pv, d1=0, d2=0, intrinsic=intrinsic, time_value=pv - intrinsic)

    d1_val = _d1(S, K, T, r, sigma, q)
    d2_val = _d2(d1_val, sigma, T)

    price = (
        S * math.exp(-q * T) * norm.cdf(d1_val)
        - K * math.exp(-r * T) * norm.cdf(d2_val)
    )

    intrinsic = max(S - K, 0.0)
    time_value = price - intrinsic

    return BSResult(
        price=max(price, 0.0),
        d1=d1_val,
        d2=d2_val,
        intrinsic=intrinsic,
        time_value=max(time_value, 0.0),
    )


def put_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> BSResult:
    """Price a European put option using Black-Scholes.

    P = K * e^(-rT) * N(-d2) - S * e^(-qT) * N(-d1)

    Args:
        S: Spot price of underlying.
        K: Strike price.
        T: Time to expiry in years.
        r: Risk-free interest rate (annualized).
        sigma: Volatility (annualized).
        q: Continuous dividend yield (annualized).

    Returns:
        BSResult with price, d1, d2, intrinsic, and time value.
    """
    if T <= 0:
        intrinsic = max(K - S, 0.0)
        return BSResult(price=intrinsic, d1=0, d2=0, intrinsic=intrinsic, time_value=0)

    if sigma <= 0:
        pv = max(K * math.exp(-r * T) - S * math.exp(-q * T), 0.0)
        intrinsic = max(K - S, 0.0)
        return BSResult(price=pv, d1=0, d2=0, intrinsic=intrinsic, time_value=pv - intrinsic)

    d1_val = _d1(S, K, T, r, sigma, q)
    d2_val = _d2(d1_val, sigma, T)

    price = (
        K * math.exp(-r * T) * norm.cdf(-d2_val)
        - S * math.exp(-q * T) * norm.cdf(-d1_val)
    )

    intrinsic = max(K - S, 0.0)
    time_value = price - intrinsic

    return BSResult(
        price=max(price, 0.0),
        d1=d1_val,
        d2=d2_val,
        intrinsic=intrinsic,
        time_value=max(time_value, 0.0),
    )


def price_option(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    q: float = 0.0,
) -> BSResult:
    """Price an option — dispatches to call_price or put_price.

    Args:
        option_type: "CE" or "call" for call, "PE" or "put" for put.
    """
    ot = option_type.upper()
    if ot in ("CE", "CALL", "C"):
        return call_price(S, K, T, r, sigma, q)
    elif ot in ("PE", "PUT", "P"):
        return put_price(S, K, T, r, sigma, q)
    else:
        raise ValueError(f"Invalid option_type: {option_type}. Use CE/PE or call/put.")


def put_call_parity_check(
    call_px: float,
    put_px: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
) -> dict:
    """Verify put-call parity: C - P = S*e^(-qT) - K*e^(-rT).

    Returns the theoretical relationship and any deviation.
    Deviations > 1% of spot may indicate arbitrage or bad data.
    """
    lhs = call_px - put_px
    rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
    deviation = lhs - rhs
    deviation_pct = abs(deviation) / S * 100 if S > 0 else 0

    return {
        "call_minus_put": round(lhs, 4),
        "theoretical": round(rhs, 4),
        "deviation": round(deviation, 4),
        "deviation_pct": round(deviation_pct, 4),
        "parity_holds": bool(deviation_pct < 1.0),
    }
