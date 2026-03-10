"""Tests for futures basis analysis."""

import pytest

from diamond_options.pricing.basis_analysis import (
    BasisAnalysis,
    analyze_basis,
    annualized_basis,
    basis_convergence_rate,
    basis_percentile,
    basis_trade_signal,
    basis_z_score,
    calculate_basis,
    historical_basis_stats,
    roll_yield,
)


class TestCalculateBasis:
    def test_contango(self):
        result = calculate_basis(22650.0, 22500.0)
        assert result["basis"] == 150.0
        assert result["is_contango"]
        assert not result["is_backwardation"]

    def test_backwardation(self):
        result = calculate_basis(22400.0, 22500.0)
        assert result["basis"] == -100.0
        assert result["is_backwardation"]
        assert not result["is_contango"]

    def test_zero_basis(self):
        result = calculate_basis(22500.0, 22500.0)
        assert result["basis"] == 0.0
        assert not result["is_contango"]
        assert not result["is_backwardation"]

    def test_basis_pct(self):
        result = calculate_basis(22650.0, 22500.0)
        expected = 150.0 / 22500.0 * 100
        assert abs(result["basis_pct"] - round(expected, 4)) < 0.001

    def test_zero_spot(self):
        result = calculate_basis(100.0, 0.0)
        assert result["basis_pct"] == 0.0


class TestAnnualizedBasis:
    def test_basic(self):
        # 0.67% over 30 days → annualized
        ann = annualized_basis(0.6667, 30)
        expected = (0.6667 / 30) * 365
        assert abs(ann - expected) < 0.01

    def test_zero_days(self):
        assert annualized_basis(0.5, 0) == 0.0

    def test_negative_basis(self):
        ann = annualized_basis(-0.5, 20)
        assert ann < 0


class TestBasisConvergenceRate:
    def test_basic(self):
        rate = basis_convergence_rate(150.0, 30)
        assert abs(rate - 5.0) < 0.01

    def test_zero_days(self):
        assert basis_convergence_rate(150.0, 0) == 0.0

    def test_negative_basis(self):
        rate = basis_convergence_rate(-100.0, 20)
        assert rate == -5.0


class TestRollYield:
    def test_contango_roll(self):
        # Near 22650, next 22750, 30 days between
        ry = roll_yield(22650.0, 22750.0, 30)
        spread_pct = (100.0 / 22650.0) * 100
        expected = (spread_pct / 30) * 365
        assert abs(ry - expected) < 0.01

    def test_backwardation_roll(self):
        ry = roll_yield(22750.0, 22650.0, 30)
        assert ry < 0  # Negative roll yield in backwardation

    def test_zero_near_price(self):
        assert roll_yield(0.0, 100.0, 30) == 0.0

    def test_zero_days(self):
        assert roll_yield(22650.0, 22750.0, 0) == 0.0


class TestHistoricalBasisStats:
    def test_basic_stats(self):
        data = [0.5, 0.6, 0.7, 0.8, 0.9]
        stats = historical_basis_stats(data)
        assert abs(stats["mean"] - 0.7) < 0.01
        assert stats["min"] == 0.5
        assert stats["max"] == 0.9
        assert stats["count"] == 5
        assert stats["std"] > 0

    def test_empty_series(self):
        stats = historical_basis_stats([])
        assert stats["mean"] == 0.0
        assert stats["count"] == 0

    def test_single_value(self):
        stats = historical_basis_stats([1.0])
        assert stats["mean"] == 1.0
        assert stats["std"] == 0.0
        assert stats["count"] == 1


class TestBasisZScore:
    def test_above_mean(self):
        z = basis_z_score(1.5, 1.0, 0.2)
        assert z == 2.5

    def test_below_mean(self):
        z = basis_z_score(0.5, 1.0, 0.2)
        assert z == -2.5

    def test_at_mean(self):
        z = basis_z_score(1.0, 1.0, 0.2)
        assert z == 0.0

    def test_zero_std(self):
        assert basis_z_score(1.5, 1.0, 0.0) == 0.0


class TestBasisPercentile:
    def test_at_maximum(self):
        pctile = basis_percentile(1.0, [0.1, 0.2, 0.3, 0.4, 0.5])
        assert pctile == 100.0

    def test_at_minimum(self):
        # All values are above 0.0
        pctile = basis_percentile(0.0, [0.1, 0.2, 0.3, 0.4, 0.5])
        assert pctile == 0.0

    def test_median(self):
        pctile = basis_percentile(0.3, [0.1, 0.2, 0.3, 0.4, 0.5])
        # 3 values <= 0.3 out of 5
        assert pctile == 60.0

    def test_empty_series(self):
        assert basis_percentile(0.5, []) == 50.0


class TestBasisTradeSignal:
    def test_rich(self):
        signal = basis_trade_signal(1.5, 0.5, 0.3)
        # z = (1.5 - 0.5) / 0.3 = 3.33 > 1.5
        assert signal == "rich"

    def test_cheap(self):
        signal = basis_trade_signal(-0.5, 0.5, 0.3)
        # z = (-0.5 - 0.5) / 0.3 = -3.33 < -1.5
        assert signal == "cheap"

    def test_fair(self):
        signal = basis_trade_signal(0.5, 0.5, 0.3)
        # z = 0.0
        assert signal == "fair"

    def test_custom_thresholds(self):
        signal = basis_trade_signal(0.7, 0.5, 0.1, rich_threshold=1.0)
        # z = 2.0 > 1.0
        assert signal == "rich"


class TestAnalyzeBasis:
    def test_basic_analysis(self):
        result = analyze_basis(22650.0, 22500.0, 20)
        assert isinstance(result, BasisAnalysis)
        assert result.current_basis == 150.0
        assert result.days_to_expiry == 20
        assert result.annualized_basis > 0
        assert result.convergence_rate > 0

    def test_with_history(self):
        history = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]
        basis_pct = 150.0 / 22500.0 * 100  # ~0.667%
        result = analyze_basis(22650.0, 22500.0, 20, basis_history=history)
        assert result.basis_z_score != 0.0
        assert 0 <= result.basis_percentile <= 100
        assert result.signal in ("rich", "cheap", "fair")

    def test_with_roll_yield(self):
        result = analyze_basis(
            22650.0, 22500.0, 20,
            next_month_price=22750.0,
            next_month_days=30,
        )
        assert result.roll_yield != 0.0

    def test_no_history(self):
        result = analyze_basis(22650.0, 22500.0, 20)
        assert result.basis_z_score == 0.0
        assert result.basis_percentile == 50.0
        assert result.signal == "fair"

    def test_short_history_ignored(self):
        # Less than 5 data points → treated as no history
        result = analyze_basis(22650.0, 22500.0, 20, basis_history=[0.5, 0.6, 0.7])
        assert result.basis_z_score == 0.0
        assert result.signal == "fair"

    def test_backwardation(self):
        result = analyze_basis(22400.0, 22500.0, 20)
        assert result.current_basis < 0
        assert result.annualized_basis < 0
