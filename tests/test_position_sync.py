"""Tests for live position sync from Kite broker."""

from __future__ import annotations

from datetime import date

import pytest

from diamond_options.data.position_sync import (
    KitePosition,
    PortfolioSync,
    compare_positions,
    detect_spreads,
    kite_position_to_trade,
    parse_kite_position,
    sync_positions,
)
from diamond_options.data.ledger import Position


# --- Fixtures / Helpers ---

def _make_kite_raw(
    tradingsymbol: str = "NIFTY2631024500CE",
    exchange: str = "NFO",
    instrument_token: int = 11647746,
    product: str = "NRML",
    quantity: int = 65,
    average_price: float = 195.75,
    last_price: float = 210.50,
    pnl: float = 958.75,
    m2m: float = 958.75,
) -> dict:
    """Create a raw Kite position dict."""
    return {
        "tradingsymbol": tradingsymbol,
        "exchange": exchange,
        "instrument_token": instrument_token,
        "product": product,
        "quantity": quantity,
        "average_price": average_price,
        "last_price": last_price,
        "pnl": pnl,
        "m2m": m2m,
        "unrealised": pnl,
        "realised": 0,
        "buy_quantity": max(quantity, 0),
        "sell_quantity": abs(min(quantity, 0)),
        "buy_price": average_price if quantity > 0 else 0,
        "sell_price": average_price if quantity < 0 else 0,
        "multiplier": 1,
        "value": -average_price * quantity,
        "buy_value": average_price * max(quantity, 0),
        "sell_value": average_price * abs(min(quantity, 0)),
        "day_buy_quantity": max(quantity, 0),
        "day_sell_quantity": abs(min(quantity, 0)),
        "day_buy_price": average_price if quantity > 0 else 0,
        "day_sell_price": average_price if quantity < 0 else 0,
        "day_buy_value": average_price * max(quantity, 0),
        "day_sell_value": average_price * abs(min(quantity, 0)),
        "overnight_quantity": 0,
    }


# --- 1. Parse Long Position ---

def test_parse_long_call():
    """Parse a long call position (positive quantity)."""
    raw = _make_kite_raw(
        tradingsymbol="NIFTY2631024500CE",
        quantity=65,
        average_price=195.75,
        last_price=210.50,
        pnl=958.75,
    )
    kp = parse_kite_position(raw)
    assert kp is not None
    assert kp.symbol == "NIFTY"
    assert kp.strike == 24500.0
    assert kp.option_type == "CE"
    assert kp.expiry == date(2026, 3, 10)
    assert kp.quantity == 65
    assert kp.is_long is True
    assert kp.is_short is False
    assert kp.avg_price == 195.75
    assert kp.ltp == 210.50
    assert kp.pnl == 958.75


# --- 2. Parse Short Position ---

def test_parse_short_put():
    """Parse a short put position (negative quantity)."""
    raw = _make_kite_raw(
        tradingsymbol="NIFTY2631024000PE",
        quantity=-65,
        average_price=80.25,
        last_price=65.00,
        pnl=991.25,
    )
    kp = parse_kite_position(raw)
    assert kp is not None
    assert kp.symbol == "NIFTY"
    assert kp.strike == 24000.0
    assert kp.option_type == "PE"
    assert kp.quantity == -65
    assert kp.is_long is False
    assert kp.is_short is True


# --- 3. Parse Stock Option ---

def test_parse_stock_option():
    """Parse a stock (non-index) option position."""
    raw = _make_kite_raw(
        tradingsymbol="RELIANCE2631025500CE",
        quantity=250,
        average_price=45.50,
        last_price=52.00,
    )
    kp = parse_kite_position(raw)
    assert kp is not None
    assert kp.symbol == "RELIANCE"
    assert kp.strike == 25500.0
    assert kp.option_type == "CE"
    assert kp.quantity == 250


# --- 4. Skip Futures Position ---

def test_skip_futures_position():
    """Futures positions (no CE/PE suffix) should return None."""
    raw = _make_kite_raw(tradingsymbol="NIFTY26MARFUT", quantity=65)
    kp = parse_kite_position(raw)
    assert kp is None


# --- 5. Skip Zero Quantity ---

def test_skip_zero_quantity():
    """Closed positions (quantity=0) should return None."""
    raw = _make_kite_raw(quantity=0)
    kp = parse_kite_position(raw)
    assert kp is None


