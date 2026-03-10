"""Tests for futures MCP tool functions (integration tests).

Tests the same logic the MCP tools expose, using the underlying library
functions directly (MCP server has its own venv with fastmcp).
"""

import pytest


# ── Futures Pricing & Analytics ──


class TestFuturesFairValue:
    def test_cost_of_carry(self):
        from diamond_options.pricing.futures_pricing import theoretical_futures_price

        fair = theoretical_futures_price(22500, 0.065, 20 / 365, 0.012)
        assert fair > 22500  # Contango
        basis = fair - 22500
        assert basis > 0

    def test_zero_dividend_higher_fair(self):
        from diamond_options.pricing.futures_pricing import theoretical_futures_price

        f1 = theoretical_futures_price(22500, 0.065, 20 / 365, 0.0)
        f2 = theoretical_futures_price(22500, 0.065, 20 / 365, 0.02)
        assert f1 > f2


class TestBasisAnalysisTool:
    def test_returns_analysis(self):
        from diamond_options.pricing.basis_analysis import analyze_basis

        # analyze_basis(futures_price, spot_price, dte)
        result = analyze_basis(22650, 22500, 20)
        assert result.current_basis > 0  # futures > spot = positive basis
        assert result.annualized_basis > 0
        assert result.signal in ("rich", "cheap", "fair")

    def test_with_historical(self):
        from diamond_options.pricing.basis_analysis import analyze_basis

        result = analyze_basis(
            22650, 22500, 20,
            basis_history=[0.5, 0.6, 0.4, 0.7, 0.55, 0.65, 0.45],
        )
        assert result.basis_z_score != 0.0

    def test_with_next_futures(self):
        from diamond_options.pricing.basis_analysis import analyze_basis

        result = analyze_basis(
            22650, 22500, 20,
            next_month_price=22750, next_month_days=30,
        )
        assert result.roll_yield != 0.0


class TestFuturesMispricingTool:
    def test_rich_futures(self):
        from diamond_options.pricing.futures_pricing import futures_mispricing

        result = futures_mispricing(22500, 22700, 0.065, 20 / 365)
        assert result.mispricing > 0  # Futures above fair value
        assert result.is_overpriced is True

    def test_cheap_futures(self):
        from diamond_options.pricing.futures_pricing import futures_mispricing

        result = futures_mispricing(22500, 22400, 0.065, 20 / 365)
        assert result.mispricing < 0
        assert result.is_underpriced is True


# ── Futures Costs & P&L ──


class TestFuturesPnlCalculator:
    def test_profitable_long(self):
        from diamond_options.data.costs import futures_pnl

        result = futures_pnl(22500, 22700, 1, 65, "BUY")
        assert result["gross_pnl"] > 0
        assert result["net_pnl"] > 0
        assert result["total_costs"] > 0

    def test_losing_short(self):
        from diamond_options.data.costs import futures_pnl

        result = futures_pnl(22500, 22700, 1, 65, "SELL")
        assert result["gross_pnl"] < 0

    def test_breakeven(self):
        from diamond_options.data.costs import futures_breakeven

        be = futures_breakeven(22500, 1, 65, "BUY")
        assert be > 22500  # Must exceed entry to cover costs


class TestFuturesRoundTripCost:
    def test_returns_cost(self):
        from diamond_options.data.costs import futures_round_trip_cost

        cost = futures_round_trip_cost(22500, 1, 65)
        assert cost > 0


class TestFuturesMarginEstimateTool:
    def test_nifty_margin(self):
        from diamond_options.data.universe import (
            get_futures_margin_pct, get_futures_margin_estimate,
        )

        pct = get_futures_margin_pct("NIFTY")
        assert pct > 0
        margin = get_futures_margin_estimate("NIFTY", 22500, 1)
        assert margin > 0

    def test_stock_margin(self):
        from diamond_options.data.universe import get_futures_margin_estimate

        margin = get_futures_margin_estimate("RELIANCE", 2800, 1)
        assert margin > 0


# ── Futures Strategy Engine ──


class TestListFuturesStrategiesTool:
    def test_list_all(self):
        from diamond_options.strategy.futures_strategies import (
            list_futures_strategies, FuturesStrategyCategory,
        )

        strategies = list_futures_strategies()
        assert len(strategies) >= 14

    def test_filter_by_category(self):
        from diamond_options.strategy.futures_strategies import (
            list_futures_strategies, FuturesStrategyCategory,
        )

        strategies = list_futures_strategies(category=FuturesStrategyCategory.DIRECTIONAL)
        for s in strategies:
            assert s.category == FuturesStrategyCategory.DIRECTIONAL


class TestFuturesStrategyDetailsTool:
    def test_existing_strategy(self):
        from diamond_options.strategy.futures_strategies import get_futures_strategy

        s = get_futures_strategy("long_futures")
        assert s is not None
        assert s.name == "Long Futures"

    def test_nonexistent(self):
        from diamond_options.strategy.futures_strategies import get_futures_strategy

        assert get_futures_strategy("nonexistent") is None


