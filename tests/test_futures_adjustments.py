"""Tests for futures position adjustment advisor."""

import pytest

from diamond_options.risk.futures_adjustments import (
    FuturesAdjustment,
    FuturesAdjustmentAnalysis,
    FuturesAdjustmentType,
    analyze_futures_position,
    futures_expiry_checklist,
)


class TestAnalyzeFuturesPosition:
    def test_healthy_profitable_position(self):
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=2, lot_size=65,
            entry_price=22500, current_price=23000,
            spot_price=22950, days_to_expiry=15,
        )
        assert result.position_status == "healthy"
        assert isinstance(result.adjustments, list)

    def test_in_trouble_large_loss(self):
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=5, lot_size=65,
            entry_price=22500, current_price=21500,
            spot_price=21450, days_to_expiry=10,
            capital=500000.0,
        )
        assert result.position_status == "in_trouble"
        # Should recommend closing
        close_adj = [a for a in result.adjustments if a.type == FuturesAdjustmentType.CLOSE]
        assert len(close_adj) > 0
        assert close_adj[0].urgency == "immediate"

    def test_at_risk_moderate_loss(self):
        # move_pct = -2.22% → at_risk (threshold is -2.0)
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=2, lot_size=65,
            entry_price=22500, current_price=22000,
            spot_price=21950, days_to_expiry=10,
            capital=5000000.0,  # Large capital so pnl_pct < 3%
        )
        assert result.position_status == "at_risk"

    def test_challenged_near_expiry(self):
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22400,
            spot_price=22380, days_to_expiry=2,
        )
        assert result.position_status in ("challenged", "at_risk")

    def test_roll_suggested_near_expiry(self):
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22550,
            spot_price=22530, days_to_expiry=2,
        )
        roll_adj = [a for a in result.adjustments if a.type == FuturesAdjustmentType.ROLL_NEXT]
        assert len(roll_adj) > 0

    def test_profit_taking_suggested(self):
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22000, current_price=22600,
            spot_price=22550, days_to_expiry=15,
        )
        assert result.position_status == "healthy"
        close_adj = [a for a in result.adjustments if a.type == FuturesAdjustmentType.CLOSE]
        assert len(close_adj) > 0

    def test_scale_down_multiple_lots(self):
        # move_pct = (22250-22500)/22500*100 = -1.11% → challenged
        # pnl = -250*4*65 = -65000, pnl_pct = -65000/5000000 = -1.3%
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=4, lot_size=65,
            entry_price=22500, current_price=22250,
            spot_price=22230, days_to_expiry=10,
            capital=5000000.0,
        )
        assert result.position_status in ("challenged", "at_risk")
        scale_adj = [a for a in result.adjustments if a.type == FuturesAdjustmentType.SCALE_DOWN]
        assert len(scale_adj) > 0

    def test_hedge_suggested_challenged(self):
        # move_pct = -1.11%, pnl_pct = -0.65% → challenged
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=2, lot_size=65,
            entry_price=22500, current_price=22250,
            spot_price=22230, days_to_expiry=10,
            capital=5000000.0,
        )
        assert result.position_status in ("challenged", "at_risk")
        hedge_adj = [a for a in result.adjustments if a.type == FuturesAdjustmentType.ADD_HEDGE]
        assert len(hedge_adj) > 0

    def test_convert_spread_suggested(self):
        # move_pct = -1.11%, pnl_pct = -0.65% → challenged with >5 DTE
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=2, lot_size=65,
            entry_price=22500, current_price=22250,
            spot_price=22230, days_to_expiry=15,
            capital=5000000.0,
        )
        assert result.position_status == "challenged"
        spread_adj = [a for a in result.adjustments if a.type == FuturesAdjustmentType.CONVERT_SPREAD]
        assert len(spread_adj) > 0

    def test_stop_suggestion_for_profitable(self):
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22400, current_price=22550,
            spot_price=22530, days_to_expiry=15,
            stop_loss=0,
        )
        stop_adj = [a for a in result.adjustments if a.type == FuturesAdjustmentType.ADD_STOP]
        assert len(stop_adj) > 0

    def test_short_position_analysis(self):
        # For short: direction=-1, move_pct = (22700-22500)/22500*100*(-1) = -0.89%
        # pnl = (22700-22500)*1*65*(-1) = -13000, pnl_pct = -13000/500000 = -2.6%
        result = analyze_futures_position(
            symbol="NIFTY", action="SELL", lots=1, lot_size=65,
            entry_price=22500, current_price=22700,
            spot_price=22680, days_to_expiry=10,
            capital=500000.0,
        )
        # Price went up — bad for short; pnl_pct at -2.6% triggers at_risk
        assert result.position_status in ("at_risk", "in_trouble")

    def test_stop_hit_triggers_in_trouble(self):
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22100,
            spot_price=22080, days_to_expiry=10,
            stop_loss=22200,
        )
        assert result.position_status == "in_trouble"

    def test_target_hit_close_suggested(self):
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=23100,
            spot_price=23050, days_to_expiry=15,
            target=23000,
        )
        close_adj = [a for a in result.adjustments if a.type == FuturesAdjustmentType.CLOSE]
        assert len(close_adj) > 0

    def test_has_trigger(self):
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22550,
            spot_price=22530, days_to_expiry=15,
        )
        assert len(result.trigger) > 0

    def test_has_do_nothing_risk(self):
        result = analyze_futures_position(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22550,
            spot_price=22530, days_to_expiry=15,
        )
        assert len(result.do_nothing_risk) > 0


class TestFuturesExpiryChecklist:
    def test_index_expiry_day(self):
        checklist = futures_expiry_checklist(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22600,
            spot_price=22580, days_to_expiry=0,
        )
        assert any("cash-settle" in item.lower() for item in checklist)

    def test_stock_expiry_day_delivery_warning(self):
        checklist = futures_expiry_checklist(
            symbol="RELIANCE", action="BUY", lots=1, lot_size=250,
            entry_price=2800, current_price=2850,
            spot_price=2840, days_to_expiry=0,
        )
        assert any("physical" in item.lower() or "delivery" in item.lower() for item in checklist)

    def test_near_expiry_roll_suggestion(self):
        checklist = futures_expiry_checklist(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22550,
            spot_price=22530, days_to_expiry=1,
        )
        assert any("roll" in item.lower() for item in checklist)

    def test_profitable_position_note(self):
        checklist = futures_expiry_checklist(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22700,
            spot_price=22680, days_to_expiry=0,
        )
        assert any("profitable" in item.lower() or "profit" in item.lower() for item in checklist)

    def test_losing_position_note(self):
        checklist = futures_expiry_checklist(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22300,
            spot_price=22280, days_to_expiry=0,
        )
        assert any("loss" in item.lower() for item in checklist)

    def test_stock_delivery_margin_estimate(self):
        checklist = futures_expiry_checklist(
            symbol="RELIANCE", action="BUY", lots=1, lot_size=250,
            entry_price=2800, current_price=2850,
            spot_price=2840, days_to_expiry=0,
        )
        assert any("margin" in item.lower() or "delivery" in item.lower() for item in checklist)

    def test_no_immediate_action_far_expiry(self):
        checklist = futures_expiry_checklist(
            symbol="NIFTY", action="BUY", lots=1, lot_size=65,
            entry_price=22500, current_price=22500,
            spot_price=22490, days_to_expiry=20,
        )
        # With no P&L and far expiry, should get fallback message
        assert any("no immediate" in item.lower() for item in checklist)