# --- 6. Skip Empty Symbol ---

def test_skip_empty_tradingsymbol():
    """Missing tradingsymbol should return None."""
    raw = _make_kite_raw()
    raw["tradingsymbol"] = ""
    kp = parse_kite_position(raw)
    assert kp is None


# --- 7. KitePosition Lot Size (Index) ---

def test_kite_position_lot_size_index():
    """Lot size should be fetched from universe for known symbols."""
    raw = _make_kite_raw(tradingsymbol="NIFTY2631024500CE", quantity=130)
    kp = parse_kite_position(raw)
    assert kp is not None
    assert kp.lot_size == 65  # NIFTY lot size
    assert kp.lots == 2  # 130 / 65


# --- 8. KitePosition Lot Size (Stock) ---

def test_kite_position_lot_size_stock():
    """Lot size for stock options."""
    raw = _make_kite_raw(tradingsymbol="RELIANCE2631025500CE", quantity=500)
    kp = parse_kite_position(raw)
    assert kp is not None
    assert kp.lot_size == 250  # RELIANCE lot size
    assert kp.lots == 2


# --- 9. Sync Positions Summary ---

def test_sync_positions_summary():
    """sync_positions builds correct summary with long/short counts."""
    positions = [
        _make_kite_raw(
            tradingsymbol="NIFTY2631024500CE",
            quantity=65, pnl=500, m2m=500,
        ),
        _make_kite_raw(
            tradingsymbol="NIFTY2631024000PE",
            quantity=-65, pnl=300, m2m=300,
        ),
        _make_kite_raw(
            tradingsymbol="BANKNIFTY2631052000CE",
            quantity=15, pnl=-100, m2m=-100,
        ),
    ]
    ps = sync_positions(positions)
    assert isinstance(ps, PortfolioSync)
    assert len(ps.positions) == 3
    assert ps.num_long == 2
    assert ps.num_short == 1
    assert ps.total_pnl == 700.0  # 500 + 300 - 100
    assert ps.total_m2m == 700.0
    assert "NIFTY" in ps.net_quantity_by_symbol
    assert ps.net_quantity_by_symbol["NIFTY"] == 0  # 65 + (-65) = 0
    assert ps.net_quantity_by_symbol["BANKNIFTY"] == 15


# --- 10. Sync Empty Positions ---

def test_sync_empty_positions():
    """Empty position list should produce empty summary."""
    ps = sync_positions([])
    assert len(ps.positions) == 0
    assert ps.total_pnl == 0.0
    assert ps.num_long == 0
    assert ps.num_short == 0
    assert ps.net_quantity_by_symbol == {}


# --- 11. Sync with Futures (Separated) ---

def test_sync_separates_futures():
    """Futures positions should be in futures_positions, not positions."""
    positions = [
        _make_kite_raw(tradingsymbol="NIFTY2631024500CE", quantity=65, pnl=100, m2m=100),
        _make_kite_raw(tradingsymbol="NIFTY26MARFUT", quantity=65, pnl=200, m2m=200),
    ]
    ps = sync_positions(positions)
    assert len(ps.positions) == 1  # Only the option
    assert len(ps.futures_positions) == 1  # The future
    # Total P&L includes futures
    assert ps.total_pnl == 300.0


# --- 12. Convert to OptionTrade (Long) ---

def test_kite_to_trade_long():
    """Long position maps to BUY action."""
    raw = _make_kite_raw(
        tradingsymbol="NIFTY2631024500CE",
        quantity=65,
        average_price=195.75,
    )
    kp = parse_kite_position(raw)
    trade = kite_position_to_trade(kp)
    assert trade.action == "BUY"
    assert trade.symbol == "NIFTY"
    assert trade.strike == 24500.0
    assert trade.option_type == "CE"
    assert trade.lots == 1
    assert trade.lot_size == 65
    assert trade.price == 195.75
    assert trade.total_cost == 0.0
    assert trade.strategy_tag == "kite_sync"
    assert "kite_" in trade.trade_group


# --- 13. Convert to OptionTrade (Short) ---

def test_kite_to_trade_short():
    """Short position maps to SELL action."""
    raw = _make_kite_raw(
        tradingsymbol="NIFTY2631024000PE",
        quantity=-130,
        average_price=80.25,
    )
    kp = parse_kite_position(raw)
    trade = kite_position_to_trade(kp)
    assert trade.action == "SELL"
    assert trade.lots == 2  # 130 / 65
    assert trade.lot_size == 65


