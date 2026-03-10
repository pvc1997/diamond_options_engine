"""Tests for futures portfolio risk management."""

import pytest

from diamond_options.risk.futures_risk import (
    FuturesPortfolioRisk,
    FuturesPositionRisk,
    FuturesRiskAlert,
    FuturesRiskLevel,
    FuturesRiskLimits,
    aggregate_futures_risk,
    calculate_futures_position_risk,
    futures_exposure_summary,
)


@pytest.fixture
def long_nifty_risk() -> FuturesPositionRisk:
    return calculate_futures_position_risk(
        symbol="NIFTY",
        action="BUY",
        lots=2,
        lot_size=65,
        entry_price=22500.0,
        current_price=22650.0,
        spot_price=22550.0,
        days_to_expiry=15,
        capital=500000.0,
    )


@pytest.fixture
def short_reliance_risk() -> FuturesPositionRisk:
    return calculate_futures_position_risk(
        symbol="RELIANCE",
        action="SELL",
        lots=1,
        lot_size=250,
        entry_price=2800.0,
        current_price=2750.0,
        spot_price=2740.0,
        days_to_expiry=10,
        capital=500000.0,
    )


class TestCalculatePositionRisk:
    def test_long_position_pnl(self, long_nifty_risk):
        # (22650 - 22500) × 2 × 65 = 19500
        assert long_nifty_risk.unrealized_pnl == 19500.0

    def test_short_position_pnl(self, short_reliance_risk):
        # (2800 - 2750) × 1 × 250 = 12500 (short profits when price drops)
        assert short_reliance_risk.unrealized_pnl == 12500.0

    def test_notional_value(self, long_nifty_risk):
        expected = 22650.0 * 2 * 65
        assert long_nifty_risk.notional_value == expected

    def test_margin_required(self, long_nifty_risk):
        assert long_nifty_risk.margin_required > 0

    def test_margin_utilization(self, long_nifty_risk):
        assert long_nifty_risk.margin_utilization_pct > 0
        assert long_nifty_risk.margin_utilization_pct < 100

    def test_basis_pct(self, long_nifty_risk):
        # (22650 - 22550) / 22550 × 100
        assert long_nifty_risk.basis_pct > 0

    def test_days_to_expiry(self, long_nifty_risk):
        assert long_nifty_risk.days_to_expiry == 15

    def test_action_preserved(self, long_nifty_risk, short_reliance_risk):
        assert long_nifty_risk.action == "BUY"
        assert short_reliance_risk.action == "SELL"

    def test_losing_long_position(self):
        risk = calculate_futures_position_risk(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22300,
            spot_price=22250, days_to_expiry=10,
        )
        assert risk.unrealized_pnl < 0

    def test_losing_short_position(self):
        risk = calculate_futures_position_risk(
            symbol="RELIANCE", action="SELL", lots=1, lot_size=250,
            entry_price=2800, current_price=2850,
            spot_price=2840, days_to_expiry=10,
        )
        assert risk.unrealized_pnl < 0


class TestAggregateFuturesRisk:
    def test_aggregate_two_positions(self, long_nifty_risk, short_reliance_risk):
        portfolio = aggregate_futures_risk(
            [long_nifty_risk, short_reliance_risk], capital=500000.0,
        )
        assert portfolio.position_count == 2
        assert portfolio.long_count == 1
        assert portfolio.short_count == 1

    def test_total_pnl(self, long_nifty_risk, short_reliance_risk):
        portfolio = aggregate_futures_risk(
            [long_nifty_risk, short_reliance_risk], capital=500000.0,
        )
        expected = long_nifty_risk.unrealized_pnl + short_reliance_risk.unrealized_pnl
        assert portfolio.total_unrealized_pnl == expected

    def test_notional_long_short(self, long_nifty_risk, short_reliance_risk):
        portfolio = aggregate_futures_risk(
            [long_nifty_risk, short_reliance_risk], capital=500000.0,
        )
        assert portfolio.total_notional_long == long_nifty_risk.notional_value
        assert portfolio.total_notional_short == short_reliance_risk.notional_value

    def test_gross_notional(self, long_nifty_risk, short_reliance_risk):
        portfolio = aggregate_futures_risk(
            [long_nifty_risk, short_reliance_risk], capital=500000.0,
        )
        assert portfolio.gross_notional == (
            long_nifty_risk.notional_value + short_reliance_risk.notional_value
        )

    def test_margin_utilization(self, long_nifty_risk, short_reliance_risk):
        portfolio = aggregate_futures_risk(
            [long_nifty_risk, short_reliance_risk], capital=500000.0,
        )
        assert portfolio.margin_utilization_pct > 0

    def test_by_symbol(self, long_nifty_risk, short_reliance_risk):
        portfolio = aggregate_futures_risk(
            [long_nifty_risk, short_reliance_risk], capital=500000.0,
        )
        assert "NIFTY" in portfolio.by_symbol
        assert "RELIANCE" in portfolio.by_symbol

    def test_empty_portfolio(self):
        portfolio = aggregate_futures_risk([], capital=500000.0)
        assert portfolio.position_count == 0
        assert portfolio.risk_level == FuturesRiskLevel.LOW

    def test_directional_bias_bullish(self, long_nifty_risk):
        portfolio = aggregate_futures_risk([long_nifty_risk], capital=500000.0)
        assert portfolio.directional_bias == "bullish"

    def test_directional_bias_bearish(self, short_reliance_risk):
        portfolio = aggregate_futures_risk([short_reliance_risk], capital=500000.0)
        assert portfolio.directional_bias == "bearish"


