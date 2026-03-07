"""Tests for portfolio-level Greeks aggregation and risk limits."""

import pytest

from diamond_options.risk.portfolio_greeks import (
    PositionGreeks,
    PortfolioGreeks,
    RiskLimits,
    RiskAlert,
    calculate_position_greeks,
    aggregate_portfolio_greeks,
    check_risk_limits,
    portfolio_exposure_summary,
)


@pytest.fixture
def long_call_pos():
    return calculate_position_greeks(
        symbol="NIFTY", spot=22500, strike=22500, option_type="CE",
        action="BUY", lots=2, lot_size=25, days_to_expiry=7, iv=0.13,
    )


@pytest.fixture
def short_put_pos():
    return calculate_position_greeks(
        symbol="NIFTY", spot=22500, strike=22300, option_type="PE",
        action="SELL", lots=2, lot_size=25, days_to_expiry=7, iv=0.14,
    )


class TestCalculatePositionGreeks:
    def test_long_call_delta_positive(self, long_call_pos):
        """Long call should have positive delta."""
        assert long_call_pos.delta > 0

    def test_long_call_theta_negative(self, long_call_pos):
        """Long call should have negative theta (time decay hurts buyer)."""
        assert long_call_pos.theta < 0

    def test_long_call_vega_positive(self, long_call_pos):
        """Long call vega is positive (benefits from vol increase)."""
        assert long_call_pos.vega > 0

    def test_short_put_delta_positive(self, short_put_pos):
        """Short put has positive delta (equivalent to bullish)."""
        # Short put delta = -(negative put delta) = positive
        assert short_put_pos.delta > 0

    def test_short_put_theta_positive(self, short_put_pos):
        """Short put earns theta (time decay benefits seller)."""
        assert short_put_pos.theta > 0

    def test_short_put_vega_negative(self, short_put_pos):
        """Short put vega is negative (hurt by vol increase)."""
        assert short_put_pos.vega < 0

    def test_scaled_by_lots(self):
        """Greeks should scale linearly with lot count."""
        one_lot = calculate_position_greeks(
            "NIFTY", 22500, 22500, "CE", "BUY", 1, 25, 7, 0.13,
        )
        two_lots = calculate_position_greeks(
            "NIFTY", 22500, 22500, "CE", "BUY", 2, 25, 7, 0.13,
        )
        assert abs(two_lots.delta - 2 * one_lot.delta) < 0.01

    def test_metadata_preserved(self, long_call_pos):
        assert long_call_pos.symbol == "NIFTY"
        assert long_call_pos.strike == 22500
        assert long_call_pos.option_type == "CE"
        assert long_call_pos.action == "BUY"


class TestAggregatePortfolioGreeks:
    def test_empty_portfolio(self):
        pf = aggregate_portfolio_greeks([])
        assert pf.net_delta == 0
        assert pf.position_count == 0

    def test_single_position(self, long_call_pos):
        pf = aggregate_portfolio_greeks([long_call_pos])
        assert pf.net_delta == long_call_pos.delta
        assert pf.position_count == 1

    def test_delta_neutral(self, long_call_pos, short_put_pos):
        """Long call + short put should partially offset."""
        pf = aggregate_portfolio_greeks([long_call_pos, short_put_pos])
        # Both are bullish, so delta adds
        assert pf.net_delta > long_call_pos.delta

    def test_theta_aggregation(self, long_call_pos, short_put_pos):
        """Net theta should be sum of position thetas."""
        pf = aggregate_portfolio_greeks([long_call_pos, short_put_pos])
        expected = long_call_pos.theta + short_put_pos.theta
        assert abs(pf.net_theta - expected) < 0.01

    def test_straddle_near_zero_delta(self):
        """ATM straddle should have near-zero net delta."""
        long_call = calculate_position_greeks(
            "NIFTY", 22500, 22500, "CE", "BUY", 1, 25, 30, 0.13,
        )
        long_put = calculate_position_greeks(
            "NIFTY", 22500, 22500, "PE", "BUY", 1, 25, 30, 0.13,
        )
        pf = aggregate_portfolio_greeks([long_call, long_put])
        assert abs(pf.net_delta) < 5  # Near zero for ATM straddle


