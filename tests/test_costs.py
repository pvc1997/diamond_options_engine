"""Tests for options transaction cost model.

Verifies exact INR amounts for Indian F&O market costs.
"""

from diamond_options.data.costs import (
    calculate_options_costs,
    calculate_futures_costs,
    spread_round_trip_cost,
)


class TestOptionsCosts:
    def test_zero_amount(self):
        cost = calculate_options_costs("BUY", 0)
        assert cost.total == 0

    def test_buy_side_no_stt(self):
        """Options buy side has zero STT."""
        cost = calculate_options_costs("BUY", 10000)
        assert cost.stt == 0.0

    def test_sell_side_has_stt(self):
        """Options sell side has 0.0625% STT."""
        cost = calculate_options_costs("SELL", 10000)
        assert cost.stt == round(10000 * 0.000625, 2)

    def test_brokerage_flat_20(self):
        """Discount broker flat Rs. 20 per order."""
        cost = calculate_options_costs("BUY", 50000)
        assert cost.brokerage == 20.0

    def test_gst_on_brokerage(self):
        """GST is 18% of (brokerage + exchange + SEBI)."""
        cost = calculate_options_costs("BUY", 10000)
        expected_base = 20.0 + 10000 * 0.000495 + 10000 * 0.00001
        expected_gst = round(expected_base * 0.18, 2)
        assert cost.gst == expected_gst

    def test_stamp_duty_buy_only(self):
        """Stamp duty only on buy side."""
        buy = calculate_options_costs("BUY", 10000)
        sell = calculate_options_costs("SELL", 10000)
        assert buy.stamp_duty > 0
        assert sell.stamp_duty == 0

    def test_total_is_sum_of_parts(self):
        cost = calculate_options_costs("BUY", 25000)
        expected = (
            cost.brokerage + cost.gst + cost.stt + cost.exchange_fees
            + cost.sebi_charges + cost.stamp_duty + cost.slippage
        )
        assert abs(cost.total - expected) < 0.01

    def test_buy_cheaper_than_sell(self):
        """Buy should be cheaper (no STT) for same premium."""
        buy = calculate_options_costs("BUY", 10000)
        sell = calculate_options_costs("SELL", 10000)
        assert buy.total < sell.total

    def test_realistic_nifty_trade(self):
        """Nifty ATM option: 25 lot * 130 premium = Rs. 3250."""
        premium = 25 * 130  # 3250
        buy = calculate_options_costs("BUY", premium)
        assert buy.total > 20  # At least brokerage
        assert buy.total < 50  # Should be modest

    def test_large_premium(self):
        """Large premium trade should scale costs proportionally."""
        small = calculate_options_costs("SELL", 1000)
        large = calculate_options_costs("SELL", 100000)
        # STT and exchange fees scale, brokerage is flat
        assert large.stt > small.stt * 50


class TestFuturesCosts:
    def test_futures_stt_lower(self):
        """Futures STT (0.0125%) is lower than options STT (0.0625%)."""
        opt = calculate_options_costs("SELL", 100000)
        fut = calculate_futures_costs("SELL", 100000)
        assert fut.stt < opt.stt

    def test_futures_buy_no_stt(self):
        cost = calculate_futures_costs("BUY", 100000)
        assert cost.stt == 0.0


class TestSpreadCost:
    def test_two_leg_spread(self):
        """Bull call spread: buy lower + sell higher."""
        legs = [
            {"action": "BUY", "premium_amount": 3250},   # Buy 22400 CE
            {"action": "SELL", "premium_amount": 2000},   # Sell 22600 CE
        ]
        cost = spread_round_trip_cost(legs)
        assert cost > 80  # At least 4 * Rs. 20 brokerage
        assert isinstance(cost, float)

    def test_four_leg_iron_condor(self):
        """Iron condor: 4 legs, 8 orders total (open + close)."""
        legs = [
            {"action": "SELL", "premium_amount": 2000},
            {"action": "BUY", "premium_amount": 1000},
            {"action": "SELL", "premium_amount": 2500},
            {"action": "BUY", "premium_amount": 1500},
        ]
        cost = spread_round_trip_cost(legs)
        assert cost > 160  # At least 8 * Rs. 20 brokerage
