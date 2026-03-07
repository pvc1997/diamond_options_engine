"""Tests for Kite MCP bridge — parsing, chain building, OI analysis."""

from datetime import date

import pytest

from diamond_options.data.kite_bridge import (
    OIAnalysis,
    OILevel,
    analyze_oi,
    build_chain_from_kite_quotes,
    detect_oi_walls,
    get_expiry_from_kite,
    get_lot_size_from_kite,
    kite_quote_to_option_quote,
    parse_kite_symbol,
)
from diamond_options.data.options_chain import OptionsChain, OptionQuote


# ═══════════════════════════════════════════════════════════════
# parse_kite_symbol
# ═══════════════════════════════════════════════════════════════


class TestParseKiteSymbol:
    def test_weekly_format_ce(self):
        result = parse_kite_symbol("NIFTY2631024450CE")
        assert result is not None
        assert result["symbol"] == "NIFTY"
        assert result["expiry"] == date(2026, 3, 10)
        assert result["strike"] == 24450.0
        assert result["option_type"] == "CE"

    def test_weekly_format_pe(self):
        result = parse_kite_symbol("NIFTY2631024200PE")
        assert result is not None
        assert result["strike"] == 24200.0
        assert result["option_type"] == "PE"

    def test_monthly_format(self):
        result = parse_kite_symbol("NIFTY26MAR24450CE")
        assert result is not None
        assert result["symbol"] == "NIFTY"
        assert result["strike"] == 24450.0
        assert result["option_type"] == "CE"

    def test_banknifty_weekly(self):
        result = parse_kite_symbol("BANKNIFTY2631057500CE")
        assert result is not None
        assert result["symbol"] == "BANKNIFTY"
        assert result["strike"] == 57500.0

    def test_invalid_symbol(self):
        assert parse_kite_symbol("INVALID") is None
        assert parse_kite_symbol("") is None

    def test_stock_option(self):
        result = parse_kite_symbol("RELIANCE26MAR2500CE")
        assert result is not None
        assert result["symbol"] == "RELIANCE"
        assert result["strike"] == 2500.0


# ═══════════════════════════════════════════════════════════════
# kite_quote_to_option_quote
# ═══════════════════════════════════════════════════════════════


class TestKiteQuoteToOptionQuote:
    def test_basic_conversion(self):
        kite_quote = {
            "last_price": 169.3,
            "oi": 1597700,
            "volume": 50000,
            "ohlc": {"open": 289, "high": 298.8, "low": 157.05, "close": 346.2},
        }
        result = kite_quote_to_option_quote(
            "NFO:NIFTY2631024550CE", kite_quote, date(2026, 3, 10),
        )
        assert result is not None
        assert result.strike == 24550.0
        assert result.option_type == "CE"
        assert result.ltp == 169.3
        assert result.open_interest == 1597700
        assert result.volume == 50000
        assert result.change == pytest.approx(-176.9, abs=0.1)

    def test_missing_oi(self):
        kite_quote = {"last_price": 100, "ohlc": {"close": 100}}
        result = kite_quote_to_option_quote(
            "NFO:NIFTY2631024500CE", kite_quote, date(2026, 3, 10),
        )
        assert result is not None
        assert result.open_interest == 0

    def test_invalid_key(self):
        result = kite_quote_to_option_quote(
            "NFO:INVALID", {"last_price": 100}, date(2026, 3, 10),
        )
        assert result is None


# ═══════════════════════════════════════════════════════════════
# build_chain_from_kite_quotes
# ═══════════════════════════════════════════════════════════════


def _make_kite_quotes():
    """Helper: build sample Kite quotes dict."""
    return {
        "NFO:NIFTY2631024400CE": {
            "last_price": 250, "oi": 500000, "volume": 10000,
            "ohlc": {"close": 300},
        },
        "NFO:NIFTY2631024450CE": {
            "last_price": 200, "oi": 1500000, "volume": 20000,
            "ohlc": {"close": 250},
        },
        "NFO:NIFTY2631024500CE": {
            "last_price": 150, "oi": 3000000, "volume": 30000,
            "ohlc": {"close": 200},
        },
        "NFO:NIFTY2631024400PE": {
            "last_price": 150, "oi": 3000000, "volume": 15000,
            "ohlc": {"close": 100},
        },
        "NFO:NIFTY2631024450PE": {
            "last_price": 200, "oi": 2000000, "volume": 25000,
            "ohlc": {"close": 150},
        },
        "NFO:NIFTY2631024500PE": {
            "last_price": 250, "oi": 1000000, "volume": 12000,
            "ohlc": {"close": 200},
        },
    }


