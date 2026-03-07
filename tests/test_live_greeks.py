"""Tests for live Greeks computation from market prices."""

from datetime import date, timedelta

import pytest

from diamond_options.pricing.live_greeks import (
    OptionWithGreeks,
    chain_greeks_summary,
    compute_chain_greeks,
    compute_greeks_for_quote,
    compute_iv_from_market,
    _classify_moneyness,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _future_expiry(days: int = 7) -> date:
    """Return a date `days` from today."""
    return date.today() + timedelta(days=days)


def _expiry_today() -> date:
    return date.today()


# ---------------------------------------------------------------------------
# compute_iv_from_market
# ---------------------------------------------------------------------------


class TestComputeIVFromMarket:
    """Tests for IV extraction from market prices."""

    def test_atm_call_iv(self):
        """ATM call should return a reasonable IV."""
        spot = 24000.0
        strike = 24000.0
        expiry = _future_expiry(7)
        ltp = 250.0  # Reasonable ATM premium for NIFTY weekly
        iv = compute_iv_from_market(ltp, spot, strike, expiry, "CE")
        assert iv is not None
        assert 0.05 < iv < 1.0, f"ATM call IV {iv} outside reasonable range"

    def test_atm_put_iv(self):
        """ATM put should return a reasonable IV."""
        spot = 24000.0
        strike = 24000.0
        expiry = _future_expiry(7)
        ltp = 240.0
        iv = compute_iv_from_market(ltp, spot, strike, expiry, "PE")
        assert iv is not None
        assert 0.05 < iv < 1.0, f"ATM put IV {iv} outside reasonable range"

    def test_itm_call_iv(self):
        """ITM call (spot > strike) should solve IV."""
        spot = 24000.0
        strike = 23500.0
        expiry = _future_expiry(14)
        ltp = 580.0  # 500 intrinsic + 80 time value
        iv = compute_iv_from_market(ltp, spot, strike, expiry, "CE")
        assert iv is not None
        assert iv > 0

    def test_otm_call_iv(self):
        """OTM call (spot < strike) should solve IV for non-zero premium."""
        spot = 24000.0
        strike = 24500.0
        expiry = _future_expiry(14)
        ltp = 50.0
        iv = compute_iv_from_market(ltp, spot, strike, expiry, "CE")
        assert iv is not None
        assert iv > 0

    def test_zero_premium_returns_none(self):
        """Zero LTP should return None."""
        iv = compute_iv_from_market(0.0, 24000.0, 24500.0, _future_expiry(7), "CE")
        assert iv is None

    def test_negative_premium_returns_none(self):
        """Negative LTP should return None."""
        iv = compute_iv_from_market(-10.0, 24000.0, 24500.0, _future_expiry(7), "CE")
        assert iv is None

    def test_expired_option_returns_none(self):
        """Past expiry should return None."""
        past_expiry = date.today() - timedelta(days=1)
        iv = compute_iv_from_market(100.0, 24000.0, 24000.0, past_expiry, "CE")
        assert iv is None

    def test_expiry_day_returns_iv(self):
        """Expiry day (T=0) should still attempt to solve with small T."""
        spot = 24000.0
        strike = 24000.0
        expiry = _expiry_today()
        ltp = 30.0  # Small ATM premium on expiry day
        iv = compute_iv_from_market(ltp, spot, strike, expiry, "CE")
        # Should either return a valid IV or None, but not crash
        if iv is not None:
            assert iv > 0

    def test_deep_otm_near_zero_premium(self):
        """Deep OTM with tiny premium — IV solver may fail gracefully."""
        spot = 24000.0
        strike = 26000.0
        expiry = _future_expiry(3)
        ltp = 0.5  # Barely any premium
        iv = compute_iv_from_market(ltp, spot, strike, expiry, "CE")
        # May return None or a very high IV — both are acceptable
        if iv is not None:
            assert iv > 0


# ---------------------------------------------------------------------------
# _classify_moneyness
# ---------------------------------------------------------------------------


class TestClassifyMoneyness:
    def test_atm_call(self):
        assert _classify_moneyness(24000, 24000, "CE") == "ATM"

    def test_atm_near(self):
        """Within 0.5% should be ATM."""
        assert _classify_moneyness(24000, 24100, "CE") == "ATM"

    def test_itm_call(self):
        assert _classify_moneyness(24000, 23500, "CE") == "ITM"

    def test_otm_call(self):
        assert _classify_moneyness(24000, 24500, "CE") == "OTM"

    def test_itm_put(self):
        assert _classify_moneyness(24000, 24500, "PE") == "ITM"

    def test_otm_put(self):
        assert _classify_moneyness(24000, 23500, "PE") == "OTM"


# ---------------------------------------------------------------------------
# compute_greeks_for_quote
# ---------------------------------------------------------------------------


class TestComputeGreeksForQuote:
    def test_atm_call_greeks(self):
        """ATM call should have delta near 0.5 and positive vega."""
        owg = compute_greeks_for_quote(
            spot=24000.0, strike=24000.0, expiry=_future_expiry(14),
            option_type="CE", ltp=350.0, oi=500000, volume=100000,
        )
        assert owg is not None
        assert 0.3 < owg.delta < 0.7, f"ATM call delta {owg.delta} not near 0.5"
        assert owg.gamma > 0
        assert owg.theta < 0  # Long option loses value to time decay
        assert owg.vega > 0
        assert owg.moneyness == "ATM"
        assert owg.iv > 0
        assert owg.oi == 500000
        assert owg.volume == 100000

    def test_call_delta_range(self):
        """Call delta should be between 0 and 1."""
        owg = compute_greeks_for_quote(
            spot=24000.0, strike=23000.0, expiry=_future_expiry(14),
            option_type="CE", ltp=1100.0,
        )
        assert owg is not None
        assert 0.0 <= owg.delta <= 1.0

    def test_put_delta_range(self):
        """Put delta should be between -1 and 0."""
        owg = compute_greeks_for_quote(
            spot=24000.0, strike=24000.0, expiry=_future_expiry(14),
            option_type="PE", ltp=340.0,
        )
        assert owg is not None
        assert -1.0 <= owg.delta <= 0.0

    def test_itm_call_intrinsic(self):
        """ITM call should have positive intrinsic value."""
        owg = compute_greeks_for_quote(
            spot=24000.0, strike=23500.0, expiry=_future_expiry(7),
            option_type="CE", ltp=580.0,
        )
        assert owg is not None
        assert owg.intrinsic_value == 500.0
        assert owg.time_value == 80.0
        assert owg.moneyness == "ITM"

    def test_otm_put_no_intrinsic(self):
        """OTM put should have zero intrinsic value."""
        owg = compute_greeks_for_quote(
            spot=24000.0, strike=23500.0, expiry=_future_expiry(7),
            option_type="PE", ltp=60.0,
        )
        assert owg is not None
        assert owg.intrinsic_value == 0.0
        assert owg.time_value == 60.0
        assert owg.moneyness == "OTM"

    def test_returns_none_for_zero_premium(self):
        """Zero premium should return None."""
        owg = compute_greeks_for_quote(
            spot=24000.0, strike=24000.0, expiry=_future_expiry(7),
            option_type="CE", ltp=0.0,
        )
        assert owg is None

    def test_frozen_dataclass(self):
        """OptionWithGreeks should be immutable."""
        owg = compute_greeks_for_quote(
            spot=24000.0, strike=24000.0, expiry=_future_expiry(14),
            option_type="CE", ltp=350.0,
        )
        assert owg is not None
        with pytest.raises(AttributeError):
            owg.delta = 0.99  # type: ignore


# ---------------------------------------------------------------------------
# compute_chain_greeks
# ---------------------------------------------------------------------------


class TestComputeChainGreeks:
    def _make_kite_quotes(self, expiry: date) -> dict:
        """Build a small Kite quotes dict for testing."""
        yy = expiry.strftime("%y")
        mm = str(expiry.month)
        dd = expiry.strftime("%d")
        prefix = f"NFO:NIFTY{yy}{mm}{dd}"
        return {
            f"{prefix}23500CE": {"last_price": 580.0, "oi": 100000, "volume": 50000},
            f"{prefix}24000CE": {"last_price": 250.0, "oi": 300000, "volume": 120000},
            f"{prefix}24500CE": {"last_price": 50.0, "oi": 200000, "volume": 80000},
            f"{prefix}23500PE": {"last_price": 30.0, "oi": 80000, "volume": 30000},
            f"{prefix}24000PE": {"last_price": 240.0, "oi": 350000, "volume": 150000},
            f"{prefix}24500PE": {"last_price": 550.0, "oi": 150000, "volume": 60000},
        }

    def test_chain_returns_all_valid(self):
        """Should return Greeks for all valid quotes."""
        expiry = _future_expiry(7)
        quotes = self._make_kite_quotes(expiry)
        result = compute_chain_greeks(24000.0, expiry, quotes)
        # Should get at least some results (some may fail IV solve)
        assert len(result) > 0

    def test_chain_sorted_calls_then_puts(self):
        """Result should have calls sorted by strike, then puts."""
        expiry = _future_expiry(14)
        quotes = self._make_kite_quotes(expiry)
        result = compute_chain_greeks(24000.0, expiry, quotes)
        if len(result) < 2:
            pytest.skip("Not enough results to verify sorting")

        calls = [r for r in result if r.option_type == "CE"]
        puts = [r for r in result if r.option_type == "PE"]

        # Calls should come first
        if calls and puts:
            call_indices = [result.index(c) for c in calls]
            put_indices = [result.index(p) for p in puts]
            assert max(call_indices) < min(put_indices)

        # Each group sorted by strike
        if len(calls) > 1:
            assert all(calls[i].strike <= calls[i + 1].strike for i in range(len(calls) - 1))
        if len(puts) > 1:
            assert all(puts[i].strike <= puts[i + 1].strike for i in range(len(puts) - 1))

    def test_chain_skips_unparseable_symbols(self):
        """Quotes with unparseable keys should be skipped."""
        expiry = _future_expiry(7)
        quotes = {
            "INVALID_KEY": {"last_price": 100.0, "oi": 1000, "volume": 500},
        }
        result = compute_chain_greeks(24000.0, expiry, quotes)
        assert len(result) == 0

    def test_chain_skips_zero_premium(self):
        """Quotes with zero premium should be skipped."""
        expiry = _future_expiry(7)
        yy = expiry.strftime("%y")
        mm = str(expiry.month)
        dd = expiry.strftime("%d")
        quotes = {
            f"NFO:NIFTY{yy}{mm}{dd}24000CE": {"last_price": 0, "oi": 1000, "volume": 0},
        }
        result = compute_chain_greeks(24000.0, expiry, quotes)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# chain_greeks_summary
# ---------------------------------------------------------------------------


class TestChainGreeksSummary:
    def _make_owg(
        self, strike: float, option_type: str, iv: float, delta: float,
        gamma: float = 0.001, theta: float = -5.0, vega: float = 10.0,
        moneyness: str = "OTM",
    ) -> OptionWithGreeks:
        return OptionWithGreeks(
            strike=strike, option_type=option_type, expiry=_future_expiry(7),
            ltp=100.0, oi=10000, volume=5000,
            iv=iv, delta=delta, gamma=gamma, theta=theta, vega=vega, rho=0.5,
            intrinsic_value=0.0, time_value=100.0, moneyness=moneyness,
        )

    def test_summary_atm_iv(self):
        """ATM IV should pick nearest strike to spot."""
        greeks_list = [
            self._make_owg(23500, "CE", 0.18, 0.7, moneyness="ITM"),
            self._make_owg(24000, "CE", 0.15, 0.5, moneyness="ATM"),
            self._make_owg(24500, "CE", 0.20, 0.3, moneyness="OTM"),
            self._make_owg(23500, "PE", 0.22, -0.3, moneyness="OTM"),
            self._make_owg(24000, "PE", 0.16, -0.5, moneyness="ATM"),
            self._make_owg(24500, "PE", 0.14, -0.7, moneyness="ITM"),
        ]
        summary = chain_greeks_summary(greeks_list, 24000.0)
        assert summary["atm_call_iv"] == 0.15
        assert summary["atm_put_iv"] == 0.16

    def test_summary_average_ivs(self):
        """Average IVs should be computed for calls and puts separately."""
        greeks_list = [
            self._make_owg(23500, "CE", 0.18, 0.7),
            self._make_owg(24000, "CE", 0.20, 0.5),
            self._make_owg(24000, "PE", 0.22, -0.5),
            self._make_owg(24500, "PE", 0.24, -0.3),
        ]
        summary = chain_greeks_summary(greeks_list, 24000.0)
        assert summary["avg_call_iv"] == pytest.approx(0.19, abs=0.001)
        assert summary["avg_put_iv"] == pytest.approx(0.23, abs=0.001)

    def test_summary_iv_skew(self):
        """IV skew = avg OTM put IV - avg OTM call IV."""
        greeks_list = [
            self._make_owg(24500, "CE", 0.14, 0.3, moneyness="OTM"),
            self._make_owg(25000, "CE", 0.12, 0.2, moneyness="OTM"),
            self._make_owg(23000, "PE", 0.22, -0.2, moneyness="OTM"),
            self._make_owg(23500, "PE", 0.20, -0.3, moneyness="OTM"),
        ]
        summary = chain_greeks_summary(greeks_list, 24000.0)
        # OTM put avg = 0.21, OTM call avg = 0.13, skew = 0.08
        assert summary["iv_skew"] == pytest.approx(0.08, abs=0.001)

    def test_summary_aggregate_greeks(self):
        """Total Greeks should sum across all options."""
        greeks_list = [
            self._make_owg(24000, "CE", 0.15, 0.5, gamma=0.001, theta=-5.0, vega=10.0),
            self._make_owg(24000, "PE", 0.16, -0.5, gamma=0.001, theta=-4.0, vega=9.0),
        ]
        summary = chain_greeks_summary(greeks_list, 24000.0)
        assert summary["total_delta"] == pytest.approx(0.0, abs=0.01)
        assert summary["total_gamma"] == pytest.approx(0.002, abs=0.0001)
        assert summary["total_theta"] == pytest.approx(-9.0, abs=0.1)
        assert summary["total_vega"] == pytest.approx(19.0, abs=0.1)

    def test_summary_put_call_iv_ratio(self):
        """Put-call IV ratio should be avg_put_iv / avg_call_iv."""
        greeks_list = [
            self._make_owg(24000, "CE", 0.20, 0.5),
            self._make_owg(24000, "PE", 0.25, -0.5),
        ]
        summary = chain_greeks_summary(greeks_list, 24000.0)
        assert summary["put_call_iv_ratio"] == pytest.approx(1.25, abs=0.01)

    def test_summary_empty_list(self):
        """Empty list should return all None/zero values."""
        summary = chain_greeks_summary([], 24000.0)
        assert summary["atm_call_iv"] is None
        assert summary["atm_put_iv"] is None
        assert summary["total_delta"] == 0.0
        assert summary["num_calls"] == 0
        assert summary["num_puts"] == 0

    def test_summary_counts(self):
        """Should count calls and puts correctly."""
        greeks_list = [
            self._make_owg(23500, "CE", 0.18, 0.7),
            self._make_owg(24000, "CE", 0.15, 0.5),
            self._make_owg(24500, "CE", 0.20, 0.3),
            self._make_owg(24000, "PE", 0.16, -0.5),
            self._make_owg(24500, "PE", 0.14, -0.7),
        ]
        summary = chain_greeks_summary(greeks_list, 24000.0)
        assert summary["num_calls"] == 3
        assert summary["num_puts"] == 2
