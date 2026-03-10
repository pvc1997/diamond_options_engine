"""Tests for futures strategy scanner."""

import pytest

from diamond_options.strategy.futures_scanner import (
    FuturesMarketCondition,
    FuturesStrategySignal,
    OIBuildupSignal,
    TrendDirection,
    classify_oi_buildup,
    scan_futures_strategies,
    score_futures_strategy,
)
from diamond_options.strategy.futures_strategies import (
    FuturesStrategyCategory,
    get_futures_strategy,
)


@pytest.fixture
def bullish_condition() -> FuturesMarketCondition:
    return FuturesMarketCondition(
        spot=22500.0,
        near_futures=22650.0,
        next_futures=22750.0,
        basis_pct=0.667,
        annualized_basis=8.1,
        vix=15.0,
        trend=TrendDirection.BULLISH,
        realized_vol=0.14,
        days_to_expiry=20,
        oi_buildup=OIBuildupSignal.LONG_BUILDUP,
        rollover_pct=25.0,
    )


@pytest.fixture
def bearish_condition() -> FuturesMarketCondition:
    return FuturesMarketCondition(
        spot=22500.0,
        near_futures=22400.0,
        next_futures=22350.0,
        basis_pct=-0.444,
        annualized_basis=-5.4,
        vix=28.0,
        trend=TrendDirection.STRONG_BEARISH,
        realized_vol=0.22,
        days_to_expiry=15,
        oi_buildup=OIBuildupSignal.SHORT_BUILDUP,
        rollover_pct=40.0,
    )


@pytest.fixture
def neutral_condition() -> FuturesMarketCondition:
    return FuturesMarketCondition(
        spot=22500.0,
        near_futures=22530.0,
        next_futures=22580.0,
        basis_pct=0.133,
        annualized_basis=2.4,
        vix=14.0,
        trend=TrendDirection.NEUTRAL,
        realized_vol=0.12,
        days_to_expiry=25,
        oi_buildup=OIBuildupSignal.NEUTRAL,
    )


class TestScoreFuturesStrategy:
    def test_long_futures_bullish(self, bullish_condition):
        strategy = get_futures_strategy("long_futures")
        signal = score_futures_strategy(strategy, bullish_condition)
        assert signal.score >= 60
        assert signal.confidence in ("high", "moderate")

    def test_long_futures_bearish(self, bearish_condition):
        strategy = get_futures_strategy("long_futures")
        signal = score_futures_strategy(strategy, bearish_condition)
        assert signal.score < 40  # Should score poorly

    def test_short_futures_bearish(self, bearish_condition):
        strategy = get_futures_strategy("short_futures")
        signal = score_futures_strategy(strategy, bearish_condition)
        assert signal.score >= 50

    def test_pair_trade_neutral(self, neutral_condition):
        strategy = get_futures_strategy("pair_trade")
        signal = score_futures_strategy(strategy, neutral_condition)
        assert signal.score >= 40

    def test_calendar_spread_contango(self, bullish_condition):
        strategy = get_futures_strategy("calendar_spread_bull")
        signal = score_futures_strategy(strategy, bullish_condition)
        assert signal.score >= 30  # Should like contango

    def test_has_reasons(self, bullish_condition):
        strategy = get_futures_strategy("long_futures")
        signal = score_futures_strategy(strategy, bullish_condition)
        assert len(signal.reasons) == 6  # 6 scoring components

    def test_score_clamped_0_100(self, bullish_condition):
        for slug in ["long_futures", "short_futures", "pair_trade",
                      "calendar_spread_bull", "cash_futures_arb"]:
            strategy = get_futures_strategy(slug)
            signal = score_futures_strategy(strategy, bullish_condition)
            assert 0 <= signal.score <= 100

    def test_confidence_mapping(self, bullish_condition):
        strategy = get_futures_strategy("long_futures")
        signal = score_futures_strategy(strategy, bullish_condition)
        if signal.score >= 75:
            assert signal.confidence == "high"
        elif signal.score >= 55:
            assert signal.confidence == "moderate"
        elif signal.score >= 35:
            assert signal.confidence == "weak"
        else:
            assert signal.confidence == "avoid"


class TestScanFuturesStrategies:
    def test_returns_ranked(self, bullish_condition):
        signals = scan_futures_strategies(bullish_condition)
        assert len(signals) > 0
        # Should be sorted by score descending
        for i in range(len(signals) - 1):
            assert signals[i].score >= signals[i + 1].score

    def test_max_results(self, bullish_condition):
        signals = scan_futures_strategies(bullish_condition, max_results=2)
        assert len(signals) <= 2

    def test_min_score_filter(self, bullish_condition):
        signals = scan_futures_strategies(bullish_condition, min_score=60)
        for s in signals:
            assert s.score >= 60

    def test_category_filter(self, bullish_condition):
        signals = scan_futures_strategies(
            bullish_condition,
            category=FuturesStrategyCategory.DIRECTIONAL,
        )
        for s in signals:
            assert s.strategy.category == FuturesStrategyCategory.DIRECTIONAL

    def test_defined_risk_only(self, bullish_condition):
        signals = scan_futures_strategies(
            bullish_condition, defined_risk_only=True,
        )
        for s in signals:
            assert s.strategy.risk_profile.value in ("defined", "low_risk")

    def test_bearish_market_prefers_short(self, bearish_condition):
        signals = scan_futures_strategies(bearish_condition, max_results=10)
        if signals:
            # Short futures or hedge should score well in bearish
            top_slugs = {s.strategy.slug for s in signals[:3]}
            bearish_slugs = {"short_futures", "index_futures_hedge",
                            "stock_futures_hedge", "synthetic_short"}
            assert top_slugs & bearish_slugs  # At least one bearish strategy in top 3


class TestClassifyOIBuildup:
    def test_long_buildup(self):
        assert classify_oi_buildup(1.5, 3.0) == OIBuildupSignal.LONG_BUILDUP

    def test_short_buildup(self):
        assert classify_oi_buildup(-1.5, 3.0) == OIBuildupSignal.SHORT_BUILDUP

    def test_long_unwinding(self):
        assert classify_oi_buildup(-1.5, -3.0) == OIBuildupSignal.LONG_UNWINDING

    def test_short_covering(self):
        assert classify_oi_buildup(1.5, -3.0) == OIBuildupSignal.SHORT_COVERING

    def test_neutral_small_changes(self):
        assert classify_oi_buildup(0.1, 0.1) == OIBuildupSignal.NEUTRAL

    def test_custom_threshold(self):
        assert classify_oi_buildup(0.3, 0.3, threshold=0.5) == OIBuildupSignal.NEUTRAL
        assert classify_oi_buildup(0.6, 0.6, threshold=0.5) == OIBuildupSignal.LONG_BUILDUP
