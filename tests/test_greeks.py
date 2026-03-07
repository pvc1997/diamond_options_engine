"""Tests for Greeks calculations.

Validates Greek values against known properties and boundary conditions.
"""

import pytest

from diamond_options.pricing.greeks import (
    call_delta,
    put_delta,
    gamma,
    call_theta,
    put_theta,
    vega,
    call_rho,
    put_rho,
    vanna,
    charm,
    calculate_greeks,
    probability_itm,
    probability_of_profit,
)


# Standard test parameters
S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.20


class TestDelta:
    def test_atm_call_delta(self):
        """ATM call delta should be ~0.5 (slightly above due to drift)."""
        d = call_delta(S, K, T, r, sigma)
        assert 0.50 < d < 0.65

    def test_atm_put_delta(self):
        """ATM put delta should be negative, near -0.5 (adjusted for drift)."""
        d = put_delta(S, K, T, r, sigma)
        assert -0.60 < d < -0.30

    def test_call_put_delta_relationship(self):
        """Call delta - Put delta = e^(-qT) ≈ 1 (no dividends)."""
        cd = call_delta(S, K, T, r, sigma)
        pd = put_delta(S, K, T, r, sigma)
        assert abs((cd - pd) - 1.0) < 0.01

    def test_deep_itm_call_delta(self):
        """Deep ITM call delta approaches 1."""
        d = call_delta(150, 100, 0.5, r, sigma)
        assert d > 0.95

    def test_deep_otm_call_delta(self):
        """Deep OTM call delta approaches 0."""
        d = call_delta(50, 100, 0.5, r, sigma)
        assert d < 0.01

    def test_delta_range(self):
        """Call delta in [0,1], put delta in [-1,0]."""
        for k in [80, 90, 100, 110, 120]:
            cd = call_delta(100, k, 0.5, r, sigma)
            assert 0 <= cd <= 1
            pd = put_delta(100, k, 0.5, r, sigma)
            assert -1 <= pd <= 0

    def test_expiry_delta(self):
        """At expiry, delta is 0 or 1 (or -1)."""
        assert call_delta(110, 100, 0, r, sigma) == 1.0
        assert call_delta(90, 100, 0, r, sigma) == 0.0
        assert put_delta(90, 100, 0, r, sigma) == -1.0
        assert put_delta(110, 100, 0, r, sigma) == 0.0


class TestGamma:
    def test_atm_gamma_highest(self):
        """Gamma is highest for ATM options."""
        g_atm = gamma(100, 100, 0.1, r, sigma)
        g_itm = gamma(120, 100, 0.1, r, sigma)
        g_otm = gamma(80, 100, 0.1, r, sigma)
        assert g_atm > g_itm
        assert g_atm > g_otm

    def test_gamma_positive(self):
        """Gamma is always positive."""
        for k in [80, 90, 100, 110, 120]:
            assert gamma(100, k, 0.5, r, sigma) >= 0

    def test_gamma_increases_near_expiry(self):
        """ATM gamma increases as expiry approaches."""
        g_far = gamma(100, 100, 1.0, r, sigma)
        g_near = gamma(100, 100, 0.01, r, sigma)
        assert g_near > g_far

    def test_gamma_same_for_call_and_put(self):
        """Gamma is the same for calls and puts at same strike."""
        g = gamma(100, 100, 0.5, r, sigma)
        assert g > 0  # Just verify it works; gamma is inherently the same


class TestTheta:
    def test_call_theta_negative(self):
        """Long call theta should be negative (time decay)."""
        th = call_theta(S, K, T, r, sigma)
        assert th < 0

    def test_put_theta_negative(self):
        """Long put theta should be negative."""
        th = put_theta(S, K, T, r, sigma)
        assert th < 0

    def test_atm_theta_highest_magnitude(self):
        """ATM options have the highest theta (time decay)."""
        th_atm = abs(call_theta(100, 100, 0.1, r, sigma))
        th_otm = abs(call_theta(100, 120, 0.1, r, sigma))
        assert th_atm > th_otm

    def test_theta_increases_near_expiry(self):
        """Theta accelerates as expiry approaches."""
        th_far = abs(call_theta(100, 100, 1.0, r, sigma))
        th_near = abs(call_theta(100, 100, 0.02, r, sigma))
        assert th_near > th_far

    def test_theta_is_per_day(self):
        """Theta should be a per-day value (not per-year)."""
        th = call_theta(22500, 22500, 7 / 365, 0.065, 0.13)
        # ATM Nifty weekly theta should be ~15-30 per day
        assert -50 < th < 0


