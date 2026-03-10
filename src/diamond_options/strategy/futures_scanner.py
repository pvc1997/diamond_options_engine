"""Futures signal scanner — market condition scoring and strategy selection.

Analyzes current market conditions (basis, VIX, trend, OI buildup, rollover)
and scores each futures strategy's suitability. Returns ranked recommendations.

Scoring (0-100):
- Trend alignment: 30 pts
- Basis regime: 20 pts
- VIX alignment: 15 pts
- OI buildup signal: 15 pts
- Rollover signal: 10 pts
- DTE alignment: 10 pts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from diamond_options.strategy.futures_strategies import (
    FUTURES_STRATEGIES,
    FuturesOutlook,
    FuturesRiskProfile,
    FuturesStrategyCategory,
    FuturesStrategySpec,
)


class TrendDirection(str, Enum):
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


class OIBuildupSignal(str, Enum):
    """OI buildup interpretation (price + OI change)."""

    LONG_BUILDUP = "long_buildup"  # Price up + OI up
    SHORT_BUILDUP = "short_buildup"  # Price down + OI up
    LONG_UNWINDING = "long_unwinding"  # Price down + OI down
    SHORT_COVERING = "short_covering"  # Price up + OI down
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class FuturesMarketCondition:
    """Snapshot of current market conditions for futures signal generation."""

    spot: float
    near_futures: float  # Near-month futures price
    next_futures: float  # Next-month futures price (0 if unavailable)
    basis_pct: float  # Near-month basis as % of spot
    annualized_basis: float  # Annualized cost of carry (%)
    vix: float
    trend: TrendDirection
    realized_vol: float  # Recent realized vol (annualized)
    days_to_expiry: int  # DTE for near-month
    oi_buildup: OIBuildupSignal = OIBuildupSignal.NEUTRAL
    rollover_pct: float = 0.0  # % of OI in next month (0-100)
    basis_z_score: float = 0.0  # Current basis vs. historical
    volume_ratio: float = 1.0  # Today's volume / avg volume


@dataclass(frozen=True)
class FuturesStrategySignal:
    """A scored futures strategy recommendation."""

    strategy: FuturesStrategySpec
    score: int  # 0-100
    confidence: str  # "high", "moderate", "weak", "avoid"
    reasons: list[str]


def _vix_regime(vix: float) -> str:
    if vix < 12:
        return "low"
    elif vix < 18:
        return "normal"
    elif vix < 25:
        return "elevated"
    elif vix < 35:
        return "high"
    return "crisis"


def _score_trend(
    strategy: FuturesStrategySpec, trend: TrendDirection,
) -> tuple[int, str]:
    """Score trend alignment (max 30)."""
    bullish = {TrendDirection.BULLISH, TrendDirection.STRONG_BULLISH}
    bearish = {TrendDirection.BEARISH, TrendDirection.STRONG_BEARISH}

    if strategy.outlook == FuturesOutlook.BULLISH:
        if trend in bullish:
            return 30, f"Trend {trend.value} — strong alignment for bullish strategy"
        if trend == TrendDirection.NEUTRAL:
            return 10, "Neutral trend — mild support for bullish"
        return -10, f"Trend {trend.value} — conflicts with bullish strategy"

    if strategy.outlook == FuturesOutlook.BEARISH:
        if trend in bearish:
            return 30, f"Trend {trend.value} — strong alignment for bearish strategy"
        if trend == TrendDirection.NEUTRAL:
            return 10, "Neutral trend — mild support for bearish"
        return -10, f"Trend {trend.value} — conflicts with bearish strategy"

    if strategy.outlook == FuturesOutlook.NEUTRAL:
        if trend == TrendDirection.NEUTRAL:
            return 25, "Neutral trend — ideal for market-neutral strategy"
        if trend in {TrendDirection.BULLISH, TrendDirection.BEARISH}:
            return 10, "Mild trend — acceptable for neutral strategy"
        return -5, f"Strong trend {trend.value} — risky for neutral strategy"

    # Carry strategies work in any trend
    if strategy.outlook == FuturesOutlook.CARRY:
        return 15, "Carry strategies are trend-agnostic"

    return 10, "Trend neutral for this strategy"


def _score_basis(
    strategy: FuturesStrategySpec, basis_pct: float, basis_z_score: float,
) -> tuple[int, str]:
    """Score basis regime alignment (max 20)."""
    is_contango = basis_pct > 0.05
    is_backwardation = basis_pct < -0.05

    ideal = strategy.ideal_basis_regime

    if ideal == "any":
        return 10, f"Basis {basis_pct:.3f}% — acceptable for this strategy"

    if ideal == "contango":
        if is_contango:
            score = 20 if basis_z_score > 1.0 else 15
            return score, f"Contango {basis_pct:.3f}% (z={basis_z_score:.1f}) — ideal"
        if not is_backwardation:
            return 5, f"Basis near flat ({basis_pct:.3f}%) — marginal for contango strategy"
        return -10, f"Backwardation {basis_pct:.3f}% — wrong regime for contango strategy"

    if ideal == "backwardation":
        if is_backwardation:
            score = 20 if basis_z_score < -1.0 else 15
            return score, f"Backwardation {basis_pct:.3f}% (z={basis_z_score:.1f}) — ideal"
        if not is_contango:
            return 5, f"Basis near flat ({basis_pct:.3f}%) — marginal"
        return -10, f"Contango {basis_pct:.3f}% — wrong regime"

    return 10, f"Basis {basis_pct:.3f}%"


def _score_vix(
    strategy: FuturesStrategySpec, vix: float,
) -> tuple[int, str]:
    """Score VIX regime alignment (max 15)."""
    regime = _vix_regime(vix)
    if regime in strategy.ideal_vix_regime:
        return 15, f"VIX {vix:.1f} ({regime}) — suits {strategy.name}"
    return -5, f"VIX {vix:.1f} ({regime}) — not ideal for {strategy.name}"


def _score_oi_buildup(
    strategy: FuturesStrategySpec, oi_signal: OIBuildupSignal,
) -> tuple[int, str]:
    """Score OI buildup alignment (max 15)."""
    if oi_signal == OIBuildupSignal.NEUTRAL:
        return 5, "No clear OI signal"

    if strategy.outlook == FuturesOutlook.BULLISH:
        if oi_signal == OIBuildupSignal.LONG_BUILDUP:
            return 15, "Long buildup — smart money going long"
        if oi_signal == OIBuildupSignal.SHORT_COVERING:
            return 10, "Short covering — bullish momentum"
        if oi_signal == OIBuildupSignal.SHORT_BUILDUP:
            return -5, "Short buildup — contradicts bullish view"
        return 0, f"OI signal {oi_signal.value}"

    if strategy.outlook == FuturesOutlook.BEARISH:
        if oi_signal == OIBuildupSignal.SHORT_BUILDUP:
            return 15, "Short buildup — confirms bearish view"
        if oi_signal == OIBuildupSignal.LONG_UNWINDING:
            return 10, "Long unwinding — bearish momentum"
        if oi_signal == OIBuildupSignal.LONG_BUILDUP:
            return -5, "Long buildup — contradicts bearish view"
        return 0, f"OI signal {oi_signal.value}"

    # Neutral/carry strategies
    return 5, f"OI signal {oi_signal.value} — minor factor for this strategy"


def _score_rollover(
    strategy: FuturesStrategySpec,
    rollover_pct: float,
    dte: int,
) -> tuple[int, str]:
    """Score rollover signal (max 10)."""
    # Rollover is most relevant near expiry
    if dte > 10:
        return 5, "Not near expiry — rollover signal less relevant"

    if strategy.slug == "futures_rollover":
        if rollover_pct < 30:
            return 10, f"Low rollover {rollover_pct:.0f}% — time to roll"
        return 5, f"Rollover at {rollover_pct:.0f}% — monitor"

    # For directional strategies, high rollover = continuation
    if strategy.outlook in (FuturesOutlook.BULLISH, FuturesOutlook.BEARISH):
        if rollover_pct > 60:
            return 10, f"High rollover {rollover_pct:.0f}% — position continuation signal"
        if rollover_pct < 30:
            return 0, f"Low rollover {rollover_pct:.0f}% — traders closing, not rolling"
        return 5, f"Moderate rollover {rollover_pct:.0f}%"

    return 5, f"Rollover at {rollover_pct:.0f}%"


def _score_dte(
    strategy: FuturesStrategySpec, dte: int,
) -> tuple[int, str]:
    """Score DTE alignment (max 10)."""
    min_dte, max_dte = strategy.ideal_dte_range
    if min_dte <= dte <= max_dte:
        return 10, f"{dte} DTE — in ideal range ({min_dte}-{max_dte})"
    # Within 50% of range
    range_width = max_dte - min_dte
    if range_width > 0:
        if dte < min_dte and (min_dte - dte) <= range_width * 0.5:
            return 5, f"{dte} DTE — slightly early for {strategy.name}"
        if dte > max_dte and (dte - max_dte) <= range_width * 0.5:
            return 5, f"{dte} DTE — slightly late for {strategy.name}"
    return 0, f"{dte} DTE — outside ideal range ({min_dte}-{max_dte})"


def score_futures_strategy(
    strategy: FuturesStrategySpec,
    condition: FuturesMarketCondition,
) -> FuturesStrategySignal:
    """Score a single futures strategy against current conditions.

    Scoring (max 100):
    - Trend: 30
    - Basis: 20
    - VIX: 15
    - OI buildup: 15
    - Rollover: 10
    - DTE: 10
    """
    reasons: list[str] = []
    total = 0

    scorers = [
        lambda: _score_trend(strategy, condition.trend),
        lambda: _score_basis(strategy, condition.basis_pct, condition.basis_z_score),
        lambda: _score_vix(strategy, condition.vix),
        lambda: _score_oi_buildup(strategy, condition.oi_buildup),
        lambda: _score_rollover(strategy, condition.rollover_pct, condition.days_to_expiry),
        lambda: _score_dte(strategy, condition.days_to_expiry),
    ]

    for scorer in scorers:
        pts, reason = scorer()
        total += pts
        reasons.append(reason)

    score = max(0, min(100, total))

    if score >= 75:
        confidence = "high"
    elif score >= 55:
        confidence = "moderate"
    elif score >= 35:
        confidence = "weak"
    else:
        confidence = "avoid"

    return FuturesStrategySignal(
        strategy=strategy,
        score=score,
        confidence=confidence,
        reasons=reasons,
    )


def scan_futures_strategies(
    condition: FuturesMarketCondition,
    min_score: int = 35,
    max_results: int = 5,
    category: FuturesStrategyCategory | None = None,
    defined_risk_only: bool = False,
) -> list[FuturesStrategySignal]:
    """Scan all futures strategies and return ranked recommendations.

    Args:
        condition: Current market snapshot.
        min_score: Minimum quality score to include.
        max_results: Maximum strategies to return.
        category: Filter by category.
        defined_risk_only: Only include defined/low-risk strategies.

    Returns:
        List of FuturesStrategySignal sorted by score descending.
    """
    candidates = list(FUTURES_STRATEGIES.values())

    if category:
        candidates = [s for s in candidates if s.category == category]
    if defined_risk_only:
        candidates = [
            s for s in candidates
            if s.risk_profile in (FuturesRiskProfile.DEFINED, FuturesRiskProfile.LOW_RISK)
        ]

    signals = [score_futures_strategy(s, condition) for s in candidates]
    signals = [s for s in signals if s.score >= min_score]
    signals.sort(key=lambda s: s.score, reverse=True)

    return signals[:max_results]


def classify_oi_buildup(
    price_change_pct: float,
    oi_change_pct: float,
    threshold: float = 0.5,
) -> OIBuildupSignal:
    """Classify OI change into buildup categories.

    Args:
        price_change_pct: Price change from previous close (%).
        oi_change_pct: OI change from previous day (%).
        threshold: Minimum change to classify (%).

    Returns:
        OIBuildupSignal classification.
    """
    if abs(price_change_pct) < threshold and abs(oi_change_pct) < threshold:
        return OIBuildupSignal.NEUTRAL

    price_up = price_change_pct > threshold
    price_down = price_change_pct < -threshold
    oi_up = oi_change_pct > threshold
    oi_down = oi_change_pct < -threshold

    if price_up and oi_up:
        return OIBuildupSignal.LONG_BUILDUP
    if price_down and oi_up:
        return OIBuildupSignal.SHORT_BUILDUP
    if price_down and oi_down:
        return OIBuildupSignal.LONG_UNWINDING
    if price_up and oi_down:
        return OIBuildupSignal.SHORT_COVERING

    return OIBuildupSignal.NEUTRAL
