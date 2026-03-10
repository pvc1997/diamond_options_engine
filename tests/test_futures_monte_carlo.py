"""Tests for futures Monte Carlo simulation."""

import pytest

from diamond_options.risk.futures_monte_carlo import (
    FuturesMonteCarloResult,
    futures_stress_test,
    simulate_futures_multi_horizon,
    simulate_futures_position,
)


class TestSimulateFuturesPosition:
    def test_returns_result(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
        )
        assert isinstance(result, FuturesMonteCarloResult)

    def test_expected_pnl_long(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
        )
        # With positive drift (r=6.5%), expected P&L should be slightly positive
        assert result.expected_pnl != 0  # Should have some expectation

    def test_prob_profit_reasonable(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
        )
        assert 0 < result.prob_profit < 100

    def test_var_negative(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
        )
        assert result.var_95 < result.expected_pnl
        assert result.var_99 < result.var_95

    def test_cvar_worse_than_var(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
        )
        assert result.cvar_95 <= result.var_95

    def test_short_position(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="SELL",
            spot=22500, T=20/365, sigma=0.15,
        )
        assert isinstance(result, FuturesMonteCarloResult)

    def test_stop_loss_probability(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
            stop_loss=22000,
        )
        assert result.prob_stop_loss >= 0
        assert result.prob_stop_loss < 100

    def test_target_probability(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
            target=23000,
        )
        assert result.prob_target >= 0
        assert result.prob_target < 100

    def test_margin_call_probability(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
            margin=150000,
        )
        assert result.prob_margin_call >= 0

    def test_no_margin_no_margin_call(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
            margin=0,
        )
        assert result.prob_margin_call == 0.0

    def test_percentiles(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
        )
        assert 50 in result.percentiles
        assert result.percentiles[5] < result.percentiles[50] < result.percentiles[95]

    def test_best_worst_case(self):
        result = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
        )
        assert result.best_case > result.worst_case

    def test_higher_vol_wider_distribution(self):
        low_vol = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.10, seed=42,
        )
        high_vol = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.30, seed=42,
        )
        assert high_vol.std_pnl > low_vol.std_pnl

    def test_more_lots_scales_pnl(self):
        one_lot = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15, seed=42,
        )
        two_lots = simulate_futures_position(
            entry_price=22500, lots=2, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15, seed=42,
        )
        assert abs(two_lots.expected_pnl) > abs(one_lot.expected_pnl) * 1.5

    def test_reproducible_with_seed(self):
        r1 = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15, seed=123,
        )
        r2 = simulate_futures_position(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15, seed=123,
        )
        assert r1.expected_pnl == r2.expected_pnl


class TestSimulateFuturesMultiHorizon:
    def test_returns_list(self):
        results = simulate_futures_multi_horizon(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
        )
        assert isinstance(results, list)
        assert len(results) == 4  # Default 4 checkpoints

    def test_custom_horizons(self):
        results = simulate_futures_multi_horizon(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
            horizons=[0.5, 1.0],
        )
        assert len(results) == 2

    def test_has_required_fields(self):
        results = simulate_futures_multi_horizon(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20/365, sigma=0.15,
        )
        for r in results:
            assert "time_fraction" in r
            assert "days" in r
            assert "expected_pnl" in r
            assert "prob_profit" in r
            assert "var_95" in r
            assert "best_case" in r
            assert "worst_case" in r

    def test_longer_horizon_wider_range(self):
        results = simulate_futures_multi_horizon(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            spot=22500, T=60/365, sigma=0.15,
            horizons=[0.25, 1.0],
        )
        short = results[0]
        long = results[1]
        # Longer horizon should have wider best-worst range
        short_range = short["best_case"] - short["worst_case"]
        long_range = long["best_case"] - long["worst_case"]
        assert long_range > short_range


class TestFuturesStressTest:
    def test_default_scenarios(self):
        results = futures_stress_test(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
        )
        assert len(results) == 9  # 9 default scenarios

    def test_custom_scenarios(self):
        scenarios = [
            {"name": "Crash", "move_pct": -15.0},
            {"name": "Up", "move_pct": 5.0},
        ]
        results = futures_stress_test(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
            scenarios=scenarios,
        )
        assert len(results) == 2

    def test_long_crash_negative_pnl(self):
        results = futures_stress_test(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
        )
        crash = [r for r in results if r["move_pct"] == -10.0][0]
        assert crash["pnl"] < 0

    def test_long_rally_positive_pnl(self):
        results = futures_stress_test(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
        )
        rally = [r for r in results if r["move_pct"] == 10.0][0]
        assert rally["pnl"] > 0

    def test_short_crash_positive_pnl(self):
        results = futures_stress_test(
            entry_price=22500, lots=1, lot_size=65, action="SELL",
        )
        crash = [r for r in results if r["move_pct"] == -10.0][0]
        assert crash["pnl"] > 0

    def test_unchanged_zero_pnl(self):
        results = futures_stress_test(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
        )
        unchanged = [r for r in results if r["move_pct"] == 0.0][0]
        assert unchanged["pnl"] == 0.0

    def test_has_pnl_per_lot(self):
        results = futures_stress_test(
            entry_price=22500, lots=2, lot_size=65, action="BUY",
        )
        for r in results:
            assert "pnl_per_lot" in r
            if r["pnl"] != 0:
                assert r["pnl_per_lot"] == round(r["pnl"] / 2, 2)

    def test_pnl_scales_with_lots(self):
        one = futures_stress_test(
            entry_price=22500, lots=1, lot_size=65, action="BUY",
        )
        two = futures_stress_test(
            entry_price=22500, lots=2, lot_size=65, action="BUY",
        )
        # -10% scenario
        crash_1 = [r for r in one if r["move_pct"] == -10.0][0]
        crash_2 = [r for r in two if r["move_pct"] == -10.0][0]
        assert crash_2["pnl"] == crash_1["pnl"] * 2
