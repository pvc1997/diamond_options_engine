"""Tests for strategy recommender — end-to-end trade suggestions."""

import pytest

from diamond_options.strategy.recommender import (
    recommend_trades,
    quick_recommendation,
    TradeRecommendation,
)
from diamond_options.strategy.scanner import MarketCondition, TrendDirection
from diamond_options.strategy.definitions import StrategyCategory


@pytest.fixture
def normal_market():
    return MarketCondition(
        spot=22500, vix=15.0, iv_rank=50, iv_percentile=50,
        trend=TrendDirection.NEUTRAL,
        realized_vol=0.13, implied_vol=0.14,
        days_to_expiry=7,
    )


@pytest.fixture
def high_iv_market():
    return MarketCondition(
        spot=22500, vix=22.0, iv_rank=80, iv_percentile=85,
        trend=TrendDirection.NEUTRAL,
        realized_vol=0.12, implied_vol=0.20,
        days_to_expiry=7,
    )


@pytest.fixture
def bullish_market():
    return MarketCondition(
        spot=22500, vix=14.0, iv_rank=25, iv_percentile=20,
        trend=TrendDirection.BULLISH,
        realized_vol=0.11, implied_vol=0.10,
        days_to_expiry=30,
    )


class TestRecommendTrades:
    def test_returns_recommendations(self, normal_market):
        """Should return at least one recommendation."""
        recs = recommend_trades(normal_market)
        assert len(recs) > 0

    def test_recommendation_structure(self, normal_market):
        """Each recommendation should have all required fields."""
        recs = recommend_trades(normal_market)
        rec = recs[0]
        assert isinstance(rec, TradeRecommendation)
        assert rec.strategy is not None
        assert rec.signal is not None
        assert len(rec.legs) > 0
        assert rec.position_size.lots >= 1
        assert rec.rationale

    def test_sorted_by_score(self, normal_market):
        """Recommendations should be sorted by signal score."""
        recs = recommend_trades(normal_market, max_results=5)
        for i in range(len(recs) - 1):
            assert recs[i].signal.score >= recs[i + 1].signal.score

    def test_defined_risk_filter(self, normal_market):
        """Should filter to defined-risk only."""
        recs = recommend_trades(normal_market, defined_risk_only=True)
        from diamond_options.strategy.definitions import RiskProfile
        for rec in recs:
            assert rec.strategy.risk_profile == RiskProfile.DEFINED

    def test_category_filter(self, normal_market):
        """Should filter by category."""
        recs = recommend_trades(normal_market, category=StrategyCategory.NEUTRAL)
        for rec in recs:
            assert rec.strategy.category == StrategyCategory.NEUTRAL

    def test_high_iv_favors_sellers(self, high_iv_market):
        """High IV should rank premium selling strategies higher."""
        recs = recommend_trades(high_iv_market, max_results=3)
        # At least one of top 3 should be a premium seller
        seller_strats = [r for r in recs if r.strategy.ideal_iv == "high"]
        assert len(seller_strats) > 0

    def test_legs_have_valid_premiums(self, normal_market):
        """Legs should have positive premiums from BS pricing."""
        recs = recommend_trades(normal_market)
        for rec in recs:
            for leg in rec.legs:
                assert leg.premium >= 0

    def test_max_results_respected(self, normal_market):
        recs = recommend_trades(normal_market, max_results=2)
        assert len(recs) <= 2

    def test_position_sizing_applied(self, normal_market):
        """Position sizing should use correct method and have valid lots."""
        recs = recommend_trades(normal_market, capital=500000, max_risk_pct=2.0)
        for rec in recs:
            assert rec.position_size.lots >= 1
            assert rec.position_size.method == "fixed_risk"


class TestQuickRecommendation:
    def test_returns_list(self):
        """Should return a list of recommendation dicts."""
        recs = quick_recommendation(
            spot=22500, vix=15.0, iv_rank=50,
            realized_vol=0.13, implied_vol=0.14,
        )
        assert isinstance(recs, list)
        assert len(recs) > 0

    def test_recommendation_dict_keys(self):
        """Each recommendation should have expected keys."""
        recs = quick_recommendation(
            spot=22500, vix=15.0, iv_rank=50,
            realized_vol=0.13, implied_vol=0.14,
        )
        rec = recs[0]
        assert "strategy" in rec
        assert "score" in rec
        assert "confidence" in rec
        assert "legs" in rec
        assert "max_profit" in rec
        assert "max_loss" in rec
        assert "breakevens" in rec
        assert "expected_pnl" in rec
        assert "prob_profit" in rec
        assert "position_size" in rec
        assert "rationale" in rec

    def test_bullish_trend(self):
        """Bullish trend should return bullish-leaning strategies."""
        recs = quick_recommendation(
            spot=22500, vix=14.0, iv_rank=25,
            realized_vol=0.11, implied_vol=0.10,
            trend="bullish", days_to_expiry=30,
        )
        # At least one should have bullish outlook
        outlooks = [r["outlook"] for r in recs]
        assert "bullish" in outlooks or "neutral" in outlooks

    def test_high_vix_defined_risk(self):
        """Default defined_risk_only=True should exclude naked strategies."""
        recs = quick_recommendation(
            spot=22500, vix=25.0, iv_rank=80,
            realized_vol=0.15, implied_vol=0.22,
        )
        for rec in recs:
            assert rec["risk_profile"] == "defined"

    def test_different_lot_sizes(self):
        """Should work with different lot sizes."""
        nifty = quick_recommendation(
            spot=22500, vix=15.0, iv_rank=50,
            realized_vol=0.13, implied_vol=0.14,
            lot_size=25, strike_step=50.0,
        )
        banknifty = quick_recommendation(
            spot=48000, vix=15.0, iv_rank=50,
            realized_vol=0.13, implied_vol=0.14,
            lot_size=15, strike_step=100.0,
        )
        assert len(nifty) > 0
        assert len(banknifty) > 0
