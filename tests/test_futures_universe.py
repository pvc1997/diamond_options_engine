"""Tests for futures margin estimation in universe.py."""

import pytest

from diamond_options.data.universe import (
    FUTURES_MARGIN_PCT,
    get_futures_margin_estimate,
    get_futures_margin_pct,
)


class TestFuturesMarginPct:
    def test_index_margin_lower(self):
        assert get_futures_margin_pct("NIFTY") == 0.10
        assert get_futures_margin_pct("BANKNIFTY") == 0.11

    def test_stock_margin(self):
        assert get_futures_margin_pct("RELIANCE") == 0.15
        assert get_futures_margin_pct("ADANIENT") == 0.25

    def test_case_insensitive(self):
        assert get_futures_margin_pct("nifty") == 0.10
        assert get_futures_margin_pct("Reliance") == 0.15

    def test_unknown_symbol_default(self):
        assert get_futures_margin_pct("UNKNOWNSYMBOL") == 0.20

    def test_all_margins_in_range(self):
        for symbol, pct in FUTURES_MARGIN_PCT.items():
            assert 0.05 <= pct <= 0.50, f"{symbol} margin {pct} out of range"


class TestFuturesMarginEstimate:
    def test_nifty_margin(self):
        # NIFTY at 22650, 1 lot of 65 → notional 1,472,250
        # 10% margin → ~147,225
        margin = get_futures_margin_estimate("NIFTY", 22650.0, 1)
        expected = 22650.0 * 65 * 0.10
        assert abs(margin - expected) < 0.01

    def test_reliance_margin(self):
        margin = get_futures_margin_estimate("RELIANCE", 2500.0, 1)
        expected = 2500.0 * 250 * 0.15
        assert abs(margin - expected) < 0.01

    def test_multiple_lots(self):
        margin = get_futures_margin_estimate("NIFTY", 22650.0, 3)
        expected = 22650.0 * 3 * 65 * 0.10
        assert abs(margin - expected) < 0.01

    def test_custom_lot_size(self):
        margin = get_futures_margin_estimate("NIFTY", 22650.0, 1, lot_size=50)
        expected = 22650.0 * 50 * 0.10
        assert abs(margin - expected) < 0.01

    def test_unknown_symbol_zero_lot(self):
        # Unknown symbol with no lot_size → 0
        margin = get_futures_margin_estimate("NOTFNO", 100.0, 1)
        assert margin == 0.0

    def test_negative_lots_uses_absolute(self):
        margin = get_futures_margin_estimate("NIFTY", 22650.0, -2)
        expected = 22650.0 * 2 * 65 * 0.10
        assert abs(margin - expected) < 0.01
