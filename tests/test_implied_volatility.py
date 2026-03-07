"""Tests for Implied Volatility solver."""

import pytest

from diamond_options.pricing.black_scholes import call_price, put_price
from diamond_options.pricing.implied_volatility import (
    implied_volatility,
    implied_volatility_safe,
)


class TestIVSolver:
    def test_roundtrip_call(self):
        """IV solver should recover the original sigma from a BS price."""
        sigma = 0.25
        bs = call_price(S=100, K=100, T=1.0, r=0.05, sigma=sigma)
        recovered = implied_volatility(
            bs.price, S=100, K=100, T=1.0, r=0.05, option_type="CE",
        )
        assert recovered is not None
        assert abs(recovered - sigma) < 0.001

    def test_roundtrip_put(self):
        """IV solver for puts."""
        sigma = 0.30
        bs = put_price(S=100, K=100, T=1.0, r=0.05, sigma=sigma)
        recovered = implied_volatility(
            bs.price, S=100, K=100, T=1.0, r=0.05, option_type="PE",
        )
        assert recovered is not None
        assert abs(recovered - sigma) < 0.001

    def test_atm_convergence(self):
        """ATM options should converge quickly."""
        for sigma in [0.10, 0.20, 0.30, 0.40, 0.50]:
            bs = call_price(S=100, K=100, T=0.5, r=0.05, sigma=sigma)
            recovered = implied_volatility(
                bs.price, S=100, K=100, T=0.5, r=0.05, option_type="CE",
            )
            assert recovered is not None
            assert abs(recovered - sigma) < 0.001

    def test_otm_call(self):
        """OTM call IV recovery."""
        sigma = 0.25
        bs = call_price(S=100, K=120, T=0.5, r=0.05, sigma=sigma)
        recovered = implied_volatility(
            bs.price, S=100, K=120, T=0.5, r=0.05, option_type="CE",
        )
        assert recovered is not None
        assert abs(recovered - sigma) < 0.01

    def test_itm_put(self):
        """ITM put IV recovery."""
        sigma = 0.20
        bs = put_price(S=80, K=100, T=0.5, r=0.05, sigma=sigma)
        recovered = implied_volatility(
            bs.price, S=80, K=100, T=0.5, r=0.05, option_type="PE",
        )
        assert recovered is not None
        assert abs(recovered - sigma) < 0.01

    def test_nifty_realistic(self):
        """Realistic Nifty option IV."""
        sigma = 0.13
        bs = call_price(S=22500, K=22500, T=7 / 365, r=0.065, sigma=sigma)
        recovered = implied_volatility(
            bs.price, S=22500, K=22500, T=7 / 365, r=0.065, option_type="CE",
        )
        assert recovered is not None
        assert abs(recovered - sigma) < 0.001

    def test_short_expiry(self):
        """Very short expiry (1 day)."""
        sigma = 0.15
        bs = call_price(S=22500, K=22500, T=1 / 365, r=0.065, sigma=sigma)
        recovered = implied_volatility(
            bs.price, S=22500, K=22500, T=1 / 365, r=0.065, option_type="CE",
        )
        assert recovered is not None
        assert abs(recovered - sigma) < 0.01

    def test_high_vol(self):
        """High volatility recovery."""
        sigma = 0.80
        bs = call_price(S=100, K=100, T=0.5, r=0.05, sigma=sigma)
        recovered = implied_volatility(
            bs.price, S=100, K=100, T=0.5, r=0.05, option_type="CE",
        )
        assert recovered is not None
        assert abs(recovered - sigma) < 0.01

    def test_zero_price_returns_none(self):
        """Zero market price should return None."""
        assert implied_volatility(0, S=100, K=100, T=1.0, r=0.05, option_type="CE") is None

    def test_negative_price_returns_none(self):
        """Negative price should return None."""
        assert implied_volatility(-5, S=100, K=100, T=1.0, r=0.05, option_type="CE") is None

    def test_zero_time_returns_none(self):
        """Zero time should return None."""
        assert implied_volatility(5, S=100, K=100, T=0, r=0.05, option_type="CE") is None


class TestIVSafe:
    def test_returns_float(self):
        """Safe version always returns a float."""
        bs = call_price(S=100, K=100, T=1.0, r=0.05, sigma=0.20)
        result = implied_volatility_safe(
            bs.price, S=100, K=100, T=1.0, r=0.05, option_type="CE",
        )
        assert isinstance(result, float)
        assert result > 0

    def test_returns_zero_on_failure(self):
        """Safe version returns 0.0 on failure."""
        result = implied_volatility_safe(
            0, S=100, K=100, T=1.0, r=0.05, option_type="CE",
        )
        assert result == 0.0