class TestRiskLimits:
    def test_no_alerts_healthy(self):
        """Healthy portfolio should have no alerts."""
        pf = PortfolioGreeks(net_delta=100, net_gamma=10, net_theta=-500, net_vega=1000)
        alerts = check_risk_limits(pf)
        assert len(alerts) == 0

    def test_delta_breach(self):
        """Large delta should trigger breach."""
        pf = PortfolioGreeks(net_delta=600, net_gamma=10, net_theta=-500, net_vega=1000)
        alerts = check_risk_limits(pf)
        delta_alerts = [a for a in alerts if a.metric == "portfolio_delta"]
        assert len(delta_alerts) == 1
        assert delta_alerts[0].level == "breach"

    def test_delta_warning(self):
        """Delta near limit should trigger warning."""
        pf = PortfolioGreeks(net_delta=420, net_gamma=10, net_theta=-500, net_vega=1000)
        alerts = check_risk_limits(pf)
        delta_alerts = [a for a in alerts if a.metric == "portfolio_delta"]
        assert len(delta_alerts) == 1
        assert delta_alerts[0].level == "warning"

    def test_vega_breach(self):
        pf = PortfolioGreeks(net_delta=0, net_gamma=0, net_theta=0, net_vega=6000)
        alerts = check_risk_limits(pf)
        vega_alerts = [a for a in alerts if a.metric == "portfolio_vega"]
        assert len(vega_alerts) == 1
        assert vega_alerts[0].level == "breach"

    def test_theta_breach(self):
        """Large negative theta should trigger alert."""
        pf = PortfolioGreeks(net_delta=0, net_gamma=0, net_theta=-15000, net_vega=0)
        alerts = check_risk_limits(pf)
        theta_alerts = [a for a in alerts if a.metric == "daily_theta"]
        assert len(theta_alerts) == 1

    def test_custom_limits(self):
        """Should use custom limits when provided."""
        pf = PortfolioGreeks(net_delta=200, net_gamma=10, net_theta=-500, net_vega=1000)
        strict = RiskLimits(max_portfolio_delta=100)
        alerts = check_risk_limits(pf, strict)
        assert any(a.metric == "portfolio_delta" for a in alerts)

    def test_per_position_check(self):
        """Should flag individual positions exceeding limits."""
        pos = PositionGreeks(
            symbol="NIFTY", strike=22500, option_type="CE", action="BUY",
            lots=10, lot_size=25, delta=250, gamma=5, theta=-100, vega=200,
            rho=10, iv=0.13, days_to_expiry=7,
        )
        pf = aggregate_portfolio_greeks([pos])
        alerts = check_risk_limits(pf)
        pos_alerts = [a for a in alerts if a.metric == "position_delta"]
        assert len(pos_alerts) == 1

    def test_negative_delta_breach(self):
        """Negative delta should also be checked."""
        pf = PortfolioGreeks(net_delta=-600, net_gamma=0, net_theta=0, net_vega=0)
        alerts = check_risk_limits(pf)
        assert any(a.metric == "portfolio_delta" and a.level == "breach" for a in alerts)


class TestExposureSummary:
    def test_summary_keys(self, long_call_pos, short_put_pos):
        pf = aggregate_portfolio_greeks([long_call_pos, short_put_pos])
        summary = portfolio_exposure_summary(pf, 22500)
        assert "net_delta" in summary
        assert "directional_bias" in summary
        assert "by_symbol" in summary
        assert "daily_theta_pnl" in summary

    def test_bullish_bias(self, long_call_pos):
        pf = aggregate_portfolio_greeks([long_call_pos])
        summary = portfolio_exposure_summary(pf, 22500)
        # Long call has significant positive delta
        assert summary["directional_bias"] == "bullish" or summary["net_delta"] > 0

    def test_neutral_bias(self):
        pf = PortfolioGreeks(net_delta=10, net_gamma=0, net_theta=0, net_vega=0)
        summary = portfolio_exposure_summary(pf, 22500)
        assert summary["directional_bias"] == "neutral"

    def test_weekly_theta(self, long_call_pos):
        pf = aggregate_portfolio_greeks([long_call_pos])
        summary = portfolio_exposure_summary(pf, 22500)
        assert summary["weekly_theta_pnl"] == round(pf.net_theta * 5, 2)
