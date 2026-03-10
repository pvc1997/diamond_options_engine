"""Tests for futures position parsing and sync in position_sync.py."""

from datetime import date

import pytest

from diamond_options.data.position_sync import (
    KiteFuturesPosition,
    compare_futures_positions,
    kite_futures_position_to_trade,
    parse_kite_futures_position,
)
from diamond_options.data.futures_ledger import FuturesPosition


class TestParseKiteFuturesPosition:
    def test_parse_nifty_long(self):
        raw = {
            "tradingsymbol": "NIFTY26MARFUT",
            "exchange": "NFO",
            "quantity": 65,
            "average_price": 22650.0,
            "last_price": 22700.0,
            "pnl": 3250.0,
            "m2m": 3250.0,
            "product": "NRML",
            "instrument_token": 12345,
        }
        result = parse_kite_futures_position(raw)
        assert result is not None
        assert result.symbol == "NIFTY"
        assert result.quantity == 65
        assert result.is_long
        assert result.avg_price == 22650.0
        assert result.ltp == 22700.0
        assert result.expiry_year == 2026
        assert result.expiry_month == 3

    def test_parse_short_position(self):
        raw = {
            "tradingsymbol": "RELIANCE26APRFUT",
            "quantity": -250,
            "average_price": 2500.0,
            "last_price": 2480.0,
            "pnl": 5000.0,
            "m2m": 5000.0,
            "product": "NRML",
            "instrument_token": 0,
        }
        result = parse_kite_futures_position(raw)
        assert result is not None
        assert result.symbol == "RELIANCE"
        assert result.is_short
        assert result.expiry_month == 4

    def test_rejects_options_symbol(self):
        raw = {
            "tradingsymbol": "NIFTY2631024500CE",
            "quantity": 65,
            "average_price": 130.0,
            "last_price": 150.0,
        }
        assert parse_kite_futures_position(raw) is None

    def test_rejects_zero_quantity(self):
        raw = {
            "tradingsymbol": "NIFTY26MARFUT",
            "quantity": 0,
            "average_price": 22650.0,
            "last_price": 22650.0,
        }
        assert parse_kite_futures_position(raw) is None

    def test_rejects_empty_symbol(self):
        raw = {"tradingsymbol": "", "quantity": 65}
        assert parse_kite_futures_position(raw) is None

    def test_unrealized_pnl(self):
        raw = {
            "tradingsymbol": "NIFTY26MARFUT",
            "quantity": 65,
            "average_price": 22650.0,
            "last_price": 22700.0,
            "pnl": 0, "m2m": 0, "product": "NRML", "instrument_token": 0,
        }
        pos = parse_kite_futures_position(raw)
        assert pos is not None
        assert pos.unrealized_pnl == (22700.0 - 22650.0) * 65

    def test_notional_value(self):
        raw = {
            "tradingsymbol": "NIFTY26MARFUT",
            "quantity": 130,  # 2 lots
            "average_price": 22650.0,
            "last_price": 22700.0,
            "pnl": 0, "m2m": 0, "product": "NRML", "instrument_token": 0,
        }
        pos = parse_kite_futures_position(raw)
        assert pos is not None
        assert pos.notional_value == abs(22700.0 * 130)

    def test_lots_calculation(self):
        raw = {
            "tradingsymbol": "NIFTY26MARFUT",
            "quantity": 195,  # 3 lots of 65
            "average_price": 22650.0,
            "last_price": 22700.0,
            "pnl": 0, "m2m": 0, "product": "NRML", "instrument_token": 0,
        }
        pos = parse_kite_futures_position(raw)
        assert pos is not None
        assert pos.lots == 3


