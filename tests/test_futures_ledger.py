"""Tests for futures trade ledger."""

from datetime import date
from pathlib import Path
import tempfile

import pytest

from diamond_options.data.futures_ledger import (
    FuturesLedger,
    FuturesPosition,
    FuturesTrade,
)


@pytest.fixture
def ledger():
    """Fresh futures ledger with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_futures.db"
        yield FuturesLedger(name="test", db_path=db_path)


def _make_trade(
    action="BUY",
    symbol="NIFTY",
    expiry="2026-03-31",
    lots=1,
    lot_size=65,
    price=22650.0,
    total_cost=50.0,
    strategy_tag="single",
    trade_group="grp1",
    rationale="Test trade",
) -> FuturesTrade:
    return FuturesTrade(
        timestamp="2026-03-09 10:00:00",
        action=action,
        symbol=symbol,
        expiry=expiry,
        lots=lots,
        lot_size=lot_size,
        price=price,
        total_cost=total_cost,
        strategy_tag=strategy_tag,
        trade_group=trade_group,
        rationale=rationale,
    )


class TestFuturesTrade:
    def test_turnover(self):
        t = _make_trade(price=22650.0, lots=2, lot_size=65)
        assert t.turnover == 22650.0 * 2 * 65

    def test_quantity(self):
        t = _make_trade(lots=3, lot_size=65)
        assert t.quantity == 195


class TestFuturesPosition:
    def test_is_long(self):
        pos = FuturesPosition("NIFTY", "2026-03-31", 2, 65, 22650.0, "single", "grp1")
        assert pos.is_long
        assert not pos.is_short

    def test_is_short(self):
        pos = FuturesPosition("NIFTY", "2026-03-31", -1, 65, 22650.0, "single", "grp1")
        assert pos.is_short
        assert not pos.is_long

    def test_quantity(self):
        pos = FuturesPosition("NIFTY", "2026-03-31", 2, 65, 22650.0, "single", "grp1")
        assert pos.quantity == 130

    def test_notional_value(self):
        pos = FuturesPosition("NIFTY", "2026-03-31", 2, 65, 22650.0, "single", "grp1")
        assert pos.notional_value == 22650.0 * 130

    def test_unrealized_pnl_long(self):
        pos = FuturesPosition("NIFTY", "2026-03-31", 1, 65, 22650.0, "single", "grp1")
        # Long 65 units at 22650, current price 22700 → profit
        pnl = pos.unrealized_pnl(22700.0)
        assert pnl == (22700.0 - 22650.0) * 65

    def test_unrealized_pnl_short(self):
        pos = FuturesPosition("NIFTY", "2026-03-31", -1, 65, 22650.0, "single", "grp1")
        # Short 65 units at 22650, current price 22600 → profit
        pnl = pos.unrealized_pnl(22600.0)
        assert pnl == (22600.0 - 22650.0) * (-65)  # = 50 * 65 = 3250

    def test_margin_estimate(self):
        pos = FuturesPosition("NIFTY", "2026-03-31", 1, 65, 22650.0, "single", "grp1")
        margin = pos.margin_estimate(0.10)
        assert margin == pos.notional_value * 0.10


class TestFuturesLedgerState:
    def test_initial_cash(self, ledger):
        assert ledger.get_cash() == 500000

    def test_initial_margin(self, ledger):
        assert ledger.get_margin_used() == 0.0

    def test_initial_capital(self, ledger):
        assert ledger.get_initial_capital() == 500000

    def test_set_cash(self, ledger):
        ledger.set_cash(400000)
        assert ledger.get_cash() == 400000

    def test_set_margin(self, ledger):
        ledger.set_margin_used(150000)
        assert ledger.get_margin_used() == 150000


class TestFuturesTrading:
    def test_buy_opens_position(self, ledger):
        trade = _make_trade(action="BUY")
        ledger.record_trade(trade)

        positions = ledger.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "NIFTY"
        assert positions[0].lots == 1
        assert positions[0].avg_price == 22650.0

    def test_buy_only_deducts_costs(self, ledger):
        """Futures trading only deducts transaction costs, not notional."""
        trade = _make_trade(action="BUY", total_cost=50.0)
        ledger.record_trade(trade)
        assert ledger.get_cash() == 500000 - 50.0

    def test_sell_opens_short(self, ledger):
        trade = _make_trade(action="SELL")
        ledger.record_trade(trade)

        positions = ledger.get_positions()
        assert len(positions) == 1
        assert positions[0].lots == -1

    def test_buy_sell_closes_position(self, ledger):
        buy = _make_trade(action="BUY", price=22650.0, total_cost=50.0)
        ledger.record_trade(buy)

        sell = FuturesTrade(
            timestamp="2026-03-10 14:00:00",
            action="SELL",
            symbol="NIFTY",
            expiry="2026-03-31",
            lots=1,
            lot_size=65,
            price=22750.0,
            total_cost=50.0,
            strategy_tag="single",
            trade_group="grp1",
            rationale="Profit target",
        )
        ledger.record_trade(sell)

        positions = ledger.get_positions()
        assert len(positions) == 0

    def test_add_to_long_position(self, ledger):
        t1 = _make_trade(action="BUY", lots=1, price=22650.0)
        ledger.record_trade(t1)

        t2 = FuturesTrade(
            timestamp="2026-03-09 11:00:00",
            action="BUY",
            symbol="NIFTY",
            expiry="2026-03-31",
            lots=1,
            lot_size=65,
            price=22700.0,
            total_cost=50.0,
            strategy_tag="single",
            trade_group="grp1",
            rationale="Adding",
        )
        ledger.record_trade(t2)

        positions = ledger.get_positions()
        assert len(positions) == 1
        assert positions[0].lots == 2
        # Average: (22650 + 22700) / 2 = 22675
        assert positions[0].avg_price == 22675.0

    def test_partial_close(self, ledger):
        buy = _make_trade(action="BUY", lots=3, price=22650.0)
        ledger.record_trade(buy)

        sell = FuturesTrade(
            timestamp="2026-03-10 10:00:00",
            action="SELL",
            symbol="NIFTY",
            expiry="2026-03-31",
            lots=1,
            lot_size=65,
            price=22700.0,
            total_cost=50.0,
            strategy_tag="single",
            trade_group="grp1",
            rationale="Partial close",
        )
        ledger.record_trade(sell)

        positions = ledger.get_positions()
        assert len(positions) == 1
        assert positions[0].lots == 2
        # Avg price unchanged on partial close
        assert positions[0].avg_price == 22650.0

    def test_separate_trade_groups(self, ledger):
        t1 = _make_trade(trade_group="trend_1")
        ledger.record_trade(t1)

        t2 = _make_trade(trade_group="hedge_1", strategy_tag="hedge")
        ledger.record_trade(t2)

        positions = ledger.get_positions()
        assert len(positions) == 2

    def test_different_expiries(self, ledger):
        t1 = _make_trade(expiry="2026-03-31", trade_group="near")
        ledger.record_trade(t1)

        t2 = _make_trade(expiry="2026-04-28", trade_group="next")
        ledger.record_trade(t2)

        positions = ledger.get_positions()
        assert len(positions) == 2


class TestFuturesQueries:
    def test_get_trades(self, ledger):
        t1 = _make_trade()
        ledger.record_trade(t1)

        trades = ledger.get_trades()
        assert len(trades) == 1
        assert trades[0].symbol == "NIFTY"

    def test_get_trades_since(self, ledger):
        t1 = _make_trade()
        ledger.record_trade(t1)

        trades = ledger.get_trades(since="2026-03-10")
        assert len(trades) == 0

        trades = ledger.get_trades(since="2026-03-09")
        assert len(trades) == 1

    def test_get_trades_by_symbol(self, ledger):
        t1 = _make_trade(symbol="NIFTY", trade_group="g1")
        t2 = _make_trade(symbol="RELIANCE", trade_group="g2", lot_size=250, price=2500.0)
        ledger.record_trade(t1)
        ledger.record_trade(t2)

        nifty_trades = ledger.get_trades_by_symbol("NIFTY")
        assert len(nifty_trades) == 1

    def test_get_positions_by_symbol(self, ledger):
        t1 = _make_trade(symbol="NIFTY", trade_group="g1")
        t2 = _make_trade(symbol="RELIANCE", trade_group="g2", lot_size=250, price=2500.0)
        ledger.record_trade(t1)
        ledger.record_trade(t2)

        nifty = ledger.get_positions_by_symbol("NIFTY")
        assert len(nifty) == 1
        assert nifty[0].symbol == "NIFTY"

    def test_get_positions_by_group(self, ledger):
        t1 = _make_trade(trade_group="spread_1", strategy_tag="calendar")
        ledger.record_trade(t1)

        positions = ledger.get_positions_by_group("spread_1")
        assert len(positions) == 1

    def test_get_expiring_positions(self, ledger):
        t1 = _make_trade(expiry="2026-03-31", trade_group="g1")
        t2 = _make_trade(expiry="2026-04-28", trade_group="g2")
        ledger.record_trade(t1)
        ledger.record_trade(t2)

        expiring = ledger.get_expiring_positions("2026-03-31")
        assert len(expiring) == 1

    def test_total_fees(self, ledger):
        t1 = _make_trade(total_cost=50.0)
        t2 = FuturesTrade(
            timestamp="2026-03-10 10:00:00",
            action="SELL",
            symbol="NIFTY",
            expiry="2026-03-31",
            lots=1,
            lot_size=65,
            price=22700.0,
            total_cost=45.0,
            strategy_tag="single",
            trade_group="grp1",
            rationale="",
        )
        ledger.record_trade(t1)
        ledger.record_trade(t2)

        assert ledger.get_total_fees() == 95.0

    def test_realized_pnl(self, ledger):
        buy = _make_trade(action="BUY", price=22650.0, total_cost=50.0)
        ledger.record_trade(buy)

        sell = FuturesTrade(
            timestamp="2026-03-10 14:00:00",
            action="SELL",
            symbol="NIFTY",
            expiry="2026-03-31",
            lots=1,
            lot_size=65,
            price=22750.0,
            total_cost=50.0,
            strategy_tag="single",
            trade_group="grp1",
            rationale="Close",
        )
        ledger.record_trade(sell)

        pnl = ledger.get_realized_pnl("grp1")
        # SELL: +22750*65 - 50, BUY: -22650*65 - 50 → (22750-22650)*65 - 100 = 6400
        expected = (22750.0 - 22650.0) * 65 - 100.0
        assert abs(pnl - expected) < 0.01

    def test_count_open_positions(self, ledger):
        t1 = _make_trade(trade_group="g1")
        t2 = _make_trade(trade_group="g2", symbol="RELIANCE", lot_size=250, price=2500.0)
        ledger.record_trade(t1)
        ledger.record_trade(t2)

        assert ledger.count_open_positions() == 2


class TestFuturesExpiry:
    def test_expire_long_position(self, ledger):
        buy = _make_trade(action="BUY", price=22650.0, total_cost=0.0)
        ledger.record_trade(buy)

        pnl = ledger.expire_positions("2026-03-31", {"NIFTY": 22800.0})
        # Long at 22650, settled at 22800 → (22800-22650)*65 = 9750
        assert abs(pnl - (22800.0 - 22650.0) * 65) < 0.01

        # Position should be closed
        assert len(ledger.get_positions()) == 0

    def test_expire_short_position(self, ledger):
        sell = _make_trade(action="SELL", price=22700.0, total_cost=0.0)
        ledger.record_trade(sell)

        pnl = ledger.expire_positions("2026-03-31", {"NIFTY": 22600.0})
        # Short at 22700, settled at 22600 → (22600-22700)*(-65) = 6500
        assert abs(pnl - (22700.0 - 22600.0) * 65) < 0.01

    def test_expire_no_settlement_price(self, ledger):
        buy = _make_trade(action="BUY", price=22650.0, total_cost=0.0)
        ledger.record_trade(buy)

        pnl = ledger.expire_positions("2026-03-31")
        # Settlement at 0 → loss of entire notional
        assert pnl == (0.0 - 22650.0) * 65


class TestFuturesReset:
    def test_reset_clears_everything(self, ledger):
        trade = _make_trade()
        ledger.record_trade(trade)
        ledger.set_margin_used(150000)

        ledger.reset()

        assert ledger.get_cash() == 500000
        assert ledger.get_margin_used() == 0
        assert len(ledger.get_positions()) == 0
        assert len(ledger.get_trades()) == 0

    def test_reset_custom_capital(self, ledger):
        ledger.reset(initial_capital=1000000)
        assert ledger.get_cash() == 1000000
        assert ledger.get_initial_capital() == 1000000
