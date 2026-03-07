"""Tests for Black-Scholes pricing model.

Validates against known analytical values and boundary conditions.
Reference values verified against Hull (2018) examples and online BS calculators.
"""

import math

import pytest

from diamond_options.pricing.black_scholes import (
    call_price,
    put_price,
    price_option,
    put_call_parity_check,
)


class TestCallPrice:
    def test_atm_call(self):
        """ATM call with standard parameters."""
        result = call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
        # ATM 1-year call with 20% vol should be ~10.45
        assert 10.0 < result.price < 11.0

    def test_deep_itm_call(self):
        """Deep ITM call should be close to intrinsic."""
        result = call_price(S=150, K=100, T=0.1, r=0.05, sigma=0.20)
        assert result.price >= 49.0  # At least intrinsic ~50
        assert result.intrinsic == 50.0

    def test_deep_otm_call(self):
        """Deep OTM call should be near zero."""
        result = call_price(S=50, K=100, T=0.1, r=0.05, sigma=0.20)
        assert result.price < 0.01

    def test_zero_time(self):
        """At expiry, call is worth intrinsic value."""
        itm = call_price(S=110, K=100, T=0, r=0.05, sigma=0.20)
        assert itm.price == 10.0
        assert itm.time_value == 0

        otm = call_price(S=90, K=100, T=0, r=0.05, sigma=0.20)
        assert otm.price == 0.0

    def test_zero_vol(self):
        """Zero vol: PV of max(S*e^(-qT) - K*e^(-rT), 0)."""
        result = call_price(S=110, K=100, T=1.0, r=0.05, sigma=0)
        # S - K*e^(-rT) = 110 - 100*e^(-0.05) ≈ 14.88
        import math
        expected = 110 - 100 * math.exp(-0.05)
        assert abs(result.price - expected) < 0.01

    def test_high_vol(self):
        """High vol increases call value."""
        low_vol = call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.10)
        high_vol = call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.50)
        assert high_vol.price > low_vol.price

    def test_longer_time_higher_price(self):
        """More time = higher call value (all else equal)."""
        short = call_price(S=100, K=100, T=0.25, r=0.05, sigma=0.20)
        long = call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
        assert long.price > short.price

    def test_nifty_realistic(self):
        """Realistic Nifty option: Spot 22500, Strike 22500, 7 DTE."""
        result = call_price(S=22500, K=22500, T=7 / 365, r=0.065, sigma=0.13)
        # ATM weekly Nifty call should be ~100-200
        assert 50 < result.price < 300

    def test_time_value_positive(self):
        """Time value should always be non-negative for European calls."""
        result = call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
        assert result.time_value >= 0

    def test_price_non_negative(self):
        """Call price should never be negative."""
        result = call_price(S=50, K=100, T=0.01, r=0.05, sigma=0.50)
        assert result.price >= 0


class TestPutPrice:
    def test_atm_put(self):
        """ATM put with standard parameters."""
        result = put_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
        assert 5.0 < result.price < 7.0

    def test_deep_itm_put(self):
        """Deep ITM put should be close to intrinsic."""
        result = put_price(S=50, K=100, T=0.1, r=0.05, sigma=0.20)
        assert result.price >= 49.0
        assert result.intrinsic == 50.0

    def test_deep_otm_put(self):
        """Deep OTM put should be near zero."""
        result = put_price(S=150, K=100, T=0.1, r=0.05, sigma=0.20)
        assert result.price < 0.01

    def test_zero_time(self):
        """At expiry, put is worth intrinsic."""
        itm = put_price(S=90, K=100, T=0, r=0.05, sigma=0.20)
        assert itm.price == 10.0

        otm = put_price(S=110, K=100, T=0, r=0.05, sigma=0.20)
        assert otm.price == 0.0


class TestPutCallParity:
    def test_parity_holds(self):
        """Put-call parity should hold for BS prices."""
        c = call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
        p = put_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
        result = put_call_parity_check(c.price, p.price, S=100, K=100, T=1.0, r=0.05)
        assert result["parity_holds"] is True
        assert abs(result["deviation"]) < 0.01

    def test_parity_nifty(self):
        """Parity for Nifty-like parameters."""
        c = call_price(S=22500, K=22500, T=7 / 365, r=0.065, sigma=0.13)
        p = put_price(S=22500, K=22500, T=7 / 365, r=0.065, sigma=0.13)
        result = put_call_parity_check(
            c.price, p.price, S=22500, K=22500, T=7 / 365, r=0.065,
        )
        assert result["parity_holds"] is True


class TestPriceOption:
    def test_call_dispatch(self):
        """price_option with CE should match call_price."""
        direct = call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
        dispatched = price_option(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="CE")
        assert abs(direct.price - dispatched.price) < 0.001

    def test_put_dispatch(self):
        """price_option with PE should match put_price."""
        direct = put_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
        dispatched = price_option(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="PE")
        assert abs(direct.price - dispatched.price) < 0.001

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            price_option(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type="XX")

    def test_accepts_various_types(self):
        """Should accept CE, PE, call, put, C, P."""
        for ot in ["CE", "call", "C"]:
            result = price_option(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type=ot)
            assert result.price > 0
        for ot in ["PE", "put", "P"]:
            result = price_option(S=100, K=100, T=1.0, r=0.05, sigma=0.20, option_type=ot)
            assert result.price > 0


class TestDividendAdjustment:
    def test_dividend_reduces_call(self):
        """Dividend yield reduces call value."""
        no_div = call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20, q=0.0)
        with_div = call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20, q=0.03)
        assert with_div.price < no_div.price

    def test_dividend_increases_put(self):
        """Dividend yield increases put value."""
        no_div = put_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20, q=0.0)
        with_div = put_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20, q=0.03)
        assert with_div.price > no_div.price
