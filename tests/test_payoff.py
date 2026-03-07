"""Tests for payoff and P&L calculator."""

import math

import pytest

from diamond_options.pricing.payoff import (
    Leg,
    leg_payoff_at_expiry,
    position_payoff_at_expiry,
    payoff_curve,
    analyze_payoff,
    expected_value,
)


class TestSingleLeg:
    def test_long_call_itm(self):
        """Long call profit when ITM."""
        leg = Leg(strike=22500, option_type="CE", action="BUY", premium=130, lots=1, lot_size=25)
        pnl = leg_payoff_at_expiry(leg, spot=22700)
        # (22700 - 22500 - 130) * 25 = 70 * 25 = 1750
        assert pnl == (200 - 130) * 25

    def test_long_call_otm(self):
        """Long call loss when OTM."""
        leg = Leg(strike=22500, option_type="CE", action="BUY", premium=130, lots=1, lot_size=25)
        pnl = leg_payoff_at_expiry(leg, spot=22300)
        # Max loss = premium paid = -130 * 25
        assert pnl == -130 * 25

    def test_short_put_otm(self):
        """Short put profit when OTM — keep full premium."""
        leg = Leg(strike=22300, option_type="PE", action="SELL", premium=35, lots=1, lot_size=25)
        pnl = leg_payoff_at_expiry(leg, spot=22500)
        assert pnl == 35 * 25

    def test_short_put_itm(self):
        """Short put loss when ITM."""
        leg = Leg(strike=22500, option_type="PE", action="SELL", premium=100, lots=1, lot_size=25)
        pnl = leg_payoff_at_expiry(leg, spot=22200)
        # (100 - 300) * 25 = -200 * 25 = -5000
        assert pnl == (100 - 300) * 25


class TestMultiLeg:
    def test_bull_call_spread_profit(self):
        """Bull call spread: buy lower, sell higher."""
        legs = [
            Leg(strike=22400, option_type="CE", action="BUY", premium=195, lots=1, lot_size=25),
            Leg(strike=22600, option_type="CE", action="SELL", premium=80, lots=1, lot_size=25),
        ]
        # Max profit above 22600: (200 - 115) * 25 = 2125
        pnl = position_payoff_at_expiry(legs, spot=22700)
        net_premium = 195 - 80  # 115 paid
        max_profit = (22600 - 22400 - net_premium) * 25
        assert pnl == max_profit

    def test_bull_call_spread_loss(self):
        """Bull call spread max loss below lower strike."""
        legs = [
            Leg(strike=22400, option_type="CE", action="BUY", premium=195, lots=1, lot_size=25),
            Leg(strike=22600, option_type="CE", action="SELL", premium=80, lots=1, lot_size=25),
        ]
        pnl = position_payoff_at_expiry(legs, spot=22200)
        assert pnl == -(195 - 80) * 25  # Net premium lost

    def test_short_straddle(self):
        """Short straddle: sell ATM call + sell ATM put."""
        legs = [
            Leg(strike=22500, option_type="CE", action="SELL", premium=130, lots=1, lot_size=25),
            Leg(strike=22500, option_type="PE", action="SELL", premium=100, lots=1, lot_size=25),
        ]
        # Max profit at the strike
        pnl_atm = position_payoff_at_expiry(legs, spot=22500)
        assert pnl_atm == (130 + 100) * 25  # Full premium kept

        # Loss on big move up
        pnl_up = position_payoff_at_expiry(legs, spot=23000)
        assert pnl_up < 0

    def test_iron_condor(self):
        """Iron condor: 4 legs, defined risk."""
        legs = [
            Leg(strike=22300, option_type="PE", action="SELL", premium=35, lots=1, lot_size=25),
            Leg(strike=22200, option_type="PE", action="BUY", premium=18, lots=1, lot_size=25),
            Leg(strike=22700, option_type="CE", action="SELL", premium=45, lots=1, lot_size=25),
            Leg(strike=22800, option_type="CE", action="BUY", premium=22, lots=1, lot_size=25),
        ]
        # Max profit between 22300-22700: net premium collected
        net_premium = (35 - 18 + 45 - 22)  # 40 per share
        pnl_mid = position_payoff_at_expiry(legs, spot=22500)
        assert pnl_mid == net_premium * 25

        # Max loss on break below put spread
        pnl_low = position_payoff_at_expiry(legs, spot=22100)
        width = 22300 - 22200  # 100
        max_loss = (width - net_premium) * 25
        assert pnl_low == -max_loss


class TestPayoffAnalysis:
    def test_long_call_analysis(self):
        """Analyze long call position."""
        legs = [
            Leg(strike=22500, option_type="CE", action="BUY", premium=130, lots=1, lot_size=25),
        ]
        analysis = analyze_payoff(legs, spot=22500)
        assert analysis.max_loss == -130 * 25  # Premium paid
        assert analysis.max_profit == float("inf")  # Unlimited
        assert len(analysis.breakevens) == 1
        assert abs(analysis.breakevens[0] - 22630) < 5  # Strike + premium
        assert analysis.net_premium == -130 * 25  # Paid premium

    def test_iron_condor_analysis(self):
        """Analyze iron condor."""
        legs = [
            Leg(strike=22300, option_type="PE", action="SELL", premium=35, lots=1, lot_size=25),
            Leg(strike=22200, option_type="PE", action="BUY", premium=18, lots=1, lot_size=25),
            Leg(strike=22700, option_type="CE", action="SELL", premium=45, lots=1, lot_size=25),
            Leg(strike=22800, option_type="CE", action="BUY", premium=22, lots=1, lot_size=25),
        ]
        analysis = analyze_payoff(legs, spot=22500)
        assert analysis.max_profit > 0
        assert analysis.max_loss < 0
        assert analysis.net_premium > 0  # Credit received
        assert len(analysis.breakevens) == 2  # Two breakeven points

    def test_payoff_curve_length(self):
        """Payoff curve should have correct number of points."""
        legs = [
            Leg(strike=22500, option_type="CE", action="BUY", premium=130, lots=1, lot_size=25),
        ]
        prices, payoffs = payoff_curve(legs, spot=22500, num_points=100)
        assert len(prices) == 100
        assert len(payoffs) == 100


class TestExpectedValue:
    def test_long_call_ev(self):
        """Expected value of a long call."""
        legs = [
            Leg(strike=22500, option_type="CE", action="BUY", premium=130, lots=1, lot_size=25),
        ]
        ev = expected_value(legs, spot=22500, T=7 / 365, r=0.065, sigma=0.13)
        assert "expected_pnl" in ev
        assert "prob_profit" in ev
        assert "var_95" in ev
        assert 0 <= ev["prob_profit"] <= 100

    def test_iron_condor_ev(self):
        """Iron condor should have positive expected P&L (premium selling)."""
        legs = [
            Leg(strike=22200, option_type="PE", action="SELL", premium=35, lots=1, lot_size=25),
            Leg(strike=22100, option_type="PE", action="BUY", premium=18, lots=1, lot_size=25),
            Leg(strike=22800, option_type="CE", action="SELL", premium=45, lots=1, lot_size=25),
            Leg(strike=22900, option_type="CE", action="BUY", premium=22, lots=1, lot_size=25),
        ]
        ev = expected_value(legs, spot=22500, T=7 / 365, r=0.065, sigma=0.13)
        # Wide IC on Nifty should have high prob profit
        assert ev["prob_profit"] > 50
