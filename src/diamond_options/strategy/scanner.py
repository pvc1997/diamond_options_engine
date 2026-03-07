"""Signal scanner — market condition scoring and strategy selection.

Analyzes current market conditions (VIX, IV rank, trend, support/resistance)
and scores each strategy's suitability. Returns ranked recommendations with
confidence scores.

Signal Quality Score (0-100):
- 80-100: High confidence — strong alignment across all factors
- 60-79: Moderate — most factors align
- 40-59: Weak — mixed signals
- 0-39: Avoid — conditions don't suit this strategy
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from diamond_options.strategy.definitions import (
    STRATEGIES,
    StrategyCategory,
    StrategySpec,
    MarketOutlook,
    strategies_for_regime,
)


class TrendDirection(str, Enum):
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


@dataclass(frozen=True)
class MarketCondition:
    """Snapshot of current market conditions for signal generation."""
    spot: float
    vix: float                             # India VIX value
    iv_rank: float                         # IV rank 0-100
    iv_percentile: float                   # IV percentile 0-100
    trend: TrendDirection                  # Price trend
    realized_vol: float                    # Recent realized volatility
    implied_vol: float                     # Current ATM IV
    days_to_expiry: int                    # DTE for target expiry
    pcr_oi: float = 1.0                    # Put-call ratio by OI
    support: float = 0.0                   # Nearest support level
    resistance: float = 0.0               # Nearest resistance level
    max_pain: float = 0.0                 # Max pain strike


@dataclass(frozen=True)
class StrategySignal:
    """A scored strategy recommendation."""
    strategy: StrategySpec
    score: int                             # 0-100 quality score
    confidence: str                        # "high", "moderate", "weak", "avoid"
    reasons: list[str]                     # Why this strategy scored well/poorly
    suggested_strikes: dict = field(default_factory=dict)  # Suggested strike selection
    expected_edge: str = ""                # e.g., "Positive VRP: options overpriced by 3%"


def _score_iv_alignment(strategy: StrategySpec, iv_rank: float) -> tuple[int, str]:
    """Score how well IV conditions match the strategy."""
    if strategy.ideal_iv == "any":
        return 10, "IV conditions neutral for this strategy"

    if strategy.ideal_iv == "high":
        if iv_rank > 70:
            return 25, f"IV rank {iv_rank:.0f} — excellent for premium selling"
        elif iv_rank > 50:
            return 15, f"IV rank {iv_rank:.0f} — adequate for premium selling"
        elif iv_rank > 30:
            return 5, f"IV rank {iv_rank:.0f} — mediocre for premium selling"
        else:
            return -5, f"IV rank {iv_rank:.0f} — poor for premium selling, premiums are cheap"

    if strategy.ideal_iv == "low":
        if iv_rank < 30:
            return 25, f"IV rank {iv_rank:.0f} — options are cheap, good for buying"
        elif iv_rank < 50:
            return 15, f"IV rank {iv_rank:.0f} — reasonable for buying premium"
        else:
            return 0, f"IV rank {iv_rank:.0f} — options expensive, risky to buy premium"

    return 10, "IV conditions neutral"


def _score_vix_alignment(strategy: StrategySpec, vix: float) -> tuple[int, str]:
    """Score VIX regime alignment."""
    if vix < 12:
        regime = "low"
    elif vix < 18:
        regime = "normal"
    elif vix < 25:
        regime = "elevated"
    elif vix < 35:
        regime = "high"
    else:
        regime = "crisis"

    if regime in strategy.vix_regimes:
        return 20, f"VIX {vix:.1f} ({regime}) — suits {strategy.name}"
    else:
        return -5, f"VIX {vix:.1f} ({regime}) — not ideal for {strategy.name}"


def _score_trend_alignment(strategy: StrategySpec, trend: TrendDirection) -> tuple[int, str]:
    """Score trend-strategy alignment."""
    bullish_trends = {TrendDirection.BULLISH, TrendDirection.STRONG_BULLISH}
    bearish_trends = {TrendDirection.BEARISH, TrendDirection.STRONG_BEARISH}

    if strategy.outlook == MarketOutlook.BULLISH:
        if trend in bullish_trends:
            return 20, f"Trend is {trend.value} — aligns with bullish strategy"
        elif trend == TrendDirection.NEUTRAL:
            return 5, "Trend is neutral — mild support for bullish strategy"
        else:
            return -10, f"Trend is {trend.value} — conflicts with bullish strategy"

    elif strategy.outlook == MarketOutlook.BEARISH:
        if trend in bearish_trends:
            return 20, f"Trend is {trend.value} — aligns with bearish strategy"
        elif trend == TrendDirection.NEUTRAL:
            return 5, "Trend is neutral — mild support for bearish strategy"
        else:
            return -10, f"Trend is {trend.value} — conflicts with bearish strategy"

    elif strategy.outlook == MarketOutlook.NEUTRAL:
        if trend == TrendDirection.NEUTRAL:
            return 20, "Trend is neutral — ideal for range-bound strategies"
        elif trend in {TrendDirection.BULLISH, TrendDirection.BEARISH}:
            return 5, f"Trend is mildly {trend.value} — still workable for neutral strategy"
        else:
            return -10, f"Trend is {trend.value} — too directional for neutral strategy"

    elif strategy.outlook == MarketOutlook.VOL_UP:
        if trend in {TrendDirection.STRONG_BULLISH, TrendDirection.STRONG_BEARISH}:
            return 15, "Strong trend — supports vol expansion thesis"
        return 5, "Moderate or no trend — vol expansion needs a catalyst"

    elif strategy.outlook == MarketOutlook.VOL_DOWN:
        if trend == TrendDirection.NEUTRAL:
            return 15, "Neutral trend — supports vol contraction"
        return 5, "Directional trend may sustain vol"

    return 10, "Trend alignment neutral"


def _score_vrp(strategy: StrategySpec, iv: float, rv: float) -> tuple[int, str]:
    """Score variance risk premium alignment."""
    vrp = iv - rv
    vrp_pct = (vrp / rv * 100) if rv > 0 else 0

    sells_premium = strategy.ideal_iv == "high" or "income" in strategy.tags
    buys_premium = strategy.ideal_iv == "low"

    if sells_premium:
        if vrp > 0.03:
            return 15, f"VRP +{vrp_pct:.0f}% — options overpriced, edge for sellers"
        elif vrp > 0:
            return 8, f"VRP +{vrp_pct:.0f}% — slight edge for sellers"
        else:
            return -5, f"VRP {vrp_pct:.0f}% — options cheap, no edge for sellers"

    elif buys_premium:
        if vrp < -0.02:
            return 15, f"VRP {vrp_pct:.0f}% — options underpriced, good for buyers"
        elif vrp < 0.02:
            return 8, f"VRP {vrp_pct:.0f}% — options fairly priced"
        else:
            return -5, f"VRP +{vrp_pct:.0f}% — options overpriced, risky for buyers"

    return 5, f"VRP {vrp_pct:.0f}% — neutral for this strategy"


def _score_dte(strategy: StrategySpec, dte: int) -> tuple[int, str]:
    """Score days-to-expiry alignment."""
    if strategy.ideal_dte == "any":
        return 5, f"{dte} DTE — acceptable"

    if strategy.ideal_dte == "weekly":
        if dte <= 7:
            return 10, f"{dte} DTE — ideal for weekly strategy"
        elif dte <= 14:
            return 5, f"{dte} DTE — acceptable for weekly strategy"
        else:
            return 0, f"{dte} DTE — too far out for a weekly strategy"

    if strategy.ideal_dte == "monthly":
        if 21 <= dte <= 45:
            return 10, f"{dte} DTE — ideal for monthly strategy (30-45 DTE sweet spot)"
        elif 14 <= dte <= 60:
            return 5, f"{dte} DTE — acceptable for monthly strategy"
        else:
            return 0, f"{dte} DTE — not in optimal range for monthly strategy"

    if strategy.ideal_dte == "45dte":
        if 35 <= dte <= 55:
            return 10, f"{dte} DTE — ideal 45 DTE window"
        elif 21 <= dte <= 60:
            return 5, f"{dte} DTE — close to ideal"
        else:
            return 0, f"{dte} DTE — outside 45 DTE window"

    return 5, f"{dte} DTE"


def score_strategy(
    strategy: StrategySpec,
    condition: MarketCondition,
) -> StrategySignal:
    """Score a single strategy against current market conditions.

    Scoring components (max 100):
    - IV alignment: up to 25
    - VIX regime: up to 20
    - Trend alignment: up to 20
    - VRP edge: up to 15
    - DTE fit: up to 10
    - Base score: 10

    Minimum score is 0.
    """
    reasons: list[str] = []
    total = 10  # Base score

    for scorer in [
        lambda: _score_iv_alignment(strategy, condition.iv_rank),
        lambda: _score_vix_alignment(strategy, condition.vix),
        lambda: _score_trend_alignment(strategy, condition.trend),
        lambda: _score_vrp(strategy, condition.implied_vol, condition.realized_vol),
        lambda: _score_dte(strategy, condition.days_to_expiry),
    ]:
        pts, reason = scorer()
        total += pts
        reasons.append(reason)

    score = max(0, min(100, total))

    if score >= 80:
        confidence = "high"
    elif score >= 60:
        confidence = "moderate"
    elif score >= 40:
        confidence = "weak"
    else:
        confidence = "avoid"

    # Build expected edge description
    vrp = condition.implied_vol - condition.realized_vol
    edge = ""
    if vrp > 0.02 and strategy.ideal_iv == "high":
        edge = f"Positive VRP: options overpriced by {vrp*100:.1f}% vol"
    elif vrp < -0.02 and strategy.ideal_iv == "low":
        edge = f"Negative VRP: options underpriced by {abs(vrp)*100:.1f}% vol"

    return StrategySignal(
        strategy=strategy,
        score=score,
        confidence=confidence,
        reasons=reasons,
        expected_edge=edge,
    )


def scan_strategies(
    condition: MarketCondition,
    min_score: int = 40,
    max_results: int = 5,
    category: StrategyCategory | None = None,
    defined_risk_only: bool = False,
) -> list[StrategySignal]:
    """Scan all strategies and return ranked recommendations.

    Args:
        condition: Current market snapshot.
        min_score: Minimum quality score to include (0-100).
        max_results: Maximum strategies to return.
        category: Filter by strategy category.
        defined_risk_only: Only include defined-risk strategies.

    Returns:
        List of StrategySignal sorted by score descending.
    """
    from diamond_options.strategy.definitions import RiskProfile

    candidates = list(STRATEGIES.values())

    if category:
        candidates = [s for s in candidates if s.category == category]
    if defined_risk_only:
        candidates = [s for s in candidates if s.risk_profile == RiskProfile.DEFINED]

    signals = [score_strategy(s, condition) for s in candidates]
    signals = [s for s in signals if s.score >= min_score]
    signals.sort(key=lambda s: s.score, reverse=True)

    return signals[:max_results]


def suggest_strikes(
    strategy_slug: str,
    spot: float,
    step: float = 50.0,
    otm_distance: int = 2,
) -> dict:
    """Suggest strike prices for a strategy based on spot price.

    Uses standard OTM distance conventions for Indian markets.

    Args:
        strategy_slug: Strategy identifier.
        spot: Current spot price.
        step: Strike step size (50 for NIFTY, 100 for BANKNIFTY).
        otm_distance: Number of strikes OTM for wings.

    Returns:
        Dict with suggested strike prices for each leg.
    """
    atm = round(spot / step) * step
    otm_up = atm + step * otm_distance
    otm_down = atm - step * otm_distance
    wing_up = atm + step * (otm_distance + 2)
    wing_down = atm - step * (otm_distance + 2)

    suggestions = {
        "long_call": {"strike": atm},
        "long_put": {"strike": atm},
        "bull_call_spread": {"lower_strike": atm, "upper_strike": otm_up},
        "bear_put_spread": {"upper_strike": atm, "lower_strike": otm_down},
        "bull_put_spread": {"upper_strike": otm_down + step, "lower_strike": otm_down},
        "bear_call_spread": {"lower_strike": otm_up - step, "upper_strike": otm_up},
        "short_straddle": {"strike": atm},
        "long_straddle": {"strike": atm},
        "short_strangle": {"call_strike": otm_up, "put_strike": otm_down},
        "long_strangle": {"call_strike": otm_up, "put_strike": otm_down},
        "iron_condor": {
            "put_buy_strike": wing_down,
            "put_sell_strike": otm_down,
            "call_sell_strike": otm_up,
            "call_buy_strike": wing_up,
        },
        "iron_butterfly": {
            "strike": atm,
            "put_wing": otm_down,
            "call_wing": otm_up,
        },
        "ratio_spread": {"buy_strike": atm, "sell_strike": otm_up},
        "jade_lizard": {
            "put_strike": otm_down,
            "call_sell_strike": otm_up,
            "call_buy_strike": wing_up,
        },
        "collar": {"put_strike": otm_down, "call_strike": otm_up},
    }

    result = suggestions.get(strategy_slug, {})
    result["atm"] = atm
    result["step"] = step
    return result
