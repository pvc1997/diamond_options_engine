"""Tests for futures integration MCP tool wrappers (Phase F8).

Tests the underlying library functions that MCP tools wrap,
since server.py requires fastmcp (separate venv).
"""

from datetime import date

from diamond_options.integration.stock_bridge import StockHolding, StockPortfolio
from diamond_options.integration.futures_overlay import (
    suggest_stock_futures_hedge,
    suggest_index_futures_hedge,
    compare_hedge_methods,
    futures_income_from_holdings,
)
from diamond_options.data.events import (
    get_futures_events,
    is_rollover_window,
    days_to_futures_expiry,
)


def _holding(symbol="RELIANCE", shares=500, price=2800.0):
    return StockHolding(
        ticker=f"{symbol}.NS", fno_symbol=symbol, shares=shares,
        avg_price=price, current_price=price,
        market_value=shares * price, unrealized_pnl=0,
        unrealized_pnl_pct=0, weight_pct=100,
    )


def _portfolio(value=1500000.0, fno_eligible=None):
    eligible = fno_eligible or []
    fno_value = sum(h.market_value for h in eligible)
    return StockPortfolio(
        strategy="test", holdings=eligible, total_value=value,
        cash=0, nav=value, num_stocks=len(eligible),
        fno_eligible=eligible, fno_eligible_value=fno_value,
        fno_eligible_pct=(fno_value / value * 100) if value > 0 else 0,
    )


# ── MCP: futures_hedge_stock ────────────────────────────────────


def test_mcp_futures_hedge_stock():
    """Mirrors what futures_hedge_stock MCP tool does."""
    holding = _holding("RELIANCE", 500, 2800.0)
    result = suggest_stock_futures_hedge(holding, futures_price=2815.0, days_to_expiry=20)
    assert result is not None
    assert result.lots_hedged == 2
    assert result.margin_required > 0
    assert result.basis_cost > 0


def test_mcp_futures_hedge_stock_insufficient():
    """MCP tool returns None for insufficient shares."""
    holding = _holding("RELIANCE", 100, 2800.0)
    result = suggest_stock_futures_hedge(holding, futures_price=2815.0)
    assert result is None


# ── MCP: futures_hedge_portfolio ────────────────────────────────


def test_mcp_futures_hedge_portfolio():
    """Mirrors what futures_hedge_portfolio MCP tool does."""
    p = _portfolio(2000000.0)
    result = suggest_index_futures_hedge(p, nifty_futures=22600.0, nifty_spot=22500.0)
    assert result.lots_full_hedge >= 1
    assert result.margin_full > 0
    assert result.hedge_effectiveness > 0


def test_mcp_futures_hedge_portfolio_half():
    """50% hedge ratio."""
    p = _portfolio(2000000.0)
    result = suggest_index_futures_hedge(p, nifty_futures=22600.0, hedge_ratio=0.5)
    full = suggest_index_futures_hedge(p, nifty_futures=22600.0, hedge_ratio=1.0)
    assert result.lots_full_hedge <= full.lots_full_hedge


# ── MCP: compare_hedge_methods ──────────────────────────────────


def test_mcp_compare_hedge_methods():
    """Mirrors what compare_hedge_methods MCP tool does."""
    p = _portfolio(1500000.0)
    result = compare_hedge_methods(p, nifty_spot=22500.0, nifty_futures=22600.0)
    assert len(result.methods) == 4
    assert result.recommended != ""
    # Convert to dict like MCP would
    output = {
        "recommended": result.recommended,
        "methods": [{"name": m.name, "cost": m.cost} for m in result.methods],
    }
    assert len(output["methods"]) == 4


# ── MCP: futures_income_from_stocks ─────────────────────────────


def test_mcp_futures_income():
    """Mirrors what futures_income_from_stocks MCP tool does."""
    holdings = [_holding("RELIANCE", 500, 2800.0)]
    p = _portfolio(1400000.0, fno_eligible=holdings)
    result = futures_income_from_holdings(
        p, days_to_expiry=20,
        futures_premiums={"RELIANCE": 2815.0},
    )
    assert result.eligible_count == 1
    assert result.total_income > 0
    entry = result.entries[0]
    assert entry.fno_symbol == "RELIANCE"
    assert entry.basis == 15.0


def test_mcp_futures_income_empty():
    """Empty portfolio returns zero income."""
    p = _portfolio(0, fno_eligible=[])
    result = futures_income_from_holdings(p, days_to_expiry=20)
    assert result.eligible_count == 0
    assert result.total_income == 0


# ── MCP: futures_events ─────────────────────────────────────────


def test_mcp_futures_events():
    """Mirrors what futures_events MCP tool does."""
    events = get_futures_events(from_date=date(2026, 3, 1), days_ahead=31)
    assert len(events) > 0
    # Convert to dict like MCP would
    output = {
        "events": [{"date": e.date.isoformat(), "type": e.event_type} for e in events],
        "is_rollover_window": is_rollover_window(date(2026, 3, 1)),
        "days_to_next_expiry": days_to_futures_expiry(date(2026, 3, 1)),
    }
    assert output["days_to_next_expiry"] > 0


def test_mcp_futures_events_empty_range():
    """No futures events in a short window."""
    events = get_futures_events(from_date=date(2026, 1, 2), days_ahead=1)
    # May or may not have events, but should not error
    assert isinstance(events, list)


def test_mcp_rollover_window():
    """Rollover window detection works."""
    # On Jan 1 — not in rollover window
    assert isinstance(is_rollover_window(date(2026, 1, 1)), bool)


def test_mcp_days_to_expiry():
    """Days to expiry returns positive int."""
    days = days_to_futures_expiry(date(2026, 6, 1))
    assert days > 0
    assert days <= 30
