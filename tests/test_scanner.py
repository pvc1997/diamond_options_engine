"""Tests for signal scanner and strategy scoring."""

import pytest

from diamond_options.strategy.scanner import (
    MarketCondition,
    TrendDirection,
    StrategySignal,
    score_strategy,
    scan_strategies,
    suggest_strikes,
)
from diamond_options.strategy.definitions import (
    STRATEGIES,
    StrategyCategory,
    get_strategy,
)


@pytest.fixture
def high_iv_neutral():
    """High IV, neutral trend — ideal for premium selling."""
    return MarketCondition(
        spot=22500, vix=22.0, iv_rank=80, iv_percentile=85,
        trend=TrendDirection.NEUTRAL,
        realized_vol=0.12, implied_vol=0.18,
        days_to_expiry=7,
    )


@pytest.fixture
def low_iv_bullish():
    """Low IV, bullish trend — ideal for buying calls."""
    return MarketCondition(
        spot=22500, vix=11.0, iv_rank=15, iv_percentile=10,
        trend=TrendDirection.BULLISH,
        realized_vol=0.10, implied_vol=0.09,
        days_to_expiry=30,
    )


@pytest.fixture
def crisis_condition():
    """Crisis VIX — hedge-only mode."""
    return MarketCondition(
        spot=20000, vix=40.0, iv_rank=95, iv_percentile=98,
        trend=TrendDirection.STRONG_BEARISH,
        realized_vol=0.30, implied_vol=0.45,
        days_to_expiry=7,
    )


class TestScoring:
    def test_iron_condor_high_iv_neutral(self, high_iv_neutral):
        """Iron condor should score well in high IV neutral market."""
        ic = get_strategy("iron_condor")
        signal = score_strategy(ic, high_iv_neutral)
        assert signal.score >= 60
        assert signal.confidence in ("high", "moderate")

    def test_long_call_high_iv_neutral(self, high_iv_neutral):
        """Long call should score poorly in high IV neutral market."""
        lc = get_strategy("long_call")
        signal = score_strategy(lc, high_iv_neutral)
        assert signal.score < 50  # Not ideal conditions

    def test_long_call_low_iv_bullish(self, low_iv_bullish):
        """Long call should score well in low IV bullish market."""
        lc = get_strategy("long_call")
        signal = score_strategy(lc, low_iv_bullish)
        assert signal.score >= 50

    def test_short_straddle_crisis(self, crisis_condition):
        """Short straddle should score poorly in crisis."""
        ss = get_strategy("short_straddle")
        signal = score_strategy(ss, crisis_condition)
        # Crisis VIX regime doesn't include short straddle
        assert signal.score < 60

    def test_score_range(self, high_iv_neutral):
        """All scores should be 0-100."""
        for slug, spec in STRATEGIES.items():
            signal = score_strategy(spec, high_iv_neutral)
            assert 0 <= signal.score <= 100, f"{slug} score {signal.score} out of range"

    def test_signal_has_reasons(self, high_iv_neutral):
        """Every signal should have reasons."""
        ic = get_strategy("iron_condor")
        signal = score_strategy(ic, high_iv_neutral)
        assert len(signal.reasons) >= 3

    def test_confidence_levels(self, high_iv_neutral):
        """Confidence should correspond to score ranges."""
        for spec in STRATEGIES.values():
            signal = score_strategy(spec, high_iv_neutral)
            if signal.score >= 80:
                assert signal.confidence == "high"
            elif signal.score >= 60:
                assert signal.confidence == "moderate"
            elif signal.score >= 40:
                assert signal.confidence == "weak"
            else:
                assert signal.confidence == "avoid"


class TestScanStrategies:
    def test_returns_ranked_list(self, high_iv_neutral):
        """Should return strategies sorted by score descending."""
        signals = scan_strategies(high_iv_neutral, min_score=0, max_results=10)
        assert len(signals) > 0
        for i in range(len(signals) - 1):
            assert signals[i].score >= signals[i + 1].score

    def test_min_score_filter(self, high_iv_neutral):
        """Should filter out low-scoring strategies."""
        signals = scan_strategies(high_iv_neutral, min_score=60)
        for s in signals:
            assert s.score >= 60

    def test_max_results(self, high_iv_neutral):
        """Should limit results."""
        signals = scan_strategies(high_iv_neutral, min_score=0, max_results=3)
        assert len(signals) <= 3

    def test_category_filter(self, high_iv_neutral):
        """Should filter by category."""
        signals = scan_strategies(
            high_iv_neutral, min_score=0,
            category=StrategyCategory.NEUTRAL,
        )
        for s in signals:
            assert s.strategy.category == StrategyCategory.NEUTRAL

    def test_defined_risk_only(self, high_iv_neutral):
        """Should exclude undefined risk strategies."""
        signals = scan_strategies(
            high_iv_neutral, min_score=0,
            defined_risk_only=True,
        )
        from diamond_options.strategy.definitions import RiskProfile
        for s in signals:
            assert s.strategy.risk_profile == RiskProfile.DEFINED

    def test_premium_selling_in_high_iv(self, high_iv_neutral):
        """Top strategies in high IV should include premium sellers."""
        signals = scan_strategies(high_iv_neutral, min_score=0, max_results=5)
        # At least one of the top 5 should have ideal_iv="high"
        high_iv_strats = [s for s in signals if s.strategy.ideal_iv == "high"]
        assert len(high_iv_strats) > 0


class TestSuggestStrikes:
    def test_nifty_strikes(self):
        """Should suggest reasonable strikes for NIFTY."""
        strikes = suggest_strikes("iron_condor", 22500, step=50.0)
        assert "put_buy_strike" in strikes
        assert "put_sell_strike" in strikes
        assert "call_sell_strike" in strikes
        assert "call_buy_strike" in strikes
        assert strikes["atm"] == 22500

    def test_banknifty_strikes(self):
        """Should work with different step sizes."""
        strikes = suggest_strikes("short_strangle", 48000, step=100.0)
        assert "call_strike" in strikes
        assert "put_strike" in strikes
        assert strikes["call_strike"] > 48000
        assert strikes["put_strike"] < 48000

    def test_atm_rounding(self):
        """ATM should round to nearest step."""
        strikes = suggest_strikes("long_call", 22530, step=50.0)
        assert strikes["atm"] == 22550  # Rounds to nearest 50
        assert strikes["strike"] == 22550

    def test_all_strategies_have_strikes(self):
        """suggest_strikes should handle all strategies."""
        from diamond_options.strategy.definitions import BUILDERS
        for slug in BUILDERS:
            strikes = suggest_strikes(slug, 22500, step=50.0)
            assert "atm" in strikes
