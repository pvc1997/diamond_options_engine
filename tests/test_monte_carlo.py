"""Tests for Monte Carlo simulation."""

import pytest

from diamond_options.pricing.payoff import Leg
from diamond_options.risk.monte_carlo import (
    MonteCarloResult,
    simulate_position,
    simulate_multi_expiry,
    stress_test,
)


@pytest.fixture
def long_call_legs():
    return [Leg(22500, "CE", "BUY", 130, 1, 25)]


@pytest.fixture
def iron_condor_legs():
    return [
        Leg(22200, "PE", "BUY", 18, 1, 25),
        Leg(22300, "PE", "SELL", 35, 1, 25),
        Leg(22700, "CE", "SELL", 45, 1, 25),
        Leg(22800, "CE", "BUY", 22, 1, 25),
    ]


class TestSimulatePosition:
    def test_returns_result(self, long_call_legs):
        result = simulate_position(long_call_legs, 22500, 7/365, 0.065, 0.13)
        assert isinstance(result, MonteCarloResult)

    def test_long_call_limited_loss(self, long_call_legs):
        """Long call worst case should be limited to premium paid."""
        result = simulate_position(long_call_legs, 22500, 7/365, 0.065, 0.13)
        # Premium: 130 * 25 = 3250
        assert result.worst_case >= -3250 - 1  # Allow tiny float error

    def test_iron_condor_defined_risk(self, iron_condor_legs):
        """Iron condor max loss should be bounded."""
        result = simulate_position(iron_condor_legs, 22500, 7/365, 0.065, 0.13)
        # Spread width: 100, max loss = 100*25 - net_premium
        assert result.worst_case > -3000  # Should be bounded

    def test_prob_profit_range(self, long_call_legs):
        result = simulate_position(long_call_legs, 22500, 7/365, 0.065, 0.13)
        assert 0 <= result.prob_profit <= 100

    def test_var_ordering(self, long_call_legs):
        """VaR 99 should be worse than VaR 95."""
        result = simulate_position(long_call_legs, 22500, 7/365, 0.065, 0.13)
        assert result.var_99 <= result.var_95

    def test_cvar_worse_than_var(self, long_call_legs):
        """CVaR (expected shortfall) should be <= VaR."""
        result = simulate_position(long_call_legs, 22500, 7/365, 0.065, 0.13)
        assert result.cvar_95 <= result.var_95

    def test_percentiles(self, long_call_legs):
        """Should have standard percentile keys."""
        result = simulate_position(long_call_legs, 22500, 7/365, 0.065, 0.13)
        assert 5 in result.percentiles
        assert 50 in result.percentiles
        assert 95 in result.percentiles
        # Percentiles should be monotonically increasing
        assert result.percentiles[5] <= result.percentiles[50]
        assert result.percentiles[50] <= result.percentiles[95]

    def test_reproducibility(self, long_call_legs):
        """Same seed should give same results."""
        r1 = simulate_position(long_call_legs, 22500, 7/365, 0.065, 0.13, seed=42)
        r2 = simulate_position(long_call_legs, 22500, 7/365, 0.065, 0.13, seed=42)
        assert r1.expected_pnl == r2.expected_pnl

    def test_target_probability(self, iron_condor_legs):
        """Probability of hitting a target should be reasonable."""
        result = simulate_position(
            iron_condor_legs, 22500, 7/365, 0.065, 0.13,
            target_pnl=500,
        )
        assert 0 <= result.prob_target <= 100

    def test_more_paths_different_seed(self, long_call_legs):
        """Different seeds should give different results."""
        r1 = simulate_position(long_call_legs, 22500, 7/365, 0.065, 0.13, seed=1)
        r2 = simulate_position(long_call_legs, 22500, 7/365, 0.065, 0.13, seed=99)
        # Not identical (could be same by extreme coincidence but very unlikely)
        assert r1.expected_pnl != r2.expected_pnl or r1.prob_profit != r2.prob_profit


class TestSimulateMultiExpiry:
    def test_returns_checkpoints(self, long_call_legs):
        results = simulate_multi_expiry(
            long_call_legs, 22500, 30/365, 0.065, 0.13,
        )
        assert len(results) == 4  # Default: 0.25, 0.5, 0.75, 1.0

    def test_custom_checkpoints(self, long_call_legs):
        results = simulate_multi_expiry(
            long_call_legs, 22500, 30/365, 0.065, 0.13,
            check_points=[0.5, 1.0],
        )
        assert len(results) == 2

    def test_checkpoint_keys(self, long_call_legs):
        results = simulate_multi_expiry(
            long_call_legs, 22500, 30/365, 0.065, 0.13,
        )
        for r in results:
            assert "time_fraction" in r
            assert "expected_pnl" in r
            assert "prob_profit" in r
            assert "var_95" in r


class TestStressTest:
    def test_default_scenarios(self, long_call_legs):
        results = stress_test(long_call_legs, 22500)
        assert len(results) == 9  # Default 9 scenarios

    def test_custom_scenarios(self, long_call_legs):
        scenarios = [
            {"name": "Down 5%", "spot_move_pct": -5.0},
            {"name": "Up 5%", "spot_move_pct": 5.0},
        ]
        results = stress_test(long_call_legs, 22500, scenarios)
        assert len(results) == 2

    def test_long_call_payoff_logic(self, long_call_legs):
        """Long call should profit on up-move, lose on down."""
        results = stress_test(long_call_legs, 22500)
        down_10 = next(r for r in results if r["spot_move_pct"] == -10.0)
        up_10 = next(r for r in results if r["spot_move_pct"] == 10.0)
        assert down_10["pnl"] < up_10["pnl"]

    def test_iron_condor_range_profit(self, iron_condor_legs):
        """Iron condor should profit when unchanged, lose on big moves."""
        results = stress_test(iron_condor_legs, 22500)
        unchanged = next(r for r in results if r["spot_move_pct"] == 0.0)
        crash = next(r for r in results if r["spot_move_pct"] == -10.0)
        assert unchanged["pnl"] > crash["pnl"]

    def test_scenario_keys(self, long_call_legs):
        results = stress_test(long_call_legs, 22500)
        for r in results:
            assert "scenario" in r
            assert "spot_move_pct" in r
            assert "new_spot" in r
            assert "pnl" in r
