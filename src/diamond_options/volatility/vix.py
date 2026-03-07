"""India VIX analysis and regime detection.

India VIX is the volatility index computed by NSE from NIFTY option prices.
It represents the market's expectation of 30-day forward volatility.

VIX Regime Rules (calibrated for Indian markets):
- < 12: Low vol (complacency) — buy protection, avoid selling premium
- 12-18: Normal range — balanced strategies
- 18-25: Elevated — premium selling opportunities
- 25-35: High fear — wide spreads, reduce exposure
- > 35: Crisis — only hedging, no new short premium

Historical India VIX range: ~8 (calm) to ~90 (COVID crash, March 2020).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VIXRegime:
    """Current VIX regime analysis."""
    vix_value: float
    regime: str              # "low", "normal", "elevated", "high", "crisis"
    regime_label: str        # Human-readable label
    percentile: float        # Where current VIX sits historically (0-100)
    strategy_bias: str       # Recommended strategy direction
    position_sizing: float   # Multiplier (0.25 - 1.0) for position sizing
    notes: str               # Actionable notes


# Historical India VIX levels for percentile estimation
# Mean ~15, Median ~13.5 over 2010-2025
_VIX_HISTOGRAM = {
    8: 2, 9: 5, 10: 10, 11: 12, 12: 15, 13: 14, 14: 12,
    15: 10, 16: 7, 17: 5, 18: 4, 19: 3, 20: 2.5, 21: 2,
    22: 1.5, 23: 1.2, 24: 1, 25: 0.8, 26: 0.6, 27: 0.5,
    28: 0.4, 29: 0.3, 30: 0.25, 35: 0.5, 40: 0.3, 50: 0.1,
}


def _estimate_percentile(vix: float) -> float:
    """Estimate VIX percentile from historical distribution."""
    total = sum(_VIX_HISTOGRAM.values())
    below = sum(v for k, v in _VIX_HISTOGRAM.items() if k < vix)
    return min(100.0, (below / total) * 100)


def classify_regime(vix_value: float) -> VIXRegime:
    """Classify current VIX into a trading regime.

    Args:
        vix_value: Current India VIX value.

    Returns:
        VIXRegime with actionable trading guidance.
    """
    percentile = _estimate_percentile(vix_value)

    if vix_value < 12:
        return VIXRegime(
            vix_value=vix_value,
            regime="low",
            regime_label="Low Volatility (Complacency)",
            percentile=percentile,
            strategy_bias="buy_vol",
            position_sizing=0.75,
            notes=(
                "Vol is unusually low — options are cheap. "
                "Good time to buy protection (puts) or long straddles. "
                "Avoid selling premium — risk/reward unfavorable for sellers."
            ),
        )
    elif vix_value < 18:
        return VIXRegime(
            vix_value=vix_value,
            regime="normal",
            regime_label="Normal Volatility",
            percentile=percentile,
            strategy_bias="neutral",
            position_sizing=1.0,
            notes=(
                "Vol is in normal range. All strategy types viable. "
                "Balanced approach — can sell or buy premium based on view. "
                "Standard position sizing."
            ),
        )
    elif vix_value < 25:
        return VIXRegime(
            vix_value=vix_value,
            regime="elevated",
            regime_label="Elevated Volatility",
            percentile=percentile,
            strategy_bias="sell_vol",
            position_sizing=0.80,
            notes=(
                "Vol is above normal — premium selling opportunities. "
                "Iron condors, short strangles have edge if VIX is peaking. "
                "Use wider strikes for safety. Reduce position size slightly."
            ),
        )
    elif vix_value < 35:
        return VIXRegime(
            vix_value=vix_value,
            regime="high",
            regime_label="High Volatility (Fear)",
            percentile=percentile,
            strategy_bias="sell_vol_cautious",
            position_sizing=0.50,
            notes=(
                "Market fear is elevated — premiums are rich. "
                "Sell premium with defined risk (spreads only, no naked). "
                "Use very wide strikes. Half position sizing. "
                "Excellent entry for calendar spreads if view is stabilization."
            ),
        )
    else:
        return VIXRegime(
            vix_value=vix_value,
            regime="crisis",
            regime_label="Crisis Volatility",
            percentile=percentile,
            strategy_bias="hedge_only",
            position_sizing=0.25,
            notes=(
                "Extreme fear — only hedging, no new short premium. "
                "Spreads can blow through strikes in panic. "
                "Focus on portfolio protection. "
                "Wait for VIX to stabilize before selling premium."
            ),
        )


def vix_mean_reversion_signal(
    current_vix: float,
    sma_20: float | None = None,
) -> dict:
    """Generate VIX mean-reversion signal.

    VIX tends to mean-revert: spikes don't last, and low vol regimes end.

    Args:
        current_vix: Current VIX value.
        sma_20: 20-day SMA of VIX (for trend detection).

    Returns:
        Signal dict with direction and strength.
    """
    regime = classify_regime(current_vix)
    mean_vix = 15.0  # Long-run India VIX mean

    deviation = current_vix - mean_vix
    deviation_pct = deviation / mean_vix * 100

    if sma_20 is not None:
        trend = "rising" if current_vix > sma_20 else "falling"
        trend_strength = abs(current_vix - sma_20) / sma_20 * 100
    else:
        trend = "unknown"
        trend_strength = 0.0

    # Signal
    if current_vix > mean_vix * 1.5:  # > 22.5
        signal = "sell_vol"
        strength = min(100, int(deviation_pct))
        explanation = f"VIX {deviation_pct:.0f}% above mean — likely to revert down"
    elif current_vix < mean_vix * 0.75:  # < 11.25
        signal = "buy_vol"
        strength = min(100, int(abs(deviation_pct)))
        explanation = f"VIX {abs(deviation_pct):.0f}% below mean — likely to spike"
    else:
        signal = "neutral"
        strength = 0
        explanation = "VIX near fair value — no strong mean-reversion signal"

    return {
        "current_vix": current_vix,
        "mean_vix": mean_vix,
        "deviation_pct": round(deviation_pct, 1),
        "trend": trend,
        "trend_strength": round(trend_strength, 1),
        "signal": signal,
        "signal_strength": strength,
        "explanation": explanation,
        "regime": regime.regime,
    }


def vix_term_structure_signal(
    near_vix: float,
    far_vix: float,
) -> dict:
    """Analyze VIX term structure (contango vs backwardation).

    Normal (contango): Near-term VIX < Far-term VIX → market calm
    Inverted (backwardation): Near-term VIX > Far-term VIX → market fear

    Args:
        near_vix: Near-month VIX.
        far_vix: Far-month VIX.

    Returns:
        Term structure analysis.
    """
    spread = near_vix - far_vix
    ratio = near_vix / far_vix if far_vix > 0 else 1.0

    if spread > 2:
        structure = "backwardation"
        signal = "fear"
        explanation = (
            f"Near-term vol ({near_vix:.1f}) > far-term ({far_vix:.1f}). "
            "Market pricing immediate risk. Caution with short near-term premium."
        )
    elif spread < -2:
        structure = "contango"
        signal = "calm"
        explanation = (
            f"Near-term vol ({near_vix:.1f}) < far-term ({far_vix:.1f}). "
            "Normal state — calendar spreads (sell near, buy far) have edge."
        )
    else:
        structure = "flat"
        signal = "neutral"
        explanation = "Term structure is flat — no strong directional signal."

    return {
        "near_vix": near_vix,
        "far_vix": far_vix,
        "spread": round(spread, 2),
        "ratio": round(ratio, 3),
        "structure": structure,
        "signal": signal,
        "explanation": explanation,
    }