# --- 14. Compare Positions - All Matched ---

def test_compare_all_matched():
    """All positions matched between Kite and ledger."""
    kite_pos = [
        KitePosition(
            symbol="NIFTY", tradingsymbol="NIFTY2631024500CE",
            exchange="NFO", strike=24500.0, option_type="CE",
            expiry=date(2026, 3, 10), quantity=65, avg_price=195.75,
            ltp=210.50, pnl=958.75, m2m=958.75, product="NRML",
            instrument_token=11647746,
        ),
    ]
    ledger_pos = [
        Position(
            symbol="NIFTY", strike=24500.0, option_type="CE",
            expiry="2026-03-10", lots=1, lot_size=65,
            avg_price=195.75, strategy_tag="single", trade_group="grp1",
        ),
    ]
    result = compare_positions(kite_pos, ledger_pos)
    assert len(result["matched"]) == 1
    assert len(result["kite_only"]) == 0
    assert len(result["ledger_only"]) == 0
    assert result["matched"][0]["qty_match"] is True
    assert "All positions in sync" in result["summary"]


# --- 15. Compare Positions - Kite Only ---

def test_compare_kite_only():
    """Position exists in Kite but not in ledger."""
    kite_pos = [
        KitePosition(
            symbol="NIFTY", tradingsymbol="NIFTY2631024500CE",
            exchange="NFO", strike=24500.0, option_type="CE",
            expiry=date(2026, 3, 10), quantity=65, avg_price=195.75,
            ltp=210.50, pnl=958.75, m2m=958.75, product="NRML",
            instrument_token=11647746,
        ),
    ]
    ledger_pos = []
    result = compare_positions(kite_pos, ledger_pos)
    assert len(result["kite_only"]) == 1
    assert len(result["matched"]) == 0
    assert "untracked" in result["summary"].lower()


# --- 16. Compare Positions - Ledger Only ---

def test_compare_ledger_only():
    """Position exists in ledger but not in Kite (stale)."""
    kite_pos = []
    ledger_pos = [
        Position(
            symbol="NIFTY", strike=24500.0, option_type="CE",
            expiry="2026-03-10", lots=1, lot_size=65,
            avg_price=195.75, strategy_tag="single", trade_group="grp1",
        ),
    ]
    result = compare_positions(kite_pos, ledger_pos)
    assert len(result["ledger_only"]) == 1
    assert len(result["matched"]) == 0
    assert "stale" in result["summary"].lower()


# --- 17. Compare Positions - Quantity Mismatch ---

def test_compare_quantity_mismatch():
    """Same position but different quantities."""
    kite_pos = [
        KitePosition(
            symbol="NIFTY", tradingsymbol="NIFTY2631024500CE",
            exchange="NFO", strike=24500.0, option_type="CE",
            expiry=date(2026, 3, 10), quantity=130, avg_price=195.75,
            ltp=210.50, pnl=958.75, m2m=958.75, product="NRML",
            instrument_token=11647746,
        ),
    ]
    ledger_pos = [
        Position(
            symbol="NIFTY", strike=24500.0, option_type="CE",
            expiry="2026-03-10", lots=1, lot_size=65,
            avg_price=195.75, strategy_tag="single", trade_group="grp1",
        ),
    ]
    result = compare_positions(kite_pos, ledger_pos)
    assert len(result["matched"]) == 1
    assert result["matched"][0]["qty_match"] is False
    assert result["matched"][0]["qty_diff"] == 65  # 130 - 65
    assert "mismatch" in result["summary"].lower()


# --- 18. Detect Spreads ---

