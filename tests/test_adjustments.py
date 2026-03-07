"""Tests for position adjustment advisor."""

import pytest

from diamond_options.risk.adjustments import (
    AdjustmentType,
    AdjustmentAnalysis,
    Adjustment,
    analyze_position,
    expiry_day_checklist,
)


class TestAnalyzePosition:
    def test_healthy_position(self):
        """Healthy position should return 'healthy' status."""
        result = analyze_position(
            symbol="NIFTY", strategy="iron_condor",
            spot=22500, entry_spot=22500,
            strikes=[22200, 22300, 22700, 22800],
            option_types=["PE", "PE", "CE", "CE"],
            actions=["BUY", "SELL", "SELL", "BUY"],
            premiums=[18, 35, 45, 22],
            days_to_expiry=5,
            current_pnl=500,
            max_loss=-5000,
        )
        assert result.position_status == "healthy"

    def test_challenged_position(self):
        """Position with moderate adverse move should be 'challenged'."""
        result = analyze_position(
            symbol="NIFTY", strategy="iron_condor",
            spot=22750, entry_spot=22500,
            strikes=[22200, 22300, 22700, 22800],
            option_types=["PE", "PE", "CE", "CE"],
            actions=["BUY", "SELL", "SELL", "BUY"],
            premiums=[18, 35, 45, 22],
            days_to_expiry=5,
            current_pnl=-1500,
            max_loss=-5000,
        )
        assert result.position_status in ("challenged", "at_risk")

    def test_at_risk_short_breached(self):
        """Breached short strike should be 'at_risk'."""
        result = analyze_position(
            symbol="NIFTY", strategy="bull_put_spread",
            spot=22250, entry_spot=22500,
            strikes=[22300, 22200],
            option_types=["PE", "PE"],
            actions=["SELL", "BUY"],
            premiums=[35, 18],
            days_to_expiry=5,
            current_pnl=-2500,
            max_loss=-5000,
        )
        assert result.position_status in ("at_risk", "in_trouble")

    def test_in_trouble_deep_loss(self):
        """Deep loss near expiry should be 'in_trouble'."""
        result = analyze_position(
            symbol="NIFTY", strategy="bull_put_spread",
            spot=22100, entry_spot=22500,
            strikes=[22300, 22200],
            option_types=["PE", "PE"],
            actions=["SELL", "BUY"],
            premiums=[35, 18],
            days_to_expiry=1,
            current_pnl=-4000,
            max_loss=-5000,
        )
        assert result.position_status == "in_trouble"

    def test_returns_adjustments(self):
        """Should return at least one adjustment for challenged positions."""
        result = analyze_position(
            symbol="NIFTY", strategy="iron_condor",
            spot=22750, entry_spot=22500,
            strikes=[22200, 22300, 22700, 22800],
            option_types=["PE", "PE", "CE", "CE"],
            actions=["BUY", "SELL", "SELL", "BUY"],
            premiums=[18, 35, 45, 22],
            days_to_expiry=5,
            current_pnl=-2500,
            max_loss=-5000,
        )
        assert len(result.adjustments) > 0

    def test_take_profit_suggestion(self):
        """Profitable position should suggest taking profit."""
        result = analyze_position(
            symbol="NIFTY", strategy="iron_condor",
            spot=22500, entry_spot=22500,
            strikes=[22200, 22300, 22700, 22800],
            option_types=["PE", "PE", "CE", "CE"],
            actions=["BUY", "SELL", "SELL", "BUY"],
            premiums=[18, 35, 45, 22],
            days_to_expiry=3,
            current_pnl=3000,
            max_loss=-5000,
        )
        close_adjustments = [a for a in result.adjustments if a.type == AdjustmentType.CLOSE]
        assert len(close_adjustments) > 0

    def test_immediate_urgency_in_trouble(self):
        """In-trouble positions should have 'immediate' urgency adjustments."""
        result = analyze_position(
            symbol="NIFTY", strategy="bull_put_spread",
            spot=22050, entry_spot=22500,
            strikes=[22300, 22200],
            option_types=["PE", "PE"],
            actions=["SELL", "BUY"],
            premiums=[35, 18],
            days_to_expiry=1,
            current_pnl=-4200,
            max_loss=-5000,
        )
        immediate = [a for a in result.adjustments if a.urgency == "immediate"]
        assert len(immediate) > 0

    def test_trigger_message(self):
        result = analyze_position(
            symbol="NIFTY", strategy="iron_condor",
            spot=22800, entry_spot=22500,
            strikes=[22200, 22300, 22700, 22800],
            option_types=["PE", "PE", "CE", "CE"],
            actions=["BUY", "SELL", "SELL", "BUY"],
            premiums=[18, 35, 45, 22],
            days_to_expiry=5,
            current_pnl=-3000,
            max_loss=-5000,
        )
        assert result.trigger  # Should have a trigger message

    def test_do_nothing_risk(self):
        result = analyze_position(
            symbol="NIFTY", strategy="iron_condor",
            spot=22500, entry_spot=22500,
            strikes=[22200, 22300, 22700, 22800],
            option_types=["PE", "PE", "CE", "CE"],
            actions=["BUY", "SELL", "SELL", "BUY"],
            premiums=[18, 35, 45, 22],
            days_to_expiry=5,
            current_pnl=500,
            max_loss=-5000,
        )
        assert "LOW RISK" in result.do_nothing_risk

    def test_add_hedge_for_naked(self):
        """Naked short positions should get hedge suggestions."""
        result = analyze_position(
            symbol="NIFTY", strategy="short_strangle",
            spot=22800, entry_spot=22500,
            strikes=[22700, 22300],
            option_types=["CE", "PE"],
            actions=["SELL", "SELL"],
            premiums=[45, 35],
            days_to_expiry=5,
            current_pnl=-3000,
            max_loss=-50000,
        )
        hedge = [a for a in result.adjustments if a.type == AdjustmentType.ADD_HEDGE]
        assert len(hedge) > 0


class TestExpiryDayChecklist:
    def test_itm_short_warning(self):
        """Short ITM option should warn about exercise STT."""
        checklist = expiry_day_checklist(
            strategy="bull_put_spread",
            spot=22200,
            strikes=[22300, 22100],
            option_types=["PE", "PE"],
            actions=["SELL", "BUY"],
        )
        assert any("STT" in item for item in checklist)

    def test_otm_no_action(self):
        """All OTM should say no action needed."""
        checklist = expiry_day_checklist(
            strategy="iron_condor",
            spot=22500,
            strikes=[22200, 22300, 22700, 22800],
            option_types=["PE", "PE", "CE", "CE"],
            actions=["BUY", "SELL", "SELL", "BUY"],
        )
        assert any("expire worthless" in item.lower() or "no action" in item.lower()
                    for item in checklist)

    def test_near_atm_pin_risk(self):
        """Short option near ATM should warn about pin risk."""
        checklist = expiry_day_checklist(
            strategy="short_straddle",
            spot=22502,
            strikes=[22500, 22500],
            option_types=["CE", "PE"],
            actions=["SELL", "SELL"],
        )
        assert any("pin risk" in item.lower() for item in checklist)

    def test_deadline_included(self):
        """Should always include the 3:00 PM deadline."""
        checklist = expiry_day_checklist(
            strategy="long_call",
            spot=22600,
            strikes=[22500],
            option_types=["CE"],
            actions=["BUY"],
        )
        assert any("3:00 PM" in item for item in checklist)
