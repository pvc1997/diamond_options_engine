"""Tests for futures symbol parsing and chain building in kite_bridge."""

from datetime import date

import pytest

from diamond_options.data.kite_bridge import (
    build_futures_chain_from_kite,
    kite_quote_to_futures_quote,
    parse_futures_symbol,
)


class TestParseFuturesSymbol:
    def test_nifty_monthly(self):
        result = parse_futures_symbol("NIFTY26MARFUT")
        assert result is not None
        assert result["symbol"] == "NIFTY"
        assert result["year"] == 2026
        assert result["month"] == 3
        assert result["instrument"] == "FUT"

    def test_banknifty_monthly(self):
        result = parse_futures_symbol("BANKNIFTY26APRFUT")
        assert result is not None
        assert result["symbol"] == "BANKNIFTY"
        assert result["year"] == 2026
        assert result["month"] == 4

    def test_stock_futures(self):
        result = parse_futures_symbol("RELIANCE26MARFUT")
        assert result is not None
        assert result["symbol"] == "RELIANCE"

    def test_m_and_m_special_char(self):
        result = parse_futures_symbol("M&M26MARFUT")
        assert result is not None
        assert result["symbol"] == "M&M"

    def test_all_months(self):
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                   "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        for i, m in enumerate(months, 1):
            result = parse_futures_symbol(f"NIFTY26{m}FUT")
            assert result is not None
            assert result["month"] == i

    def test_rejects_options(self):
        assert parse_futures_symbol("NIFTY2631024500CE") is None
        assert parse_futures_symbol("NIFTY26MAR24500PE") is None

    def test_rejects_invalid(self):
        assert parse_futures_symbol("") is None
        assert parse_futures_symbol("NIFTY") is None
        assert parse_futures_symbol("NIFTY26XYZ") is None

    def test_rejects_invalid_month(self):
        assert parse_futures_symbol("NIFTY26XXXFUT") is None


class TestKiteQuoteToFuturesQuote:
    def test_basic_conversion(self):
        kite_quote = {
            "last_price": 22650.0,
            "oi": 12000000,
            "oi_day_change": 500000,
            "volume": 800000,
            "ohlc": {"open": 22600, "high": 22700, "low": 22550, "close": 22580},
        }
        result = kite_quote_to_futures_quote(
            "NFO:NIFTY26MARFUT",
            kite_quote,
            date(2026, 3, 31),
            spot_price=22500.0,
            lot_size=65,
        )
        assert result is not None
        assert result.symbol == "NIFTY"
        assert result.last_price == 22650.0
        assert result.spot_price == 22500.0
        assert result.open_interest == 12000000
        assert result.oi_change == 500000
        assert result.volume == 800000
        assert result.lot_size == 65
        assert result.prev_close == 22580
        assert abs(result.change - 70.0) < 0.01

    def test_rejects_options_key(self):
        kite_quote = {"last_price": 130.0}
        result = kite_quote_to_futures_quote(
            "NFO:NIFTY2631024500CE",
            kite_quote,
            date(2026, 3, 31),
            spot_price=22500.0,
        )
        assert result is None

    def test_strips_exchange_prefix(self):
        kite_quote = {"last_price": 22650.0, "ohlc": {}}
        result = kite_quote_to_futures_quote(
            "NFO:RELIANCE26MARFUT",
            kite_quote,
            date(2026, 3, 31),
            spot_price=2500.0,
        )
        assert result is not None
        assert result.symbol == "RELIANCE"

    def test_handles_missing_ohlc(self):
        kite_quote = {"last_price": 22650.0}
        result = kite_quote_to_futures_quote(
            "NFO:NIFTY26MARFUT",
            kite_quote,
            date(2026, 3, 31),
            spot_price=22500.0,
        )
        assert result is not None
        assert result.change == 0.0

    def test_handles_depth_data(self):
        kite_quote = {
            "last_price": 22650.0,
            "ohlc": {},
            "depth": {
                "buy": [{"price": 22648.0, "quantity": 100}],
                "sell": [{"price": 22652.0, "quantity": 100}],
            },
        }
        result = kite_quote_to_futures_quote(
            "NFO:NIFTY26MARFUT",
            kite_quote,
            date(2026, 3, 31),
            spot_price=22500.0,
        )
        assert result is not None
        assert result.bid == 22648.0
        assert result.ask == 22652.0


