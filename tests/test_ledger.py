"""Tests for options trade ledger."""

from datetime import date
from pathlib import Path
import tempfile

import pytest

from diamond_options.data.ledger import OptionsLedger, OptionTrade, Position


@pytest.fixture
def ledger():
    """Fresh ledger with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield OptionsLedger(name="test", db_path=db_path)


class TestLedgerState:
    def test_initial_cash(self, ledger):
        assert ledger.get_cash() == 500000  # Default capital

    def test_initial_margin(self, ledger):
        assert ledger.get_margin_used() == 0.0

    def test_initial_capital(self, ledger):
        assert ledger.get_initial_capital() == 500000

    def test_set_cash(self, ledger):
        ledger.set_cash(400000)
        assert ledger.get_cash() == 400000

    def test_set_margin(self, ledger):
        ledger.set_margin_used(50000)
        assert ledger.get_margin_used() == 50000


class TestTrading:
    def test_buy_opens_position(self, ledger):
        trade = OptionTrade(
            timestamp="2026-03-07 10:00:00",
            action="BUY",
            symbol="NIFTY",
            strike=22500,
            option_type="CE",
            expiry="2026-03-12",
            lots=1,
            lot_size=25,
            price=130.0,
            total_cost=25.0,
            strategy_tag="single",
            trade_group="grp1",
            rationale="Bullish setup",
        )
        ledger.record_trade(trade)

        positions = ledger.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "NIFTY"
        assert positions[0].lots == 1
        assert positions[0].avg_price == 130.0

    def test_buy_reduces_cash(self, ledger):
        trade = OptionTrade(
            timestamp="2026-03-07 10:00:00",
            action="BUY",
            symbol="NIFTY",
            strike=22500,
            option_type="CE",
            expiry="2026-03-12",
            lots=1,
            lot_size=25,
            price=130.0,
            total_cost=25.0,
            strategy_tag="single",
            trade_group="grp1",
            rationale="",
        )
        ledger.record_trade(trade)

        # Cash = 500000 - (130 * 1 * 25) - 25 = 496725
        assert ledger.get_cash() == 500000 - 130 * 25 - 25

    def test_sell_opens_short_position(self, ledger):
        trade = OptionTrade(
            timestamp="2026-03-07 10:00:00",
            action="SELL",
            symbol="NIFTY",
            strike=22500,
            option_type="PE",
            expiry="2026-03-12",
            lots=1,
            lot_size=25,
            price=100.0,
            total_cost=30.0,
            strategy_tag="single",
            trade_group="grp2",
            rationale="Premium selling",
        )
        ledger.record_trade(trade)

        positions = ledger.get_positions()
        assert len(positions) == 1
        assert positions[0].lots == -1  # Short
        assert positions[0].is_short is True

    def test_sell_increases_cash(self, ledger):
        trade = OptionTrade(
            timestamp="2026-03-07 10:00:00",
            action="SELL",
            symbol="NIFTY",
            strike=22500,
            option_type="PE",
            expiry="2026-03-12",
            lots=1,
            lot_size=25,
            price=100.0,
            total_cost=30.0,
            strategy_tag="single",
            trade_group="grp2",
            rationale="",
        )
        ledger.record_trade(trade)

        # Cash = 500000 + (100 * 1 * 25) - 30 = 502470
        assert ledger.get_cash() == 500000 + 100 * 25 - 30

    def test_close_position(self, ledger):
        # Open
        ledger.record_trade(OptionTrade(
            timestamp="2026-03-07 10:00:00",
            action="BUY", symbol="NIFTY", strike=22500, option_type="CE",
            expiry="2026-03-12", lots=1, lot_size=25, price=130.0,
            total_cost=25.0, strategy_tag="single", trade_group="grp1",
            rationale="Open",
        ))
        # Close
        ledger.record_trade(OptionTrade(
            timestamp="2026-03-07 14:00:00",
            action="SELL", symbol="NIFTY", strike=22500, option_type="CE",
            expiry="2026-03-12", lots=1, lot_size=25, price=150.0,
            total_cost=30.0, strategy_tag="single", trade_group="grp1",
            rationale="Close with profit",
        ))

        positions = ledger.get_positions()
        assert len(positions) == 0  # Closed

    def test_trade_history(self, ledger):
        for i in range(3):
            ledger.record_trade(OptionTrade(
                timestamp=f"2026-03-07 {10 + i}:00:00",
                action="BUY", symbol="NIFTY", strike=22500, option_type="CE",
                expiry="2026-03-12", lots=1, lot_size=25, price=130.0,
                total_cost=25.0, strategy_tag="single", trade_group=f"grp{i}",
                rationale="",
            ))
        trades = ledger.get_trades()
        assert len(trades) == 3

    def test_total_fees(self, ledger):
        ledger.record_trade(OptionTrade(
            timestamp="2026-03-07 10:00:00",
            action="BUY", symbol="NIFTY", strike=22500, option_type="CE",
            expiry="2026-03-12", lots=1, lot_size=25, price=130.0,
            total_cost=25.50, strategy_tag="single", trade_group="grp1",
            rationale="",
        ))
        assert ledger.get_total_fees() == 25.50

    def test_count_open_positions(self, ledger):
        assert ledger.count_open_positions() == 0

        ledger.record_trade(OptionTrade(
            timestamp="2026-03-07 10:00:00",
            action="BUY", symbol="NIFTY", strike=22500, option_type="CE",
            expiry="2026-03-12", lots=1, lot_size=25, price=130.0,
            total_cost=25.0, strategy_tag="single", trade_group="grp1",
            rationale="",
        ))
        assert ledger.count_open_positions() == 1


class TestMultiLeg:
    def test_iron_condor_positions(self, ledger):
        """Iron condor should create 4 positions in same trade group."""
        group = "ic_nifty_20260312"
        legs = [
            ("SELL", 22300, "PE", 35.0),   # Short OTM put
            ("BUY", 22200, "PE", 18.0),    # Long far OTM put (hedge)
            ("SELL", 22700, "CE", 45.0),   # Short OTM call
            ("BUY", 22800, "CE", 22.0),   # Long far OTM call (hedge)
        ]

        for action, strike, opt_type, price in legs:
            ledger.record_trade(OptionTrade(
                timestamp="2026-03-07 10:00:00",
                action=action, symbol="NIFTY", strike=strike,
                option_type=opt_type, expiry="2026-03-12",
                lots=1, lot_size=25, price=price, total_cost=25.0,
                strategy_tag="iron_condor", trade_group=group,
                rationale="IC setup",
            ))

        positions = ledger.get_positions_by_group(group)
        assert len(positions) == 4

        short_legs = [p for p in positions if p.is_short]
        long_legs = [p for p in positions if p.is_long]
        assert len(short_legs) == 2
        assert len(long_legs) == 2


class TestReset:
    def test_reset_clears_everything(self, ledger):
        ledger.record_trade(OptionTrade(
            timestamp="2026-03-07 10:00:00",
            action="BUY", symbol="NIFTY", strike=22500, option_type="CE",
            expiry="2026-03-12", lots=1, lot_size=25, price=130.0,
            total_cost=25.0, strategy_tag="single", trade_group="grp1",
            rationale="",
        ))

        ledger.reset()
        assert ledger.get_cash() == 500000
        assert len(ledger.get_positions()) == 0
        assert len(ledger.get_trades()) == 0
