"""Tests for strategy definitions and leg builders."""

from diamond_options.strategy.definitions import (
    STRATEGIES,
    BUILDERS,
    StrategyCategory,
    MarketOutlook,
    RiskProfile,
    StrategySpec,
    get_strategy,
    list_strategies,
    strategies_for_regime,
    build_long_call,
    build_long_put,
    build_bull_call_spread,
    build_bear_put_spread,
    build_bull_put_spread,
    build_bear_call_spread,
    build_short_straddle,
    build_long_straddle,
    build_short_strangle,
    build_long_strangle,
    build_iron_condor,
    build_iron_butterfly,
    build_ratio_spread,
    build_jade_lizard,
    build_collar,
)
from diamond_options.pricing.payoff import position_payoff_at_expiry


class TestStrategyCatalog:
    def test_at_least_18_strategies(self):
        """Should have at least 18 strategies defined."""
        assert len(STRATEGIES) >= 18

    def test_all_have_required_fields(self):
        """Every strategy should have all required fields populated."""
        for slug, spec in STRATEGIES.items():
            assert spec.name, f"{slug} missing name"
            assert spec.slug == slug
            assert spec.category in StrategyCategory
            assert spec.outlook in MarketOutlook
            assert spec.risk_profile in RiskProfile
            assert spec.num_legs > 0
            assert spec.description
            assert spec.ideal_iv in ("high", "low", "any")

    def test_all_categories_represented(self):
        """Should have strategies in all categories."""
        categories = {s.category for s in STRATEGIES.values()}
        assert StrategyCategory.DIRECTIONAL in categories
        assert StrategyCategory.NEUTRAL in categories
        assert StrategyCategory.VOLATILITY in categories
        assert StrategyCategory.INCOME in categories
        assert StrategyCategory.HEDGE in categories

    def test_get_strategy(self):
        """Should retrieve by slug."""
        s = get_strategy("iron_condor")
        assert s is not None
        assert s.name == "Iron Condor"
        assert s.num_legs == 4

    def test_get_strategy_invalid(self):
        assert get_strategy("nonexistent") is None

    def test_list_by_category(self):
        """Filter by category."""
        directional = list_strategies(category=StrategyCategory.DIRECTIONAL)
        assert len(directional) >= 4  # At least long call/put, bull/bear spreads

    def test_list_by_outlook(self):
        bullish = list_strategies(outlook=MarketOutlook.BULLISH)
        assert all(s.outlook == MarketOutlook.BULLISH for s in bullish)
        assert len(bullish) >= 3

    def test_list_by_risk_profile(self):
        defined = list_strategies(risk_profile=RiskProfile.DEFINED)
        assert all(s.risk_profile == RiskProfile.DEFINED for s in defined)

    def test_strategies_for_regime(self):
        """Should find strategies for each VIX regime."""
        for regime in ["low", "normal", "elevated", "high"]:
            strats = strategies_for_regime(regime)
            assert len(strats) > 0, f"No strategies for {regime}"

    def test_builders_match_strategies(self):
        """Every builder should correspond to a registered strategy."""
        for slug in BUILDERS:
            assert slug in STRATEGIES, f"Builder {slug} has no strategy spec"


