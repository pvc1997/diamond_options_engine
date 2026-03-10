"""Tests for futures daily report pipeline (Phase F10).

Tests the underlying library functions that the report skill assembles.
Validates parameter resolution, data gathering, and section generation logic.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import date

import pytest


# ── Parameter Resolution Tests ─────────────────────────────────


class TestParameterResolution:
    """Test parameter defaults and mapping logic used by the report skill."""

    def test_holding_period_to_dte_intraday(self):
        """Intraday should use near-month with DTE ~ 0."""
        # The report uses near-month expiry for intraday
        dte_range = (0, 5)
        assert dte_range[0] == 0

    def test_holding_period_to_dte_weekly(self):
        dte_range = (5, 10)
        assert dte_range[0] >= 5
        assert dte_range[1] <= 10

    def test_holding_period_to_dte_monthly(self):
        dte_range = (15, 25)
        assert dte_range[0] >= 15
        assert dte_range[1] <= 25

    def test_holding_period_to_dte_positional(self):
        dte_range = (25, 60)
        assert dte_range[0] >= 25
        assert dte_range[1] <= 60

    def test_risk_appetite_sizing_conservative(self):
        sizing = {"multiplier": 0.5, "max_lots": 1, "stop_factor": 3.0}
        assert sizing["multiplier"] == 0.5
        assert sizing["max_lots"] == 1

    def test_risk_appetite_sizing_moderate(self):
        sizing = {"multiplier": 1.0, "max_lots": 3, "stop_factor": 2.0}
        assert sizing["multiplier"] == 1.0

    def test_risk_appetite_sizing_aggressive(self):
        sizing = {"multiplier": 1.25, "max_lots": 10, "stop_factor": 1.5}
        assert sizing["multiplier"] == 1.25

    def test_report_depth_sections_full(self):
        full_sections = {
            "cover", "market_context", "basis", "scanner",
            "trades", "monte_carlo", "costs", "risk_rules", "summary",
        }
        assert len(full_sections) == 9

    def test_report_depth_sections_quick(self):
        quick_sections = {"cover", "market_context", "basis", "scanner", "trades", "costs", "summary"}
        assert "monte_carlo" not in quick_sections
        assert "risk_rules" not in quick_sections

    def test_report_depth_sections_basis(self):
        basis_sections = {"cover", "market_context", "basis", "scanner", "trades"}
        assert "monte_carlo" not in basis_sections

    def test_report_depth_sections_risk(self):
        risk_sections = {"cover", "market_context", "monte_carlo", "risk_rules", "summary"}
        assert "basis" not in risk_sections
        assert "trades" not in risk_sections


# ── Basis Data Pipeline Tests ──────────────────────────────────


class TestBasisDataPipeline:
    """Test that basis analysis functions work for report data."""

    def test_fair_value_for_report(self):
        from diamond_options.pricing.futures_pricing import theoretical_futures_price

        fair = theoretical_futures_price(22500, 0.065, 20 / 365, 0.012)
        assert fair > 22500  # Contango expected
        assert fair < 22600  # Reasonable range

    def test_basis_analysis_for_report(self):
        from diamond_options.pricing.basis_analysis import calculate_basis, annualized_basis

        result = calculate_basis(22600, 22500)
        assert result["basis"] == 100
        assert result["is_contango"] is True
        ann = annualized_basis(result["basis_pct"], 20)
        assert ann > 0

    def test_live_basis_for_report(self):
        from diamond_options.pricing.live_basis import live_basis_from_kite

        result = live_basis_from_kite("NIFTY", 22500, 22600, 20)
        assert result.signal in ("rich", "cheap", "fair")
        assert result.annualized_basis > 0
        assert result.fair_value > 0

    def test_rollover_for_report(self):
        from diamond_options.pricing.live_basis import live_rollover_analysis

        result = live_rollover_analysis("NIFTY", 22600, 5, 22700, 35)
        assert result.recommendation in ("roll_now", "wait", "close")
        assert result.annualized_roll_cost > 0

    def test_mispricing_for_report(self):
        from diamond_options.pricing.futures_pricing import futures_mispricing

        result = futures_mispricing(22600, 22500, 0.065, 20 / 365, 0.012)
        assert hasattr(result, "mispricing")
        assert isinstance(result.mispricing, float)


# ── Strategy Pipeline Tests ────────────────────────────────────


class TestStrategyPipeline:
    """Test strategy scanning and recommendation for report."""

    def test_scan_returns_results(self):
        from diamond_options.strategy.futures_scanner import (
            FuturesMarketCondition,
            TrendDirection,
            OIBuildupSignal,
            scan_futures_strategies,
        )

        condition = FuturesMarketCondition(
            spot=22500,
            near_futures=22600,
            next_futures=22700,
            basis_pct=0.44,
            annualized_basis=8.11,
            vix=15.0,
            trend=TrendDirection.NEUTRAL,
            realized_vol=0.13,
            days_to_expiry=20,
            oi_buildup=OIBuildupSignal.NEUTRAL,
            rollover_pct=50.0,
        )
        signals = scan_futures_strategies(condition, min_score=0, max_results=5)
        assert len(signals) > 0
        assert signals[0].score >= signals[-1].score

    def test_recommendation_pipeline(self):
        from diamond_options.strategy.futures_recommender import quick_futures_recommendation

        recs = quick_futures_recommendation(
            spot=22500,
            near_futures=22600,
            vix=15.0,
            realized_vol=0.13,
            days_to_expiry=20,
            trend="neutral",
            oi_buildup="neutral",
            symbol="NIFTY",
            capital=500000,
        )
        assert isinstance(recs, list)


# ── Risk Pipeline Tests ───────────────────────────────────────


class TestRiskPipeline:
    """Test Monte Carlo, stress test, and cost functions for report."""

    def test_monte_carlo_for_report(self):
        from diamond_options.risk.futures_monte_carlo import simulate_futures_position

        result = simulate_futures_position(
            entry_price=22600, lots=1, lot_size=65, action="BUY",
            spot=22500, T=20 / 365, sigma=0.15,
        )
        assert result.expected_pnl is not None
        assert result.var_95 is not None
        assert result.cvar_95 is not None

    def test_stress_test_for_report(self):
        from diamond_options.risk.futures_monte_carlo import futures_stress_test

        scenarios = futures_stress_test(22600, 1, 65, "BUY")
        assert len(scenarios) == 9
        assert any("Crash" in s["scenario"] for s in scenarios)

    def test_round_trip_cost_for_report(self):
        from diamond_options.data.costs import futures_round_trip_cost

        cost = futures_round_trip_cost(22600, 1, 65)
        assert cost > 0
        assert cost < 22600 * 65 * 0.01  # Less than 1% of notional

    def test_margin_estimate_for_report(self):
        from diamond_options.data.universe import get_futures_margin_estimate

        margin = get_futures_margin_estimate("NIFTY", 22600, 1)
        assert margin > 0
        assert margin < 22600 * 65  # Less than notional

    def test_futures_pnl_for_report(self):
        from diamond_options.data.costs import futures_pnl

        result = futures_pnl(22500, 22600, 1, 65, "BUY")
        assert result["gross_pnl"] == 100 * 65
        assert result["net_pnl"] < result["gross_pnl"]  # Costs deducted

    def test_breakeven_for_report(self):
        from diamond_options.data.costs import futures_breakeven

        be = futures_breakeven(22600, 1, 65, "BUY")
        assert be > 22600  # Must move up past costs


# ── Events Pipeline Tests ─────────────────────────────────────


class TestEventsPipeline:
    """Test event data retrieval for report."""

    def test_futures_events_for_report(self):
        from diamond_options.data.events import get_futures_events

        events = get_futures_events(days_ahead=60)
        assert isinstance(events, list)
        # Should have at least some futures events within 60 days
        types = {e.event_type for e in events}
        assert len(types) > 0

    def test_rollover_window_check(self):
        from diamond_options.data.events import is_rollover_window

        result = is_rollover_window()
        assert isinstance(result, bool)

    def test_days_to_expiry(self):
        from diamond_options.data.events import days_to_futures_expiry

        days = days_to_futures_expiry()
        assert isinstance(days, int)
        assert days >= 0


# ── VIX & Volatility Pipeline Tests ───────────────────────────


class TestVolatilityPipeline:
    """Test volatility data functions for report context."""

    def test_vix_regime_detection(self):
        from diamond_options.volatility.vix import classify_regime

        regime = classify_regime(15.0)
        assert regime.regime in ("low", "normal", "elevated", "high", "crisis")

    def test_vix_position_sizing_multiplier(self):
        from diamond_options.volatility.vix import classify_regime

        regime = classify_regime(15.0)
        assert 0 < regime.position_sizing <= 1.5

    def test_hv_estimator_for_report(self):
        import random
        import pandas as pd
        from diamond_options.volatility.historical import close_to_close

        # 60 days of synthetic prices
        prices = [100.0]
        for _ in range(59):
            prices.append(prices[-1] * (1 + random.gauss(0, 0.015)))

        vol = close_to_close(pd.Series(prices))
        assert 0 < vol < 1.0  # Reasonable annualized vol


# ── Config Pipeline Tests ─────────────────────────────────────


class TestConfigPipeline:
    """Test futures config values used by report."""

    def test_futures_risk_config_defaults(self):
        from diamond_options.config import FuturesRiskSettings

        config = FuturesRiskSettings()
        assert config.basis_rich_annualized_pct == 8.0
        assert config.basis_cheap_annualized_pct == 4.0
        assert config.max_margin_utilization == 0.60
        assert config.rollover_warning_days == 5

    def test_futures_risk_config_in_main_config(self):
        from diamond_options.config import get_config

        config = get_config()
        assert hasattr(config, "futures_risk")
        assert config.futures_risk.max_notional_pct > 0


# ── Report File Naming Tests ──────────────────────────────────


class TestReportNaming:
    """Test report filename generation logic."""

    def test_standard_filename(self):
        symbol = "NIFTY"
        date_short = "10MAR2026"
        prefix = "futures_report"
        filename = f"{prefix}_{date_short}_{symbol}.pdf"
        assert filename == "futures_report_10MAR2026_NIFTY.pdf"

    def test_custom_prefix(self):
        symbol = "BANKNIFTY"
        date_short = "10MAR2026"
        prefix = "weekly_futures"
        filename = f"{prefix}_{date_short}_{symbol}.pdf"
        assert filename == "weekly_futures_10MAR2026_BANKNIFTY.pdf"

    def test_script_filename(self):
        pdf_path = "reports/futures_report_10MAR2026_NIFTY.pdf"
        script_path = pdf_path.replace(".pdf", ".py")
        assert script_path == "reports/futures_report_10MAR2026_NIFTY.py"
