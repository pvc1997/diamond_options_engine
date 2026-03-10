"""Tests for live basis analysis from Kite market quotes."""

from __future__ import annotations

import math
import pytest

from diamond_options.pricing.live_basis import (
    LiveBasisResult,
    RolloverAnalysis,
    live_basis_from_kite,
    live_basis_scan,
    live_rollover_analysis,
)


# ── LiveBasisResult dataclass ──────────────────────────────────


class TestLiveBasisResult:
    def test_fields(self):
        r = LiveBasisResult(
            symbol="NIFTY", spot=22500, futures=22600, basis=100,
            basis_pct=0.4444, annualized_basis=8.11, fair_value=22580,
            mispricing=20, mispricing_pct=0.0889, days_to_expiry=20,
            signal="rich", contango=True,
        )
        assert r.symbol == "NIFTY"
        assert r.contango is True
        assert r.signal == "rich"

    def test_frozen(self):
        r = LiveBasisResult(
            symbol="NIFTY", spot=22500, futures=22600, basis=100,
            basis_pct=0.44, annualized_basis=8.0, fair_value=22580,
            mispricing=20, mispricing_pct=0.09, days_to_expiry=20,
            signal="rich", contango=True,
        )
        with pytest.raises(AttributeError):
            r.symbol = "BANKNIFTY"


# ── live_basis_from_kite ───────────────────────────────────────


class TestLiveBasisFromKite:
    def test_contango(self):
        r = live_basis_from_kite("NIFTY", 22500, 22600, 20)
        assert r.symbol == "NIFTY"
        assert r.spot == 22500
        assert r.futures == 22600
        assert r.basis == 100
        assert r.contango is True
        assert r.basis_pct > 0

    def test_backwardation(self):
        r = live_basis_from_kite("RELIANCE", 2800, 2790, 15)
        assert r.basis == -10
        assert r.contango is False

    def test_annualized_basis(self):
        r = live_basis_from_kite("NIFTY", 22500, 22600, 20)
        expected = (100 / 22500 * 100) / 20 * 365
        assert abs(r.annualized_basis - round(expected, 2)) < 0.1

    def test_fair_value_calculation(self):
        spot = 22500
        dte = 20
        r = 0.065
        T = dte / 365.0
        expected_fv = spot * math.exp(r * T)
        result = live_basis_from_kite("NIFTY", spot, 22600, dte, risk_free_rate=r)
        assert abs(result.fair_value - round(expected_fv, 2)) < 0.01

    def test_fair_value_with_dividend(self):
        spot = 2800
        dte = 30
        r = 0.065
        q = 0.02
        T = dte / 365.0
        expected_fv = spot * math.exp((r - q) * T)
        result = live_basis_from_kite("RELIANCE", spot, 2820, dte, r, q)
        assert abs(result.fair_value - round(expected_fv, 2)) < 0.01

    def test_mispricing(self):
        r = live_basis_from_kite("NIFTY", 22500, 22700, 20)
        assert r.mispricing > 0  # futures above fair value

    def test_signal_rich(self):
        # Large positive basis -> high annualized -> "rich"
        r = live_basis_from_kite("NIFTY", 22500, 22700, 10)
        ann = (200 / 22500 * 100) / 10 * 365
        assert ann > 8
        assert r.signal == "rich"

    def test_signal_cheap(self):
        # Small basis -> low annualized -> "cheap"
        r = live_basis_from_kite("NIFTY", 22500, 22510, 30)
        ann = (10 / 22500 * 100) / 30 * 365
        assert ann < 4
        assert r.signal == "cheap"

    def test_signal_fair(self):
        # Moderate basis in the 4-8% range
        # 22500 * 0.06 * 20/365 = ~73.97 → annualized ~6%
        futures = 22500 + 74
        r = live_basis_from_kite("NIFTY", 22500, futures, 20)
        assert r.signal == "fair"

    def test_symbol_uppercased(self):
        r = live_basis_from_kite("nifty", 22500, 22600, 20)
        assert r.symbol == "NIFTY"

    def test_zero_spot(self):
        r = live_basis_from_kite("NIFTY", 0, 22600, 20)
        assert r.basis_pct == 0
        assert r.mispricing_pct == 0

    def test_zero_dte(self):
        r = live_basis_from_kite("NIFTY", 22500, 22510, 0)
        assert r.annualized_basis == 0

    def test_rounding(self):
        r = live_basis_from_kite("NIFTY", 22500.123, 22600.456, 20)
        assert r.spot == round(22500.123, 2)
        assert r.futures == round(22600.456, 2)