class TestKiteFuturesPositionToTrade:
    def test_converts_long(self):
        kfp = KiteFuturesPosition(
            symbol="NIFTY",
            tradingsymbol="NIFTY26MARFUT",
            exchange="NFO",
            expiry_year=2026,
            expiry_month=3,
            quantity=65,
            avg_price=22650.0,
            ltp=22700.0,
            pnl=3250.0,
            m2m=3250.0,
            product="NRML",
            instrument_token=12345,
        )
        trade = kite_futures_position_to_trade(kfp)
        assert trade.action == "BUY"
        assert trade.symbol == "NIFTY"
        assert trade.lots == 1
        assert trade.price == 22650.0
        assert "2026-03" in trade.expiry

    def test_converts_short(self):
        kfp = KiteFuturesPosition(
            symbol="RELIANCE",
            tradingsymbol="RELIANCE26APRFUT",
            exchange="NFO",
            expiry_year=2026,
            expiry_month=4,
            quantity=-250,
            avg_price=2500.0,
            ltp=2480.0,
            pnl=5000.0,
            m2m=5000.0,
            product="NRML",
            instrument_token=0,
        )
        trade = kite_futures_position_to_trade(kfp)
        assert trade.action == "SELL"
        assert trade.lots == 1

    def test_custom_expiry(self):
        kfp = KiteFuturesPosition(
            symbol="NIFTY",
            tradingsymbol="NIFTY26MARFUT",
            exchange="NFO",
            expiry_year=2026,
            expiry_month=3,
            quantity=65,
            avg_price=22650.0,
            ltp=22700.0,
            pnl=0, m2m=0, product="NRML", instrument_token=0,
        )
        trade = kite_futures_position_to_trade(kfp, expiry=date(2026, 3, 31))
        assert trade.expiry == "2026-03-31"

    def test_auto_trade_group(self):
        kfp = KiteFuturesPosition(
            symbol="NIFTY",
            tradingsymbol="NIFTY26MARFUT",
            exchange="NFO",
            expiry_year=2026,
            expiry_month=3,
            quantity=65,
            avg_price=22650.0,
            ltp=22700.0,
            pnl=0, m2m=0, product="NRML", instrument_token=0,
        )
        trade = kite_futures_position_to_trade(kfp)
        assert trade.trade_group.startswith("kite_NIFTY_")
        assert "NRML" in trade.trade_group


class TestCompareFuturesPositions:
    def test_matched(self):
        kite = [
            KiteFuturesPosition(
                symbol="NIFTY", tradingsymbol="NIFTY26MARFUT", exchange="NFO",
                expiry_year=2026, expiry_month=3, quantity=65,
                avg_price=22650.0, ltp=22700.0, pnl=0, m2m=0,
                product="NRML", instrument_token=0,
            ),
        ]
        ledger = [
            FuturesPosition("NIFTY", "2026-03-31", 1, 65, 22650.0, "single", "grp1"),
        ]
        result = compare_futures_positions(kite, ledger)
        assert len(result["matched"]) == 1
        assert result["matched"][0]["qty_match"]

    def test_quantity_mismatch(self):
        kite = [
            KiteFuturesPosition(
                symbol="NIFTY", tradingsymbol="NIFTY26MARFUT", exchange="NFO",
                expiry_year=2026, expiry_month=3, quantity=130,  # 2 lots
                avg_price=22650.0, ltp=22700.0, pnl=0, m2m=0,
                product="NRML", instrument_token=0,
            ),
        ]
        ledger = [
            FuturesPosition("NIFTY", "2026-03-31", 1, 65, 22650.0, "single", "grp1"),
        ]
        result = compare_futures_positions(kite, ledger)
        assert not result["matched"][0]["qty_match"]
        assert result["matched"][0]["qty_diff"] == 65

    def test_kite_only(self):
        kite = [
            KiteFuturesPosition(
                symbol="NIFTY", tradingsymbol="NIFTY26MARFUT", exchange="NFO",
                expiry_year=2026, expiry_month=3, quantity=65,
                avg_price=22650.0, ltp=22700.0, pnl=0, m2m=0,
                product="NRML", instrument_token=0,
            ),
        ]
        result = compare_futures_positions(kite, [])
        assert len(result["kite_only"]) == 1
        assert "untracked" in result["summary"].lower()

    def test_ledger_only(self):
        ledger = [
            FuturesPosition("NIFTY", "2026-03-31", 1, 65, 22650.0, "single", "grp1"),
        ]
        result = compare_futures_positions([], ledger)
        assert len(result["ledger_only"]) == 1
        assert "stale" in result["summary"].lower()

    def test_all_in_sync(self):
        kite = [
            KiteFuturesPosition(
                symbol="NIFTY", tradingsymbol="NIFTY26MARFUT", exchange="NFO",
                expiry_year=2026, expiry_month=3, quantity=65,
                avg_price=22650.0, ltp=22700.0, pnl=0, m2m=0,
                product="NRML", instrument_token=0,
            ),
        ]
        ledger = [
            FuturesPosition("NIFTY", "2026-03-31", 1, 65, 22650.0, "single", "grp1"),
        ]
        result = compare_futures_positions(kite, ledger)
        assert "in sync" in result["summary"].lower()