def test_detect_spreads_groups_by_symbol_expiry():
    """Positions with same symbol+expiry should be grouped."""
    positions = [
        KitePosition(
            symbol="NIFTY", tradingsymbol="NIFTY2631024500CE",
            exchange="NFO", strike=24500.0, option_type="CE",
            expiry=date(2026, 3, 10), quantity=65, avg_price=195.75,
            ltp=210.50, pnl=0, m2m=0, product="NRML", instrument_token=1,
        ),
        KitePosition(
            symbol="NIFTY", tradingsymbol="NIFTY2631024600CE",
            exchange="NFO", strike=24600.0, option_type="CE",
            expiry=date(2026, 3, 10), quantity=-65, avg_price=150.00,
            ltp=160.00, pnl=0, m2m=0, product="NRML", instrument_token=2,
        ),
        KitePosition(
            symbol="BANKNIFTY", tradingsymbol="BANKNIFTY2631052000CE",
            exchange="NFO", strike=52000.0, option_type="CE",
            expiry=date(2026, 3, 10), quantity=15, avg_price=300.00,
            ltp=310.00, pnl=0, m2m=0, product="NRML", instrument_token=3,
        ),
    ]
    groups = detect_spreads(positions)
    assert "NIFTY_2026-03-10" in groups
    assert len(groups["NIFTY_2026-03-10"]) == 2
    assert "BANKNIFTY_2026-03-10" in groups
    assert len(groups["BANKNIFTY_2026-03-10"]) == 1


# --- 19. Detect Spreads - Bull Call Spread ---

def test_detect_spreads_bull_call():
    """A bull call spread has one long and one short CE at same expiry."""
    positions = [
        KitePosition(
            symbol="NIFTY", tradingsymbol="NIFTY2631024500CE",
            exchange="NFO", strike=24500.0, option_type="CE",
            expiry=date(2026, 3, 10), quantity=65, avg_price=195.75,
            ltp=210.50, pnl=0, m2m=0, product="NRML", instrument_token=1,
        ),
        KitePosition(
            symbol="NIFTY", tradingsymbol="NIFTY2631024600CE",
            exchange="NFO", strike=24600.0, option_type="CE",
            expiry=date(2026, 3, 10), quantity=-65, avg_price=150.00,
            ltp=160.00, pnl=0, m2m=0, product="NRML", instrument_token=2,
        ),
    ]
    groups = detect_spreads(positions)
    group = groups["NIFTY_2026-03-10"]
    assert len(group) == 2
    long_legs = [p for p in group if p.is_long]
    short_legs = [p for p in group if p.is_short]
    assert len(long_legs) == 1
    assert len(short_legs) == 1


# --- 20. Mixed Products (NRML + MIS) ---

def test_sync_mixed_products():
    """Positions with different products should all be parsed."""
    positions = [
        _make_kite_raw(
            tradingsymbol="NIFTY2631024500CE",
            quantity=65, product="NRML", pnl=100, m2m=100,
        ),
        _make_kite_raw(
            tradingsymbol="NIFTY2631024500PE",
            quantity=-65, product="MIS", pnl=50, m2m=50,
        ),
    ]
    # Override product for second position
    positions[1]["product"] = "MIS"

    ps = sync_positions(positions)
    assert len(ps.positions) == 2
    products = {p.product for p in ps.positions}
    assert "NRML" in products
    assert "MIS" in products


# --- 21. Unrealized PnL Calculation ---

def test_unrealized_pnl():
    """Unrealized PnL = (ltp - avg_price) * quantity."""
    raw = _make_kite_raw(
        tradingsymbol="NIFTY2631024500CE",
        quantity=65,
        average_price=195.75,
        last_price=210.50,
    )
    kp = parse_kite_position(raw)
    expected = (210.50 - 195.75) * 65
    assert abs(kp.unrealized_pnl - expected) < 0.01


def test_unrealized_pnl_short():
    """Unrealized PnL for short: (ltp - avg) * negative_qty = profit when ltp drops."""
    raw = _make_kite_raw(
        tradingsymbol="NIFTY2631024000PE",
        quantity=-65,
        average_price=80.25,
        last_price=65.00,
    )
    kp = parse_kite_position(raw)
    expected = (65.00 - 80.25) * (-65)
    assert abs(kp.unrealized_pnl - expected) < 0.01
    assert kp.unrealized_pnl > 0  # Profit on short when price drops


# --- 22. Custom Trade Group and Strategy Tag ---

def test_kite_to_trade_custom_params():
    """Custom strategy_tag and trade_group are preserved."""
    raw = _make_kite_raw(tradingsymbol="NIFTY2631024500CE", quantity=65)
    kp = parse_kite_position(raw)
    trade = kite_position_to_trade(
        kp,
        strategy_tag="iron_condor",
        trade_group="IC_NIFTY_20260310",
        rationale="Leg 1 of iron condor",
    )
    assert trade.strategy_tag == "iron_condor"
    assert trade.trade_group == "IC_NIFTY_20260310"
    assert trade.rationale == "Leg 1 of iron condor"