class TestScanFuturesSignalsTool:
    def test_returns_signals(self):
        from diamond_options.strategy.futures_scanner import (
            FuturesMarketCondition, TrendDirection, OIBuildupSignal,
            scan_futures_strategies,
        )

        condition = FuturesMarketCondition(
            spot=22500, near_futures=22650, next_futures=0,
            basis_pct=0.667, annualized_basis=8.0, vix=15,
            trend=TrendDirection.BULLISH, realized_vol=0.14,
            days_to_expiry=20, oi_buildup=OIBuildupSignal.LONG_BUILDUP,
        )
        signals = scan_futures_strategies(condition)
        assert len(signals) > 0
        for s in signals:
            assert 0 <= s.score <= 100


class TestSuggestFuturesStrategyTool:
    def test_returns_recommendations(self):
        from diamond_options.strategy.futures_recommender import quick_futures_recommendation

        recs = quick_futures_recommendation(
            spot=22500, near_futures=22650, vix=15, realized_vol=0.14,
            trend="bullish", symbol="NIFTY",
        )
        assert len(recs) > 0
        assert "entry_price" in recs[0]
        assert "target" in recs[0]
        assert "margin_required" in recs[0]


# ── Futures Risk Management ──


class TestFuturesPortfolioRiskTool:
    def test_single_position(self):
        from diamond_options.risk.futures_risk import (
            calculate_futures_position_risk, aggregate_futures_risk,
            futures_exposure_summary,
        )

        pos = calculate_futures_position_risk(
            "NIFTY", "BUY", 1, 65, 22500, 22600, 22550, 15,
        )
        portfolio = aggregate_futures_risk([pos], 500000)
        summary = futures_exposure_summary(portfolio, 500000)
        assert summary["position_count"] == 1
        assert summary["unrealized_pnl"] > 0
        assert "risk_level" in summary


class TestFuturesAdjustmentAdvisorTool:
    def test_healthy_position(self):
        from diamond_options.risk.futures_adjustments import analyze_futures_position

        result = analyze_futures_position(
            "NIFTY", "BUY", 1, 65, 22500, 22550, 22530, 15,
        )
        assert result.position_status == "healthy"

    def test_near_expiry_roll(self):
        from diamond_options.risk.futures_adjustments import analyze_futures_position

        result = analyze_futures_position(
            "NIFTY", "BUY", 1, 65, 22500, 22550, 22530, 1,
        )
        roll_adj = [a for a in result.adjustments if a.type.value == "roll_next"]
        assert len(roll_adj) > 0


class TestFuturesExpiryChecklistTool:
    def test_index_expiry(self):
        from diamond_options.risk.futures_adjustments import futures_expiry_checklist

        checklist = futures_expiry_checklist(
            "NIFTY", "BUY", 1, 65, 22500, 22600, 22580, 0,
        )
        assert len(checklist) > 0
        assert any("cash-settle" in item.lower() for item in checklist)


# ── Futures Monte Carlo & Stress Test ──


class TestFuturesMonteCarloTool:
    def test_returns_result(self):
        from diamond_options.risk.futures_monte_carlo import simulate_futures_position

        result = simulate_futures_position(
            22500, 1, 65, "BUY", 22500, 20 / 365, 0.15,
        )
        assert result.prob_profit > 0
        assert result.var_95 < result.expected_pnl

    def test_with_stop_target(self):
        from diamond_options.risk.futures_monte_carlo import simulate_futures_position

        result = simulate_futures_position(
            22500, 1, 65, "BUY", 22500, 20 / 365, 0.15,
            stop_loss=22000, target=23000,
        )
        assert result.prob_stop_loss >= 0
        assert result.prob_target >= 0


class TestFuturesStressTestTool:
    def test_returns_scenarios(self):
        from diamond_options.risk.futures_monte_carlo import futures_stress_test

        results = futures_stress_test(22500, 1, 65, "BUY")
        assert len(results) == 9

    def test_long_crash_negative(self):
        from diamond_options.risk.futures_monte_carlo import futures_stress_test

        results = futures_stress_test(22500, 1, 65, "BUY")
        crash = [r for r in results if r["move_pct"] == -10.0][0]
        assert crash["pnl"] < 0


class TestFuturesMultiHorizonTool:
    def test_returns_horizons(self):
        from diamond_options.risk.futures_monte_carlo import simulate_futures_multi_horizon

        results = simulate_futures_multi_horizon(
            22500, 1, 65, "BUY", 22500, 20 / 365, 0.15,
        )
        assert len(results) == 4


# ── Futures Backtester ──


class TestBacktestFuturesTool:
    def test_long_backtest(self):
        from diamond_options.risk.futures_backtester import backtest_futures_strategy

        prices = [22000 + i * 30 for i in range(50)]
        dates = [f"2026-01-{i+1:02d}" for i in range(31)] + \
                [f"2026-02-{i+1:02d}" for i in range(19)]

        result = backtest_futures_strategy("long_futures", prices, dates)
        assert result.total_trades > 0
        assert result.total_costs > 0

    def test_insufficient_data(self):
        from diamond_options.risk.futures_backtester import backtest_futures_strategy

        result = backtest_futures_strategy("long_futures", [22500], ["2026-01-01"])
        assert result.total_trades == 0
