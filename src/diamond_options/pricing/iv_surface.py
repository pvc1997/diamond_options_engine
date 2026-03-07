"""Implied Volatility Surface — smile, skew, and term structure analysis.

Analyzes IV patterns across strikes (smile/skew) and expiries (term structure).
Provides IV rank and percentile for identifying high/low vol opportunities.

Key concepts:
- IV Smile: Higher IV for far OTM puts and calls (typical in indices)
- IV Skew: Put IV > Call IV at same distance from ATM (demand for protection)
- IV Term Structure: How IV varies across expiries (contango/backwardation)
- IV Rank: Where current IV sits relative to its 1-year range (0-100)
- IV Percentile: % of days in the past year with IV below current (0-100)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from diamond_options.data.options_chain import OptionsChain, OptionQuote
from diamond_options.pricing.implied_volatility import implied_volatility_safe
from diamond_options.utils.indian_markets import years_to_expiry


@dataclass(frozen=True)
class IVPoint:
    """A single point on the IV surface."""
    strike: float
    expiry_days: int         # Calendar days to expiry
    iv: float
    moneyness: float         # Strike / Spot
    option_type: str         # CE or PE
    delta: float             # For delta-space mapping


@dataclass(frozen=True)
class SmileAnalysis:
    """IV smile/skew analysis for a single expiry."""
    atm_iv: float            # ATM implied volatility
    put_skew: float          # 25-delta put IV - ATM IV (positive = skew)
    call_skew: float         # 25-delta call IV - ATM IV (typically negative)
    skew_ratio: float        # 25-delta put IV / 25-delta call IV
    smile_curvature: float   # Average OTM IV - ATM IV (butterfly measure)
    put_wing_iv: float       # Average far OTM put IV
    call_wing_iv: float      # Average far OTM call IV


@dataclass(frozen=True)
class IVRankPercentile:
    """IV rank and percentile relative to historical range."""
    current_iv: float
    iv_rank: float           # (current - low) / (high - low) * 100
    iv_percentile: float     # % of days below current
    iv_high: float           # 1-year high
    iv_low: float            # 1-year low
    iv_mean: float           # 1-year mean
    iv_std: float            # 1-year std
    regime: str              # "low", "normal", "high", "extreme"


def extract_smile(
    chain: OptionsChain,
    r: float = 0.065,
    q: float = 0.0,
) -> SmileAnalysis:
    """Extract IV smile/skew from an options chain.

    Analyzes the IV pattern across strikes for a single expiry.

    Args:
        chain: Options chain with IV data.
        r: Risk-free rate.
        q: Dividend yield.

    Returns:
        SmileAnalysis with skew metrics.
    """
    spot = chain.spot_price
    atm = chain.atm_strike
    T = years_to_expiry(chain.expiry)

    # Get ATM IV (average of call and put)
    atm_call = chain.get_call(atm)
    atm_put = chain.get_put(atm)

    atm_call_iv = _get_iv(atm_call, spot, T, r, q) if atm_call else 0.0
    atm_put_iv = _get_iv(atm_put, spot, T, r, q) if atm_put else 0.0

    if atm_call_iv > 0 and atm_put_iv > 0:
        atm_iv = (atm_call_iv + atm_put_iv) / 2
    else:
        atm_iv = atm_call_iv or atm_put_iv or 0.20

    # OTM put IVs (strikes below spot)
    otm_puts = chain.otm_puts()
    put_ivs = [_get_iv(p, spot, T, r, q) for p in otm_puts if p.iv > 0 or p.ltp > 0]
    put_ivs = [iv for iv in put_ivs if iv > 0]

    # OTM call IVs (strikes above spot)
    otm_calls = chain.otm_calls()
    call_ivs = [_get_iv(c, spot, T, r, q) for c in otm_calls if c.iv > 0 or c.ltp > 0]
    call_ivs = [iv for iv in call_ivs if iv > 0]

    # 25-delta approximation: ~2nd OTM strike
    put_25d_iv = put_ivs[1] if len(put_ivs) > 1 else (put_ivs[0] if put_ivs else atm_iv)
    call_25d_iv = call_ivs[1] if len(call_ivs) > 1 else (call_ivs[0] if call_ivs else atm_iv)

    put_skew = put_25d_iv - atm_iv
    call_skew = call_25d_iv - atm_iv
    skew_ratio = put_25d_iv / call_25d_iv if call_25d_iv > 0 else 1.0

    # Wings
    put_wing_iv = np.mean(put_ivs) if put_ivs else atm_iv
    call_wing_iv = np.mean(call_ivs) if call_ivs else atm_iv

    # Smile curvature (butterfly): average wing IV - ATM IV
    smile_curvature = ((put_wing_iv + call_wing_iv) / 2) - atm_iv

    return SmileAnalysis(
        atm_iv=round(atm_iv, 4),
        put_skew=round(put_skew, 4),
        call_skew=round(call_skew, 4),
        skew_ratio=round(skew_ratio, 4),
        smile_curvature=round(smile_curvature, 4),
        put_wing_iv=round(float(put_wing_iv), 4),
        call_wing_iv=round(float(call_wing_iv), 4),
    )


def _get_iv(
    quote: OptionQuote, spot: float, T: float, r: float, q: float,
) -> float:
    """Get IV from quote — use stored IV or solve from price."""
    if quote.iv > 0:
        return quote.iv
    if quote.ltp > 0 and T > 0:
        return implied_volatility_safe(
            quote.ltp, spot, quote.strike, T, r, quote.option_type, q,
        )
    return 0.0


def iv_rank(
    current_iv: float,
    historical_ivs: list[float],
) -> IVRankPercentile:
    """Calculate IV rank and percentile relative to historical IVs.

    Args:
        current_iv: Current ATM implied volatility.
        historical_ivs: List of historical daily ATM IV values (1 year).

    Returns:
        IVRankPercentile with rank (0-100), percentile, and regime.
    """
    if not historical_ivs:
        return IVRankPercentile(
            current_iv=current_iv, iv_rank=50, iv_percentile=50,
            iv_high=current_iv, iv_low=current_iv, iv_mean=current_iv,
            iv_std=0, regime="normal",
        )

    arr = np.array(historical_ivs)
    iv_high = float(np.max(arr))
    iv_low = float(np.min(arr))
    iv_mean = float(np.mean(arr))
    iv_std = float(np.std(arr))

    # IV Rank: (current - low) / (high - low) * 100
    if iv_high == iv_low:
        rank = 50.0
    else:
        rank = (current_iv - iv_low) / (iv_high - iv_low) * 100

    # IV Percentile: % of days below current
    percentile = float(np.sum(arr < current_iv)) / len(arr) * 100

    # Regime classification
    if rank < 20:
        regime = "low"
    elif rank < 50:
        regime = "normal"
    elif rank < 80:
        regime = "high"
    else:
        regime = "extreme"

    return IVRankPercentile(
        current_iv=round(current_iv, 4),
        iv_rank=round(rank, 1),
        iv_percentile=round(percentile, 1),
        iv_high=round(iv_high, 4),
        iv_low=round(iv_low, 4),
        iv_mean=round(iv_mean, 4),
        iv_std=round(iv_std, 4),
        regime=regime,
    )


def iv_term_structure(
    chains: list[OptionsChain],
    r: float = 0.065,
    q: float = 0.0,
) -> list[dict]:
    """Analyze IV across multiple expiries (term structure).

    Args:
        chains: List of options chains for different expiries (same underlying).
        r: Risk-free rate.
        q: Dividend yield.

    Returns:
        List of dicts with expiry, days, atm_iv for each chain.
        If short-term IV > long-term IV: backwardation (fear in near-term).
        If short-term IV < long-term IV: contango (normal state).
    """
    results = []
    for chain in sorted(chains, key=lambda c: c.expiry):
        smile = extract_smile(chain, r, q)
        days = (chain.expiry - chains[0].expiry).days if chains else 0

        results.append({
            "expiry": chain.expiry.isoformat(),
            "days_to_expiry": days,
            "atm_iv": smile.atm_iv,
            "put_skew": smile.put_skew,
        })

    # Determine structure type
    if len(results) >= 2:
        front_iv = results[0]["atm_iv"]
        back_iv = results[-1]["atm_iv"]
        structure = "backwardation" if front_iv > back_iv else "contango"
        for r_item in results:
            r_item["structure"] = structure

    return results


def iv_surface_grid(
    chain: OptionsChain,
    r: float = 0.065,
    q: float = 0.0,
) -> list[IVPoint]:
    """Build a flat IV surface grid for a single expiry.

    Maps strike -> IV for visualization and analysis.
    """
    spot = chain.spot_price
    T = years_to_expiry(chain.expiry)
    points = []

    for quote in chain.calls + chain.puts:
        iv = _get_iv(quote, spot, T, r, q)
        if iv <= 0:
            continue

        moneyness = quote.strike / spot
        days = max(1, int(T * 365))

        points.append(IVPoint(
            strike=quote.strike,
            expiry_days=days,
            iv=round(iv, 4),
            moneyness=round(moneyness, 4),
            option_type=quote.option_type,
            delta=quote.delta,
        ))

    return sorted(points, key=lambda p: (p.option_type, p.strike))
