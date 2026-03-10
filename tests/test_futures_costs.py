"""Tests for futures cost enhancements (P&L, breakeven, margin)."""

import pytest

from diamond_options.data.costs import (
    futures_breakeven,
    futures_margin_with_costs,
    futures_pnl,
    futures_round_trip_cost,
)


class TestFuturesRoundTripCost:
    def test_basic(self):
        # NIFTY at 22650, 1 lot of 65
        cost = futures_round_trip_cost(22650.0, 1, 65)
        assert cost > 0
        # Should be sum of BUY + SELL costs
        assert cost > 40  # At least 2 × Rs.20 brokerage

    def test_multiple_lots(self):
        cost_1 = futures_round_trip_cost(22650.0, 1, 65)
        cost_2 = futures_round_trip_cost(22650.0, 2, 65)
        # 2 lots costs more than 1 (but brokerage stays flat)
        assert cost_2 > cost_1


class TestFuturesBreakeven:
    def test_long_breakeven_above_entry(self):
        be = futures_breakeven(22650.0, 1, 65, "BUY")
        assert be > 22650.0  # Must earn enough to cover costs

    def test_short_breakeven_below_entry(self):
        be = futures_breakeven(22650.0, 1, 65, "SELL")
        assert be < 22650.0

    def test_zero_quantity(self):
        be = futures_breakeven(22650.0, 0, 65, "BUY")
        assert be == 22650.0

    def test_long_short_symmetric(self):
        be_long = futures_breakeven(22650.0, 1, 65, "BUY")
        be_short = futures_breakeven(22650.0, 1, 65, "SELL")
        # Cost per unit should be same distance from entry
        diff_long = be_long - 22650.0
        diff_short = 22650.0 - be_short
        assert abs(diff_long - diff_short) < 0.1


class TestFuturesPnl:
    def test_profitable_long(self):
        result = futures_pnl(22650.0, 22750.0, 1, 65, "BUY")
        assert result["gross_pnl"] == (22750.0 - 22650.0) * 65
        assert result["net_pnl"] < result["gross_pnl"]  # Costs reduce profit
        assert result["net_pnl"] > 0  # Still profitable
        assert result["total_costs"] > 0

    def test_losing_long(self):
        result = futures_pnl(22650.0, 22600.0, 1, 65, "BUY")
        assert result["gross_pnl"] == (22600.0 - 22650.0) * 65
        assert result["net_pnl"] < 0

    def test_profitable_short(self):
        result = futures_pnl(22650.0, 22550.0, 1, 65, "SELL")
        assert result["gross_pnl"] == (22650.0 - 22550.0) * 65
        assert result["net_pnl"] > 0

    def test_losing_short(self):
        result = futures_pnl(22650.0, 22750.0, 1, 65, "SELL")
        assert result["gross_pnl"] == (22650.0 - 22750.0) * 65
        assert result["net_pnl"] < 0

    def test_pnl_per_lot(self):
        result = futures_pnl(22650.0, 22750.0, 2, 65, "BUY")
        assert result["pnl_per_lot"] == round(result["net_pnl"] / 2, 2)

    def test_roi_on_notional(self):
        result = futures_pnl(22650.0, 22750.0, 1, 65, "BUY")
        expected_roi = result["net_pnl"] / (22650.0 * 65) * 100
        assert abs(result["roi_on_notional_pct"] - round(expected_roi, 4)) < 0.01

    def test_quantity(self):
        result = futures_pnl(22650.0, 22750.0, 2, 65, "BUY")
        assert result["quantity"] == 130

    def test_entry_exit_costs_separate(self):
        result = futures_pnl(22650.0, 22750.0, 1, 65, "BUY")
        assert result["entry_cost"] > 0
        assert result["exit_cost"] > 0
        assert abs(result["total_costs"] - result["entry_cost"] - result["exit_cost"]) < 0.01


class TestFuturesMarginWithCosts:
    def test_basic(self):
        result = futures_margin_with_costs(22650.0, 1, 65, 0.10)
        assert result["notional"] == 22650.0 * 65
        assert result["margin"] == result["notional"] * 0.10
        assert result["entry_cost"] > 0
        assert result["total_required"] == result["margin"] + result["entry_cost"]

    def test_higher_margin_pct(self):
        r1 = futures_margin_with_costs(22650.0, 1, 65, 0.10)
        r2 = futures_margin_with_costs(22650.0, 1, 65, 0.20)
        assert r2["margin"] > r1["margin"]
        assert r2["total_required"] > r1["total_required"]

    def test_multiple_lots(self):
        r1 = futures_margin_with_costs(22650.0, 1, 65, 0.10)
        r2 = futures_margin_with_costs(22650.0, 3, 65, 0.10)
        assert r2["margin"] == r1["margin"] * 3

    def test_margin_pct_preserved(self):
        result = futures_margin_with_costs(22650.0, 1, 65, 0.15)
        assert result["margin_pct"] == 0.15
