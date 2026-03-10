"""Tests for futures strategy recommender."""

import pytest

from diamond_options.strategy.futures_recommender import (
    FuturesRecommendation,
    quick_futures_recommendation,
    recommend_futures_trades,
)
from diamond_options.strategy.futures_scanner import (
    FuturesMarketCondition,
    OIBuildupSignal,
    TrendDirection,
    FuturesStrategyCategory,
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
    )


class TestRecommendFuturesTrades:
    def test_returns_recommendations(self, bullish_condition):
        recs = recommend_futures_trades(bullish_condition, symbol="NIFTY")
        assert len(recs) > 0
        assert all(isinstance(r, FuturesRecommendation) for r in recs)

    def test_ranked_by_score(self, bullish_condition):
        recs = recommend_futures_trades(bullish_condition, symbol="NIFTY")
        for i in range(len(recs) - 1):
            assert recs[i].confidence_score >= recs[i + 1].confidence_score

    def test_max_results(self, bullish_condition):
        recs = recommend_futures_trades(
            bullish_condition, symbol="NIFTY", max_results=2,
        )
        assert len(recs) <= 2

    def test_has_entry_target_stop(self, bullish_condition):
        recs = recommend_futures_trades(bullish_condition, symbol="NIFTY")
        for rec in recs:
            assert rec.entry_price > 0
            assert rec.target > 0
            assert rec.stop_loss > 0

    def test_has_sizing(self, bullish_condition):
        recs = recommend_futures_trades(bullish_condition, symbol="NIFTY")
        for rec in recs:
            assert rec.lots >= 1
            assert rec.lot_size > 0
            assert rec.margin_required > 0

    def test_has_risk_reward(self, bullish_condition):
        recs = recommend_futures_trades(bullish_condition, symbol="NIFTY")
        for rec in recs:
            assert rec.risk_reward >= 0
            assert rec.costs > 0
            assert rec.breakeven > 0

    def test_has_rationale(self, bullish_condition):
        recs = recommend_futures_trades(bullish_condition, symbol="NIFTY")
        for rec in recs:
            assert len(rec.rationale) > 20

    def test_defined_risk_only(self, bullish_condition):
        recs = recommend_futures_trades(
            bullish_condition,
            symbol="NIFTY",
            defined_risk_only=True,
        )
        for rec in recs:
            assert rec.strategy.risk_profile.value in ("defined", "low_risk")

    def test_category_filter(self, bullish_condition):
        recs = recommend_futures_trades(
            bullish_condition,
            symbol="NIFTY",
            category=FuturesStrategyCategory.DIRECTIONAL,
        )
        for rec in recs:
            assert rec.strategy.category == FuturesStrategyCategory.DIRECTIONAL

    def test_bearish_recommendations(self, bearish_condition):
        recs = recommend_futures_trades(bearish_condition, symbol="NIFTY")
        assert len(recs) > 0

    def test_small_capital_limits_lots(self, bullish_condition):
        recs = recommend_futures_trades(
            bullish_condition,
            symbol="NIFTY",
            capital=100000.0,  # Small capital
        )
        for rec in recs:
            assert rec.lots >= 1
            # With small capital, should use minimum lots (1)
            assert rec.lots == 1

    def test_stock_futures(self, bullish_condition):
        recs = recommend_futures_trades(
            bullish_condition,
            symbol="RELIANCE",
        )
        for rec in recs:
            assert rec.symbol == "RELIANCE"
            assert rec.lot_size == 250


class TestQuickFuturesRecommendation:
    def test_returns_dicts(self):
        results = quick_futures_recommendation(
            spot=22500.0,
            near_futures=22650.0,
            vix=15.0,
            realized_vol=0.14,
            symbol="NIFTY",
        )
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, dict)
            assert "strategy" in r
            assert "entry_price" in r
            assert "target" in r
            assert "stop_loss" in r
            assert "lots" in r
            assert "margin_required" in r

    def test_with_trend(self):
        results = quick_futures_recommendation(
            spot=22500.0,
            near_futures=22650.0,
            vix=15.0,
            realized_vol=0.14,
            trend="bullish",
        )
        assert len(results) > 0

    def test_with_oi_buildup(self):
        results = quick_futures_recommendation(
            spot=22500.0,
            near_futures=22650.0,
            vix=15.0,
            realized_vol=0.14,
            trend="bullish",
            oi_buildup="long_buildup",
        )
        assert len(results) > 0

    def test_defined_risk_only(self):
        results = quick_futures_recommendation(
            spot=22500.0,
            near_futures=22650.0,
            vix=15.0,
            realized_vol=0.14,
            defined_risk_only=True,
        )
        for r in results:
            assert r["risk_profile"] in ("defined", "low_risk")

    def test_has_all_fields(self):
        results = quick_futures_recommendation(
            spot=22500.0,
            near_futures=22650.0,
            vix=15.0,
            realized_vol=0.14,
        )
        if results:
            r = results[0]
            required_fields = [
                "strategy", "category", "score", "confidence",
                "outlook", "risk_profile", "symbol", "entry_price",
                "target", "stop_loss", "lots", "lot_size",
                "margin_required", "max_loss", "risk_reward",
                "costs", "breakeven", "rationale", "reasons",
            ]
            for field in required_fields:
                assert field in r, f"Missing field: {field}"