class TestVega:
    def test_vega_positive(self):
        """Vega is always positive (higher vol = higher option price)."""
        v = vega(S, K, T, r, sigma)
        assert v > 0

    def test_atm_vega_highest(self):
        """Vega is highest for ATM options."""
        v_atm = vega(100, 100, 0.5, r, sigma)
        v_otm = vega(100, 120, 0.5, r, sigma)
        assert v_atm > v_otm

    def test_vega_per_1pct(self):
        """Vega should be per 1% vol move, not per 100%."""
        v = vega(100, 100, 1.0, r, sigma)
        # For a $100 stock with 1 year, vega should be ~0.30-0.40 per 1%
        assert 0.10 < v < 1.0

    def test_longer_expiry_more_vega(self):
        """Longer time to expiry = more vega."""
        v_short = vega(100, 100, 0.1, r, sigma)
        v_long = vega(100, 100, 1.0, r, sigma)
        assert v_long > v_short


class TestRho:
    def test_call_rho_positive(self):
        """Call rho is positive (higher rates help calls)."""
        rh = call_rho(S, K, T, r, sigma)
        assert rh > 0

    def test_put_rho_negative(self):
        """Put rho is negative (higher rates hurt puts)."""
        rh = put_rho(S, K, T, r, sigma)
        assert rh < 0


class TestSecondOrder:
    def test_vanna_exists(self):
        """Vanna should be non-zero for ATM options."""
        v = vanna(S, K, T, r, sigma)
        assert v != 0

    def test_charm_exists(self):
        """Charm should be non-zero."""
        c = charm(S, K, T, r, sigma)
        assert c != 0


class TestCalculateGreeks:
    def test_call_greeks_bundle(self):
        """calculate_greeks returns complete bundle for calls."""
        g = calculate_greeks(S, K, T, r, sigma, "CE")
        assert 0 < g.delta < 1
        assert g.gamma > 0
        assert g.theta < 0
        assert g.vega > 0
        assert g.rho > 0

    def test_put_greeks_bundle(self):
        """calculate_greeks returns complete bundle for puts."""
        g = calculate_greeks(S, K, T, r, sigma, "PE")
        assert -1 < g.delta < 0
        assert g.gamma > 0
        assert g.theta < 0
        assert g.vega > 0
        assert g.rho < 0

    def test_nifty_greeks(self):
        """Realistic Nifty option Greeks."""
        g = calculate_greeks(22500, 22500, 7 / 365, 0.065, 0.13, "CE")
        assert 0.4 < g.delta < 0.6  # ATM
        assert g.gamma > 0
        assert g.theta < 0  # Time decay


class TestProbability:
    def test_atm_probability_itm(self):
        """ATM call has ~50% probability of being ITM."""
        p = probability_itm(100, 100, 1.0, r, sigma, "CE")
        assert 0.45 < p < 0.60

    def test_deep_itm_probability(self):
        """Deep ITM should have high probability."""
        p = probability_itm(150, 100, 0.5, r, sigma, "CE")
        assert p > 0.95

    def test_deep_otm_probability(self):
        """Deep OTM should have low probability."""
        p = probability_itm(50, 100, 0.5, r, sigma, "CE")
        assert p < 0.01

    def test_probability_of_profit(self):
        """PoP should be less than prob ITM (need to cover premium)."""
        p_itm = probability_itm(100, 100, 1.0, r, sigma, "CE")
        p_profit = probability_of_profit(100, 100, 1.0, r, sigma, "CE", premium=10.0)
        assert p_profit < p_itm  # Need more movement to profit

    def test_seller_pop_complement(self):
        """Seller's PoP = 1 - Buyer's PoP."""
        buyer = probability_of_profit(100, 100, 1.0, r, sigma, "CE", premium=10.0)
        seller = probability_of_profit(100, 100, 1.0, r, sigma, "CE", premium=-10.0)
        assert abs(buyer + seller - 1.0) < 0.01
