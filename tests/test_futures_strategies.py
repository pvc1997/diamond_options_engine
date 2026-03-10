"""Tests for futures strategy definitions."""

import pytest

from diamond_options.strategy.futures_strategies import (
    FUTURES_STRATEGIES,
    FuturesOutlook,
    FuturesRiskProfile,
    FuturesStrategyCategory,
    FuturesStrategySpec,
    futures_strategies_for_regime,
    get_futures_strategy,
    list_futures_strategies,
)


class TestFuturesStrategyCatalog:
    def test_has_strategies(self):
        assert len(FUTURES_STRATEGIES) >= 14

    def test_all_have_slugs(self):
        for slug, spec in FUTURES_STRATEGIES.items():
            assert slug == spec.slug

    def test_all_have_descriptions(self):
        for spec in FUTURES_STRATEGIES.values():
            assert len(spec.description) > 10

    def test_directional_strategies(self):
        directional = list_futures_strategies(
            category=FuturesStrategyCategory.DIRECTIONAL
        )
        slugs = {s.slug for s in directional}
        assert "long_futures" in slugs
        assert "short_futures" in slugs

    def test_spread_strategies(self):
        spreads = list_futures_strategies(
            category=FuturesStrategyCategory.SPREAD
        )
        slugs = {s.slug for s in spreads}
        assert "calendar_spread_bull" in slugs
        assert "calendar_spread_bear" in slugs
        assert "futures_rollover" in slugs

    def test_arbitrage_strategies(self):
        arb = list_futures_strategies(
            category=FuturesStrategyCategory.ARBITRAGE
        )
        slugs = {s.slug for s in arb}
        assert "cash_futures_arb" in slugs
        assert "conversion" in slugs
        assert "reversal" in slugs

    def test_hedge_strategies(self):
        hedge = list_futures_strategies(
            category=FuturesStrategyCategory.HEDGE
        )
        slugs = {s.slug for s in hedge}
        assert "index_futures_hedge" in slugs
        assert "stock_futures_hedge" in slugs
        assert "pair_trade" in slugs

    def test_hybrid_strategies(self):
        hybrid = list_futures_strategies(
            category=FuturesStrategyCategory.HYBRID
        )
        slugs = {s.slug for s in hybrid}
        assert "synthetic_long" in slugs
        assert "synthetic_short" in slugs
        assert "futures_covered_call" in slugs
        assert "futures_protective_put" in slugs

    def test_bullish_strategies(self):
        bullish = list_futures_strategies(outlook=FuturesOutlook.BULLISH)
        assert len(bullish) >= 4
        for s in bullish:
            assert s.outlook == FuturesOutlook.BULLISH

    def test_defined_risk_strategies(self):
        defined = list_futures_strategies(
            risk_profile=FuturesRiskProfile.DEFINED
        )
        assert len(defined) >= 5
        for s in defined:
            assert s.risk_profile == FuturesRiskProfile.DEFINED

    def test_get_strategy(self):
        s = get_futures_strategy("long_futures")
        assert s is not None
        assert s.name == "Long Futures"

    def test_get_nonexistent(self):
        assert get_futures_strategy("nonexistent") is None


class TestFuturesStrategyDetails:
    def test_long_futures(self):
        s = get_futures_strategy("long_futures")
        assert s.category == FuturesStrategyCategory.DIRECTIONAL
        assert s.outlook == FuturesOutlook.BULLISH
        assert s.risk_profile == FuturesRiskProfile.UNLIMITED
        assert s.num_legs == 1
        assert s.margin_type == "full"

    def test_calendar_spread_margin(self):
        s = get_futures_strategy("calendar_spread_bull")
        assert s.margin_type == "spread"
        assert s.risk_profile == FuturesRiskProfile.DEFINED
        assert s.ideal_basis_regime == "contango"

    def test_cash_futures_arb(self):
        s = get_futures_strategy("cash_futures_arb")
        assert s.risk_profile == FuturesRiskProfile.LOW_RISK
        assert s.ideal_basis_regime == "contango"
        assert "crisis" in s.ideal_vix_regime  # Works in all regimes

    def test_dte_ranges(self):
        rollover = get_futures_strategy("futures_rollover")
        assert rollover.ideal_dte_range == (0, 5)

        long_fut = get_futures_strategy("long_futures")
        assert long_fut.ideal_dte_range[0] >= 5


class TestFuturesStrategiesForRegime:
    def test_low_vix(self):
        strategies = futures_strategies_for_regime("low")
        slugs = {s.slug for s in strategies}
        assert "long_futures" in slugs
        assert "cash_futures_arb" in slugs

    def test_crisis_vix(self):
        strategies = futures_strategies_for_regime("crisis")
        slugs = {s.slug for s in strategies}
        assert "cash_futures_arb" in slugs
        assert "index_futures_hedge" in slugs
        # Directional long not recommended in crisis
        assert "long_futures" not in slugs

    def test_elevated_vix(self):
        strategies = futures_strategies_for_regime("elevated")
        # Most strategies work in elevated
        assert len(strategies) >= 8