class TestFuturesRiskLimits:
    def test_notional_breach(self, long_nifty_risk):
        limits = FuturesRiskLimits(max_notional_exposure=1000000.0)
        portfolio = aggregate_futures_risk(
            [long_nifty_risk], capital=500000.0, limits=limits,
        )
        breach_alerts = [a for a in portfolio.alerts if a.metric == "notional_exposure"]
        assert len(breach_alerts) > 0

    def test_margin_breach(self, long_nifty_risk, short_reliance_risk):
        limits = FuturesRiskLimits(max_margin_utilization_pct=5.0)
        portfolio = aggregate_futures_risk(
            [long_nifty_risk, short_reliance_risk], capital=500000.0, limits=limits,
        )
        margin_alerts = [a for a in portfolio.alerts if a.metric == "margin_utilization"]
        assert len(margin_alerts) > 0

    def test_unrealized_loss_alert(self):
        losing = calculate_futures_position_risk(
            symbol="NIFTY", action="BUY", lots=5, lot_size=65,
            entry_price=22500, current_price=22000,
            spot_price=21950, days_to_expiry=10, capital=500000.0,
        )
        limits = FuturesRiskLimits(max_unrealized_loss_pct=2.0)
        portfolio = aggregate_futures_risk([losing], capital=500000.0, limits=limits)
        loss_alerts = [a for a in portfolio.alerts if a.metric == "unrealized_loss"]
        assert len(loss_alerts) > 0
        assert portfolio.risk_level == FuturesRiskLevel.CRITICAL

    def test_dte_warning(self):
        near_expiry = calculate_futures_position_risk(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22550,
            spot_price=22530, days_to_expiry=1,
        )
        portfolio = aggregate_futures_risk([near_expiry], capital=500000.0)
        dte_alerts = [a for a in portfolio.alerts if a.metric == "expiry_proximity"]
        assert len(dte_alerts) > 0

    def test_basis_deviation_warning(self):
        wide_basis = calculate_futures_position_risk(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=23000, current_price=23000,
            spot_price=22500, days_to_expiry=20,
        )
        limits = FuturesRiskLimits(max_basis_deviation_pct=1.0)
        portfolio = aggregate_futures_risk([wide_basis], capital=500000.0, limits=limits)
        basis_alerts = [a for a in portfolio.alerts if a.metric == "basis_deviation"]
        assert len(basis_alerts) > 0

    def test_no_alerts_healthy(self):
        # Two positions so single_position check doesn't fire (each < 100% of total margin)
        p1 = calculate_futures_position_risk(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22520,
            spot_price=22510, days_to_expiry=20, capital=5000000.0,
        )
        p2 = calculate_futures_position_risk(
            symbol="RELIANCE", action="BUY", lots=1, lot_size=250,
            entry_price=2800, current_price=2810,
            spot_price=2805, days_to_expiry=20, capital=5000000.0,
        )
        # Use high single_position limit to avoid that alert
        limits = FuturesRiskLimits(max_single_position_pct=100.0, max_concentration_pct=100.0)
        portfolio = aggregate_futures_risk([p1, p2], capital=5000000.0, limits=limits)
        assert portfolio.risk_level == FuturesRiskLevel.LOW


class TestFuturesExposureSummary:
    def test_summary_fields(self, long_nifty_risk, short_reliance_risk):
        portfolio = aggregate_futures_risk(
            [long_nifty_risk, short_reliance_risk], capital=500000.0,
        )
        summary = futures_exposure_summary(portfolio, capital=500000.0)
        assert "total_notional_long" in summary
        assert "total_notional_short" in summary
        assert "net_notional" in summary
        assert "available_margin" in summary
        assert "risk_level" in summary
        assert "by_symbol" in summary
        assert "alerts" in summary

    def test_available_margin(self, long_nifty_risk):
        portfolio = aggregate_futures_risk([long_nifty_risk], capital=500000.0)
        summary = futures_exposure_summary(portfolio, capital=500000.0)
        assert summary["available_margin"] == round(500000 - portfolio.total_margin, 2)