class TestLegBuilders:
    def test_long_call(self):
        legs = build_long_call(22500, 130, lots=1, lot_size=25)
        assert len(legs) == 1
        assert legs[0].action == "BUY"
        assert legs[0].option_type == "CE"
        # ITM payoff: (22700 - 22500 - 130) * 25 = 1750
        pnl = position_payoff_at_expiry(legs, 22700)
        assert pnl == (200 - 130) * 25

    def test_long_put(self):
        legs = build_long_put(22500, 100, lots=1, lot_size=25)
        assert len(legs) == 1
        assert legs[0].action == "BUY"
        assert legs[0].option_type == "PE"
        # ITM payoff: (22500 - 22300 - 100) * 25 = 2500
        pnl = position_payoff_at_expiry(legs, 22300)
        assert pnl == (200 - 100) * 25

    def test_bull_call_spread(self):
        legs = build_bull_call_spread(22400, 22600, 195, 80, lot_size=25)
        assert len(legs) == 2
        # Max loss at 22200 (both OTM): -(195-80)*25 = -2875
        pnl_loss = position_payoff_at_expiry(legs, 22200)
        assert pnl_loss == -(195 - 80) * 25
        # Max profit at 22700 (both ITM): (200 - 115)*25 = ?
        # Long: (22700-22400-195)*25 = 2625, Short: -(22700-22600-80)*25 = -(-60)*25... wait
        # Long: (300-195)*25 = 2625, Short: (80-100)*25 = -500
        pnl_profit = position_payoff_at_expiry(legs, 22700)
        assert pnl_profit == (300 - 195) * 25 + (80 - 100) * 25  # 2625 - 500 = 2125

    def test_bear_put_spread(self):
        legs = build_bear_put_spread(22500, 22300, 100, 35, lot_size=25)
        assert len(legs) == 2
        # Max profit at 22200: long PE ITM 300-100=200, short PE ITM -(100-35)=-65 => nope
        # Long: (22500-22200-100)*25=5000, Short: (35-(22300-22200))*25=(35-100)*25=-1625
        pnl = position_payoff_at_expiry(legs, 22200)
        assert pnl > 0

    def test_bull_put_spread(self):
        legs = build_bull_put_spread(22400, 22200, 60, 18, lot_size=25)
        assert len(legs) == 2
        # Both OTM at 22500: net premium = (60-18)*25 = 1050
        pnl_profit = position_payoff_at_expiry(legs, 22500)
        assert pnl_profit == (60 - 18) * 25

    def test_bear_call_spread(self):
        legs = build_bear_call_spread(22500, 22700, 130, 45, lot_size=25)
        assert len(legs) == 2
        # Both OTM at 22400: net premium = (130-45)*25 = 2125
        pnl_profit = position_payoff_at_expiry(legs, 22400)
        assert pnl_profit == (130 - 45) * 25

    def test_short_straddle(self):
        legs = build_short_straddle(22500, 130, 100, lot_size=25)
        assert len(legs) == 2
        # Max profit at 22500: all premium = (130+100)*25 = 5750
        pnl = position_payoff_at_expiry(legs, 22500)
        assert pnl == (130 + 100) * 25

    def test_long_straddle(self):
        legs = build_long_straddle(22500, 130, 100, lot_size=25)
        assert len(legs) == 2
        # Max loss at 22500: all premium lost = -(130+100)*25
        pnl = position_payoff_at_expiry(legs, 22500)
        assert pnl == -(130 + 100) * 25

    def test_short_strangle(self):
        legs = build_short_strangle(22600, 22400, 80, 60, lot_size=25)
        assert len(legs) == 2
        # Profit in range: (80+60)*25 = 3500
        pnl = position_payoff_at_expiry(legs, 22500)
        assert pnl == (80 + 60) * 25

    def test_long_strangle(self):
        legs = build_long_strangle(22600, 22400, 80, 60, lot_size=25)
        assert len(legs) == 2
        # Max loss in range: -(80+60)*25 = -3500
        pnl = position_payoff_at_expiry(legs, 22500)
        assert pnl == -(80 + 60) * 25

    def test_iron_condor(self):
        legs = build_iron_condor(
            22200, 22300, 22700, 22800,
            18, 35, 45, 22, lot_size=25,
        )
        assert len(legs) == 4
        # In the range: net premium = (35+45-18-22)*25 = 40*25 = 1000
        pnl = position_payoff_at_expiry(legs, 22500)
        assert pnl == (35 + 45 - 18 - 22) * 25

    def test_iron_butterfly(self):
        legs = build_iron_butterfly(
            22500, 22300, 22700,
            130, 100, 45, 35, lot_size=25,
        )
        assert len(legs) == 4
        # At ATM: net premium = (100+130-35-45)*25 = 150*25 = 3750
        pnl = position_payoff_at_expiry(legs, 22500)
        assert pnl == (100 + 130 - 35 - 45) * 25

    def test_ratio_spread(self):
        legs = build_ratio_spread(22500, 22600, 130, 80, "CE", lot_size=25)
        assert len(legs) == 2
        assert legs[1].lots == 2  # Sell 2x

    def test_jade_lizard(self):
        legs = build_jade_lizard(22300, 22600, 22700, 35, 80, 45, lot_size=25)
        assert len(legs) == 3
        # All expire OTM at 22500: net premium = (35+80-45)*25
        pnl = position_payoff_at_expiry(legs, 22500)
        assert pnl == (35 + 80 - 45) * 25

    def test_collar(self):
        legs = build_collar(22300, 22700, 35, 45, lot_size=25)
        assert len(legs) == 2