class TestBuildChainFromKite:
    def test_builds_chain(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        assert isinstance(chain, OptionsChain)
        assert chain.symbol == "NIFTY"
        assert chain.spot_price == 24450.0
        assert len(chain.calls) == 3
        assert len(chain.puts) == 3

    def test_calls_sorted(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        strikes = [q.strike for q in chain.calls]
        assert strikes == sorted(strikes)

    def test_oi_preserved(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        ce_500 = chain.get_call(24500)
        assert ce_500 is not None
        assert ce_500.open_interest == 3000000

    def test_pcr_from_live_oi(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        pcr = chain.pcr_oi()
        assert pcr is not None
        total_put = 3000000 + 2000000 + 1000000
        total_call = 500000 + 1500000 + 3000000
        assert pcr == pytest.approx(total_put / total_call, abs=0.01)

    def test_max_pain(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        mp = chain.max_pain()
        assert mp is not None
        assert 24400 <= mp <= 24500

    def test_empty_quotes(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), {},
        )
        assert len(chain.calls) == 0
        assert len(chain.puts) == 0


# ═══════════════════════════════════════════════════════════════
# analyze_oi
# ═══════════════════════════════════════════════════════════════


class TestAnalyzeOI:
    def test_basic_analysis(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        analysis = analyze_oi(chain)
        assert isinstance(analysis, OIAnalysis)
        assert analysis.total_call_oi > 0
        assert analysis.total_put_oi > 0
        assert analysis.pcr_oi > 0

    def test_call_wall_detected(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        analysis = analyze_oi(chain)
        assert analysis.call_wall == 24500.0  # highest call OI
        assert analysis.call_wall_oi == 3000000

    def test_put_base_detected(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        analysis = analyze_oi(chain)
        assert analysis.put_base == 24400.0  # highest put OI
        assert analysis.put_base_oi == 3000000

    def test_key_levels_sorted(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        analysis = analyze_oi(chain)
        assert len(analysis.key_levels) > 0
        # Should be sorted by total OI descending
        for i in range(len(analysis.key_levels) - 1):
            curr = analysis.key_levels[i]
            nxt = analysis.key_levels[i + 1]
            assert (curr.call_oi + curr.put_oi) >= (nxt.call_oi + nxt.put_oi)


# ═══════════════════════════════════════════════════════════════
# detect_oi_walls
# ═══════════════════════════════════════════════════════════════


class TestDetectOIWalls:
    def test_detects_walls(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        walls = detect_oi_walls(chain, 24450.0)
        assert "call_walls" in walls
        assert "put_walls" in walls
        assert "interpretation" in walls

    def test_call_wall_above_spot(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        walls = detect_oi_walls(chain, 24450.0)
        for wall in walls["call_walls"]:
            assert wall["strike"] > 24450.0

    def test_put_wall_below_spot(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), _make_kite_quotes(),
        )
        walls = detect_oi_walls(chain, 24450.0)
        for wall in walls["put_walls"]:
            assert wall["strike"] < 24450.0

    def test_empty_chain(self):
        chain = build_chain_from_kite_quotes(
            "NIFTY", 24450.0, date(2026, 3, 10), {},
        )
        walls = detect_oi_walls(chain, 24450.0)
        assert walls["call_walls"] == []
        assert walls["put_walls"] == []


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


class TestHelpers:
    def test_get_lot_size(self):
        assert get_lot_size_from_kite({"lot_size": 65}) == 65
        assert get_lot_size_from_kite({}) == 0

    def test_get_expiry(self):
        exp = get_expiry_from_kite({"expiry_date": "2026-03-10"})
        assert exp == date(2026, 3, 10)
        assert get_expiry_from_kite({}) is None
        assert get_expiry_from_kite({"expiry_date": "invalid"}) is None
