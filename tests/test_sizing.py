"""Tests for position sizing module."""

import pytest

from diamond_options.strategy.sizing import (
    PositionSize,
    fixed_risk_size,
    kelly_size,
    vix_adjusted_multiplier,
    max_lots_by_capital,
)


class TestFixedRiskSize:
    def test_basic_sizing(self):
        """Should calculate lots from risk budget."""
        size = fixed_risk_size(
            capital=500000,
            max_risk_pct=2.0,
            max_loss_per_lot=2500,
            lot_size=25,
        )
        # Risk budget: 500000 * 2% = 10000
        # Lots: 10000 / 2500 = 4
        assert size.lots == 4
        assert size.lot_size == 25
        assert size.total_quantity == 100
        assert size.capital_at_risk == 10000

    def test_minimum_one_lot(self):
        """Should always return at least 1 lot."""
        size = fixed_risk_size(
            capital=100000,
            max_risk_pct=0.5,
            max_loss_per_lot=50000,
            lot_size=25,
        )
        assert size.lots == 1

    def test_margin_constraint(self):
        """Should respect margin limits."""
        size = fixed_risk_size(
            capital=500000,
            max_risk_pct=10.0,
            max_loss_per_lot=1000,
            lot_size=25,
            margin_per_lot=80000,
            max_margin_pct=0.30,
        )
        # By risk: 50000 / 1000 = 50
        # By margin: 150000 / 80000 = 1
        assert size.lots <= 2

    def test_vix_multiplier(self):
        """VIX multiplier should reduce size."""
        full = fixed_risk_size(500000, 2.0, 2500, 25, vix_multiplier=1.0)
        half = fixed_risk_size(500000, 2.0, 2500, 25, vix_multiplier=0.5)
        assert half.lots <= full.lots

    def test_max_lots_cap(self):
        """Should respect max lots cap."""
        size = fixed_risk_size(
            capital=10000000,
            max_risk_pct=10.0,
            max_loss_per_lot=100,
            lot_size=25,
            max_lots=10,
        )
        assert size.lots == 10

    def test_zero_capital(self):
        """Should handle zero capital."""
        size = fixed_risk_size(0, 2.0, 2500, 25)
        assert size.lots == 0

    def test_zero_max_loss(self):
        """Should handle zero max loss per lot."""
        size = fixed_risk_size(500000, 2.0, 0, 25)
        assert size.lots == 0

    def test_method_label(self):
        size = fixed_risk_size(500000, 2.0, 2500, 25)
        assert size.method == "fixed_risk"

    def test_notes_include_risk_budget(self):
        size = fixed_risk_size(500000, 2.0, 2500, 25)
        assert "Risk budget" in size.notes


class TestKellySize:
    def test_positive_edge(self):
        """Positive edge should give non-zero lots."""
        size = kelly_size(
            capital=500000,
            win_probability=0.6,
            avg_win=5000,
            avg_loss=3000,
            lot_size=25,
            max_loss_per_lot=3000,
        )
        assert size.lots > 0
        assert size.method == "kelly"

    def test_no_edge(self):
        """No edge should give 0 lots."""
        size = kelly_size(
            capital=500000,
            win_probability=0.3,
            avg_win=2000,
            avg_loss=5000,
            lot_size=25,
            max_loss_per_lot=5000,
        )
        assert size.lots == 0

    def test_half_kelly_smaller(self):
        """Half Kelly should give fewer lots than full Kelly."""
        full = kelly_size(500000, 0.6, 5000, 3000, 25, 3000, fraction=1.0)
        half = kelly_size(500000, 0.6, 5000, 3000, 25, 3000, fraction=0.5)
        assert half.lots <= full.lots

    def test_notes_contain_kelly_info(self):
        size = kelly_size(500000, 0.6, 5000, 3000, 25, 3000)
        assert "Kelly" in size.notes
        assert "Win rate" in size.notes

    def test_invalid_probability(self):
        """Edge case: P=0 or P=1 should return 0."""
        size = kelly_size(500000, 0, 5000, 3000, 25, 3000)
        assert size.lots == 0
        size = kelly_size(500000, 1.0, 5000, 3000, 25, 3000)
        assert size.lots == 0


class TestVIXMultiplier:
    def test_low_vix(self):
        assert vix_adjusted_multiplier(10) == 0.75

    def test_normal_vix(self):
        assert vix_adjusted_multiplier(15) == 1.0

    def test_elevated_vix(self):
        assert vix_adjusted_multiplier(22) == 0.80

    def test_high_vix(self):
        assert vix_adjusted_multiplier(30) == 0.50

    def test_crisis_vix(self):
        assert vix_adjusted_multiplier(45) == 0.25


class TestMaxLotsByCapital:
    def test_basic(self):
        """Should calculate affordable lots."""
        lots = max_lots_by_capital(
            capital=500000,
            premium_per_share=130,
            lot_size=25,
            max_allocation_pct=5.0,
        )
        # Max spend: 25000, Cost per lot: 130*25=3250
        assert lots == 7  # 25000/3250 = 7.69 → 7

    def test_zero_premium(self):
        assert max_lots_by_capital(500000, 0, 25) == 0

    def test_zero_capital(self):
        assert max_lots_by_capital(0, 130, 25) == 0

    def test_expensive_option(self):
        """Expensive option should allow fewer lots."""
        lots = max_lots_by_capital(500000, 500, 25, 5.0)
        assert lots < max_lots_by_capital(500000, 100, 25, 5.0)
