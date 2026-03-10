"""Tests for futures pricing via cost-of-carry model."""

import math

import pytest

from diamond_options.pricing.futures_pricing import (
    FuturesPricingResult,
    calendar_spread_fair_value,
    contango_or_backwardation,
    fair_value,
    futures_mispricing,
    implied_dividend_yield,
    implied_interest_rate,
    theoretical_futures_price,
)


class TestTheoreticalFuturesPrice:
    def test_basic_pricing(self):
        # Spot 22500, 6.5% rate, 30 days
        T = 30 / 365
        fv = theoretical_futures_price(22500.0, 0.065, T)
        expected = 22500.0 * math.exp(0.065 * T)
        assert abs(fv - expected) < 0.01

    def test_with_dividend_yield(self):
        # Net carry = r - q
        T = 60 / 365
        fv = theoretical_futures_price(22500.0, 0.065, T, q=0.012)
        expected = 22500.0 * math.exp((0.065 - 0.012) * T)
        assert abs(fv - expected) < 0.01

    def test_zero_time(self):
        # At expiry, futures = spot
        fv = theoretical_futures_price(22500.0, 0.065, 0.0)
        assert fv == 22500.0

    def test_zero_spot(self):
        fv = theoretical_futures_price(0.0, 0.065, 30 / 365)
        assert fv == 0.0

    def test_contango_with_positive_rate(self):
        T = 30 / 365
        fv = theoretical_futures_price(22500.0, 0.065, T)
        assert fv > 22500.0  # Futures above spot in contango

    def test_backwardation_with_high_dividend(self):
        T = 30 / 365
        fv = theoretical_futures_price(22500.0, 0.02, T, q=0.10)
        assert fv < 22500.0  # High dividend → backwardation

    def test_fair_value_alias(self):
        T = 30 / 365
        fv1 = theoretical_futures_price(22500.0, 0.065, T)
        fv2 = fair_value(22500.0, 0.065, T)
        assert fv1 == fv2


class TestFuturesMispricing:
    def test_fairly_priced(self):
        T = 30 / 365
        fv = theoretical_futures_price(22500.0, 0.065, T)
        result = futures_mispricing(22500.0, fv, 0.065, T)
        assert abs(result.mispricing) < 0.1
        assert not result.is_overpriced
        assert not result.is_underpriced

    def test_overpriced(self):
        T = 30 / 365
        fv = theoretical_futures_price(22500.0, 0.065, T)
        result = futures_mispricing(22500.0, fv + 100, 0.065, T)
        assert result.mispricing > 0
        assert result.is_overpriced
        assert not result.is_underpriced

    def test_underpriced(self):
        T = 30 / 365
        fv = theoretical_futures_price(22500.0, 0.065, T)
        result = futures_mispricing(22500.0, fv - 100, 0.065, T)
        assert result.mispricing < 0
        assert result.is_underpriced
        assert not result.is_overpriced

    def test_result_fields(self):
        T = 30 / 365
        result = futures_mispricing(22500.0, 22620.0, 0.065, T)
        assert isinstance(result, FuturesPricingResult)
        assert result.market_price == 22620.0
        assert result.fair_value > 0
        assert result.carry_cost > 0
        assert result.implied_rate > 0

    def test_carry_cost(self):
        T = 30 / 365
        result = futures_mispricing(22500.0, 22620.0, 0.065, T)
        # carry_cost = fair_value - spot
        expected_carry = result.fair_value - 22500.0
        assert abs(result.carry_cost - expected_carry) < 0.01

    def test_custom_threshold(self):
        T = 30 / 365
        fv = theoretical_futures_price(22500.0, 0.065, T)
        # With strict threshold, small mispricing triggers signal
        result = futures_mispricing(22500.0, fv + 30, 0.065, T, threshold_pct=0.01)
        assert result.is_overpriced


class TestImpliedInterestRate:
    def test_roundtrip(self):
        # If we price at 6.5%, implied rate should be ~6.5%
        T = 30 / 365
        fv = theoretical_futures_price(22500.0, 0.065, T)
        rate = implied_interest_rate(22500.0, fv, T)
        assert abs(rate - 0.065) < 0.001

    def test_with_dividend(self):
        T = 60 / 365
        q = 0.012
        fv = theoretical_futures_price(22500.0, 0.065, T, q)
        rate = implied_interest_rate(22500.0, fv, T, q)
        assert abs(rate - 0.065) < 0.001

    def test_zero_time(self):
        assert implied_interest_rate(22500.0, 22600.0, 0.0) == 0.0

    def test_zero_prices(self):
        assert implied_interest_rate(0.0, 22600.0, 30 / 365) == 0.0
        assert implied_interest_rate(22500.0, 0.0, 30 / 365) == 0.0

    def test_higher_futures_implies_higher_rate(self):
        T = 30 / 365
        rate1 = implied_interest_rate(22500.0, 22600.0, T)
        rate2 = implied_interest_rate(22500.0, 22700.0, T)
        assert rate2 > rate1


class TestImpliedDividendYield:
    def test_roundtrip(self):
        T = 60 / 365
        r = 0.065
        q = 0.015
        fv = theoretical_futures_price(22500.0, r, T, q)
        q_implied = implied_dividend_yield(22500.0, fv, r, T)
        assert abs(q_implied - q) < 0.001

    def test_zero_dividend_when_futures_at_carry(self):
        T = 30 / 365
        r = 0.065
        fv = theoretical_futures_price(22500.0, r, T, q=0.0)
        q_implied = implied_dividend_yield(22500.0, fv, r, T)
        assert abs(q_implied) < 0.001

    def test_zero_time(self):
        assert implied_dividend_yield(22500.0, 22600.0, 0.065, 0.0) == 0.0


class TestContangoOrBackwardation:
    def test_contango(self):
        assert contango_or_backwardation(22600, 22700) == "contango"

    def test_backwardation(self):
        assert contango_or_backwardation(22700, 22600) == "backwardation"

    def test_flat(self):
        assert contango_or_backwardation(22600, 22600) == "flat"


class TestCalendarSpreadFairValue:
    def test_contango_spread(self):
        # Near 20 days, far 50 days
        result = calendar_spread_fair_value(22500.0, 0.065, 20 / 365, 50 / 365)
        assert result["spread"] > 0  # Far > near in contango
        assert result["structure"] == "contango"

    def test_near_far_values(self):
        T_near = 20 / 365
        T_far = 50 / 365
        result = calendar_spread_fair_value(22500.0, 0.065, T_near, T_far)
        assert result["near_fair_value"] == round(
            theoretical_futures_price(22500.0, 0.065, T_near), 2
        )
        assert result["far_fair_value"] == round(
            theoretical_futures_price(22500.0, 0.065, T_far), 2
        )

    def test_spread_pct(self):
        result = calendar_spread_fair_value(22500.0, 0.065, 20 / 365, 50 / 365)
        expected_pct = result["spread"] / 22500.0 * 100
        assert abs(result["spread_pct"] - round(expected_pct, 4)) < 0.001

    def test_with_dividend(self):
        result_no_div = calendar_spread_fair_value(22500.0, 0.065, 20 / 365, 50 / 365)
        result_div = calendar_spread_fair_value(
            22500.0, 0.065, 20 / 365, 50 / 365, q=0.02
        )
        # Higher dividend reduces carry → narrower spread
        assert result_div["spread"] < result_no_div["spread"]