# ── live_basis_scan ────────────────────────────────────────────


class TestLiveBasisScan:
    def test_basic_scan(self):
        quotes = [
            {"symbol": "NIFTY", "spot_price": 22500, "futures_price": 22700, "days_to_expiry": 10},
            {"symbol": "BANKNIFTY", "spot_price": 48000, "futures_price": 48050, "days_to_expiry": 30},
            {"symbol": "RELIANCE", "spot_price": 2800, "futures_price": 2830, "days_to_expiry": 20},
        ]
        results = live_basis_scan(quotes)
        assert len(results) == 3
        assert all(isinstance(r, LiveBasisResult) for r in results)

    def test_sort_order(self):
        """Rich and cheap signals should come before fair."""
        quotes = [
            # annualized ~5.5% -> fair
            {"symbol": "FAIR1", "spot_price": 1000, "futures_price": 1003, "days_to_expiry": 20},
            # annualized ~18.25% -> rich
            {"symbol": "RICH1", "spot_price": 1000, "futures_price": 1050, "days_to_expiry": 10},
            # annualized ~1.2% -> cheap
            {"symbol": "CHEAP1", "spot_price": 1000, "futures_price": 1001, "days_to_expiry": 30},
        ]
        results = live_basis_scan(quotes)
        signals = [r.signal for r in results]
        # Rich and cheap come before fair
        assert "fair" in signals
        assert "rich" in signals
        assert signals.index("rich") < signals.index("fair")
        assert signals.index("cheap") < signals.index("fair")

    def test_skips_zero_prices(self):
        quotes = [
            {"symbol": "GOOD", "spot_price": 100, "futures_price": 105, "days_to_expiry": 20},
            {"symbol": "BAD1", "spot_price": 0, "futures_price": 105, "days_to_expiry": 20},
            {"symbol": "BAD2", "spot_price": 100, "futures_price": 0, "days_to_expiry": 20},
        ]
        results = live_basis_scan(quotes)
        assert len(results) == 1
        assert results[0].symbol == "GOOD"

    def test_empty_quotes(self):
        assert live_basis_scan([]) == []

    def test_custom_risk_free_rate(self):
        quotes = [
            {"symbol": "NIFTY", "spot_price": 22500, "futures_price": 22600, "days_to_expiry": 20},
        ]
        r1 = live_basis_scan(quotes, risk_free_rate=0.05)
        r2 = live_basis_scan(quotes, risk_free_rate=0.10)
        # Higher risk-free rate -> higher fair value -> lower mispricing
        assert r1[0].mispricing > r2[0].mispricing

    def test_default_dte(self):
        quotes = [{"symbol": "NIFTY", "spot_price": 22500, "futures_price": 22600}]
        results = live_basis_scan(quotes)
        assert len(results) == 1
        assert results[0].days_to_expiry == 20  # default

    def test_dividend_yield(self):
        quotes = [
            {"symbol": "ITC", "spot_price": 450, "futures_price": 455,
             "days_to_expiry": 20, "dividend_yield": 0.03},
        ]
        results = live_basis_scan(quotes)
        assert len(results) == 1


# ── RolloverAnalysis dataclass ─────────────────────────────────