class TestBuildFuturesChainFromKite:
    def test_builds_chain_with_two_months(self):
        kite_quotes = {
            "NFO:NIFTY26MARFUT": {
                "last_price": 22650.0,
                "oi": 12000000,
                "volume": 800000,
                "ohlc": {},
            },
            "NFO:NIFTY26APRFUT": {
                "last_price": 22750.0,
                "oi": 4000000,
                "volume": 200000,
                "ohlc": {},
            },
        }
        expiry_map = {
            "NFO:NIFTY26MARFUT": date(2026, 3, 31),
            "NFO:NIFTY26APRFUT": date(2026, 4, 28),
        }

        chain = build_futures_chain_from_kite(
            "NIFTY", 22500.0, kite_quotes, expiry_map, lot_size=65,
        )
        assert chain is not None
        assert chain.symbol == "NIFTY"
        assert chain.near_month.last_price == 22650.0
        assert chain.next_month is not None
        assert chain.next_month.last_price == 22750.0
        assert chain.far_month is None

    def test_builds_chain_with_three_months(self):
        kite_quotes = {
            "NFO:NIFTY26MARFUT": {"last_price": 22650.0, "ohlc": {}},
            "NFO:NIFTY26APRFUT": {"last_price": 22750.0, "ohlc": {}},
            "NFO:NIFTY26MAYFUT": {"last_price": 22850.0, "ohlc": {}},
        }
        expiry_map = {
            "NFO:NIFTY26MARFUT": date(2026, 3, 31),
            "NFO:NIFTY26APRFUT": date(2026, 4, 28),
            "NFO:NIFTY26MAYFUT": date(2026, 5, 26),
        }

        chain = build_futures_chain_from_kite(
            "NIFTY", 22500.0, kite_quotes, expiry_map, lot_size=65,
        )
        assert chain is not None
        assert chain.far_month is not None
        assert chain.far_month.last_price == 22850.0

    def test_returns_none_for_empty(self):
        chain = build_futures_chain_from_kite("NIFTY", 22500.0, {}, {})
        assert chain is None

    def test_skips_options_in_quotes(self):
        kite_quotes = {
            "NFO:NIFTY26MARFUT": {"last_price": 22650.0, "ohlc": {}},
            "NFO:NIFTY2631024500CE": {"last_price": 130.0, "ohlc": {}},
        }
        expiry_map = {
            "NFO:NIFTY26MARFUT": date(2026, 3, 31),
            "NFO:NIFTY2631024500CE": date(2026, 3, 10),
        }

        chain = build_futures_chain_from_kite(
            "NIFTY", 22500.0, kite_quotes, expiry_map,
        )
        assert chain is not None
        assert chain.near_month.last_price == 22650.0
        assert chain.next_month is None

    def test_sorts_by_expiry(self):
        # Provide quotes in reverse order
        kite_quotes = {
            "NFO:NIFTY26APRFUT": {"last_price": 22750.0, "ohlc": {}},
            "NFO:NIFTY26MARFUT": {"last_price": 22650.0, "ohlc": {}},
        }
        expiry_map = {
            "NFO:NIFTY26APRFUT": date(2026, 4, 28),
            "NFO:NIFTY26MARFUT": date(2026, 3, 31),
        }

        chain = build_futures_chain_from_kite(
            "NIFTY", 22500.0, kite_quotes, expiry_map,
        )
        assert chain is not None
        # Near month should be March despite being second in input
        assert chain.near_month.expiry == date(2026, 3, 31)
        assert chain.next_month.expiry == date(2026, 4, 28)

    def test_skips_missing_expiry(self):
        kite_quotes = {
            "NFO:NIFTY26MARFUT": {"last_price": 22650.0, "ohlc": {}},
            "NFO:NIFTY26APRFUT": {"last_price": 22750.0, "ohlc": {}},
        }
        # Only provide expiry for March
        expiry_map = {
            "NFO:NIFTY26MARFUT": date(2026, 3, 31),
        }

        chain = build_futures_chain_from_kite(
            "NIFTY", 22500.0, kite_quotes, expiry_map,
        )
        assert chain is not None
        assert chain.next_month is None