class TestRolloverAnalysis:
    def test_fields(self):
        r = RolloverAnalysis(
            symbol="NIFTY", near_price=22600, near_expiry_dte=3,
            next_price=22700, next_expiry_dte=33, calendar_spread=100,
            calendar_spread_pct=0.4425, roll_cost_pct=0.4425,
            annualized_roll_cost=5.38, recommendation="roll_now",
            rationale="Expiry in 3 days",
        )
        assert r.symbol == "NIFTY"
        assert r.recommendation == "roll_now"


# ── live_rollover_analysis ─────────────────────────────────────


class TestLiveRolloverAnalysis:
    def test_expiry_imminent(self):
        r = live_rollover_analysis("NIFTY", 22600, 1, 22700, 31)
        assert r.recommendation == "roll_now"
        assert "imminent" in r.rationale.lower() or "must roll" in r.rationale.lower()

    def test_expiry_3_days_reasonable_spread(self):
        r = live_rollover_analysis("NIFTY", 22600, 3, 22620, 33)
        assert r.recommendation == "roll_now"
        assert r.calendar_spread == 20

    def test_expiry_3_days_wide_spread(self):
        r = live_rollover_analysis("NIFTY", 22600, 2, 22900, 32)
        assert r.recommendation == "roll_now"
        assert "wide" in r.rationale.lower() or "must roll" in r.rationale.lower()

    def test_7_days_good_spread(self):
        r = live_rollover_analysis("NIFTY", 22600, 5, 22610, 35)
        spread_pct = abs(10 / 22600 * 100)
        assert spread_pct < 0.5
        assert r.recommendation == "roll_now"

    def test_7_days_moderate_spread(self):
        r = live_rollover_analysis("NIFTY", 22600, 5, 22750, 35)
        spread_pct = 150 / 22600 * 100
        assert 0.5 < spread_pct < 1.0
        assert r.recommendation == "wait"

    def test_7_days_wide_spread(self):
        r = live_rollover_analysis("NIFTY", 22600, 5, 22900, 35)
        spread_pct = 300 / 22600 * 100
        assert spread_pct > 1.0
        assert r.recommendation == "wait"

    def test_no_urgency(self):
        r = live_rollover_analysis("NIFTY", 22600, 15, 22700, 45)
        assert r.recommendation == "wait"
        assert "no urgency" in r.rationale.lower()

    def test_backwardation_note(self):
        r = live_rollover_analysis("NIFTY", 22600, 10, 22500, 40)
        assert r.calendar_spread == -100
        assert "backwardation" in r.rationale.lower()

    def test_high_roll_cost_note(self):
        # Big spread over short period -> high annualized cost
        r = live_rollover_analysis("NIFTY", 22600, 1, 23200, 31)
        assert "high roll cost" in r.rationale.lower() or r.annualized_roll_cost > 10

    def test_spread_calculations(self):
        r = live_rollover_analysis("NIFTY", 22600, 5, 22700, 35)
        assert r.calendar_spread == 100
        assert abs(r.calendar_spread_pct - round(100 / 22600 * 100, 4)) < 0.01
        assert r.roll_cost_pct == r.calendar_spread_pct

    def test_annualized_roll_cost(self):
        r = live_rollover_analysis("NIFTY", 22600, 5, 22700, 35)
        days_between = 35 - 5
        spread_pct = 100 / 22600 * 100
        expected_ann = spread_pct / days_between * 365
        assert abs(r.annualized_roll_cost - round(expected_ann, 2)) < 0.1

    def test_symbol_uppercased(self):
        r = live_rollover_analysis("nifty", 22600, 5, 22700, 35)
        assert r.symbol == "NIFTY"

    def test_zero_near_price(self):
        r = live_rollover_analysis("NIFTY", 0, 5, 22700, 35)
        assert r.calendar_spread_pct == 0

    def test_equal_dte(self):
        r = live_rollover_analysis("NIFTY", 22600, 5, 22700, 5)
        assert r.annualized_roll_cost == 0
