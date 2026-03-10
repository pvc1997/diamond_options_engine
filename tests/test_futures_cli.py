"""Tests for futures CLI commands."""

from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from diamond_options.cli import app
from diamond_options.data.futures_ledger import FuturesPosition

runner = CliRunner()


def _mock_ledger(positions=None, cash=500000.0, margin=0.0, capital=500000.0):
    """Create a mock FuturesLedger."""
    ledger = MagicMock()
    ledger.get_positions.return_value = positions or []
    ledger.get_cash.return_value = cash
    ledger.get_margin_used.return_value = margin
    ledger.get_initial_capital.return_value = capital
    return ledger


# ── futures status ──────────────────────────────────────────────


def test_futures_status_empty():
    """futures status with no positions shows summary."""
    with patch(
        "diamond_options.data.futures_ledger.FuturesLedger",
        return_value=_mock_ledger(),
    ):
        result = runner.invoke(app, ["futures", "status"])
        assert result.exit_code == 0
        assert "Futures Portfolio" in result.output
        assert "Open Positions:   0" in result.output


def test_futures_status_with_positions():
    """futures status shows position table."""
    positions = [
        FuturesPosition(
            symbol="NIFTY", expiry="2026-03-31", lots=2, lot_size=65,
            avg_price=22500.0, strategy_tag="trend_long", trade_group="g1",
        ),
        FuturesPosition(
            symbol="RELIANCE", expiry="2026-03-31", lots=-1, lot_size=250,
            avg_price=2800.0, strategy_tag="hedge", trade_group="g2",
        ),
    ]
    with patch(
        "diamond_options.data.futures_ledger.FuturesLedger",
        return_value=_mock_ledger(positions=positions, margin=150000.0, cash=350000.0),
    ):
        result = runner.invoke(app, ["futures", "status"])
        assert result.exit_code == 0
        assert "NIFTY" in result.output
        assert "RELIANCE" in result.output
        assert "30.0%" in result.output  # margin util


def test_futures_status_margin_utilization():
    """futures status calculates margin utilization correctly."""
    with patch(
        "diamond_options.data.futures_ledger.FuturesLedger",
        return_value=_mock_ledger(margin=300000.0, cash=200000.0),
    ):
        result = runner.invoke(app, ["futures", "status"])
        assert result.exit_code == 0
        assert "60.0%" in result.output


# ── futures chain ───────────────────────────────────────────────


def test_futures_chain_no_cache():
    """futures chain shows message when no cached data."""
    with patch(
        "diamond_options.data.futures_chain.load_futures_chain_from_cache",
        return_value=None,
    ):
        result = runner.invoke(app, ["futures", "chain", "NIFTY"])
        assert result.exit_code == 1
        assert "No cached" in result.output


def test_futures_chain_invalid_symbol():
    """futures chain rejects invalid symbol."""
    result = runner.invoke(app, ["futures", "chain", "INVALID_SYMBOL"])
    assert result.exit_code == 1
    assert "not in the F&O" in result.output


def test_futures_chain_with_data():
    """futures chain displays term structure."""
    from datetime import date
    from diamond_options.data.futures_chain import FuturesQuote, FuturesChain

    near = FuturesQuote(
        symbol="NIFTY", expiry=date(2026, 3, 31), last_price=22600.0,
        spot_price=22500.0, lot_size=65, open_interest=1000000, volume=500000,
    )
    next_m = FuturesQuote(
        symbol="NIFTY", expiry=date(2026, 4, 28), last_price=22750.0,
        spot_price=22500.0, lot_size=65, open_interest=500000, volume=200000,
    )
    chain = FuturesChain(
        symbol="NIFTY", spot=22500.0, timestamp="2026-03-10T10:00:00",
        near_month=near, next_month=next_m,
    )

    with patch(
        "diamond_options.data.futures_chain.load_futures_chain_from_cache",
        return_value=chain,
    ):
        result = runner.invoke(app, ["futures", "chain", "NIFTY"])
        assert result.exit_code == 0
        assert "NIFTY Futures Term Structure" in result.output
        assert "Near" in result.output
        assert "Next" in result.output
        assert "Calendar Spread" in result.output
        assert "150.00" in result.output
        assert "Rollover" in result.output


# ── futures basis ───────────────────────────────────────────────


def test_futures_basis_basic():
    """futures basis shows analysis for given prices."""
    result = runner.invoke(
        app, ["futures", "basis", "NIFTY", "22600", "22500", "--dte", "20"]
    )
    assert result.exit_code == 0
    assert "Basis Analysis" in result.output
    assert "Spot" in result.output
    assert "Futures" in result.output
    assert "Fair Value" in result.output
    assert "Signal" in result.output


def test_futures_basis_contango():
    """futures basis detects contango (futures > spot)."""
    result = runner.invoke(
        app, ["futures", "basis", "NIFTY", "22700", "22500", "--dte", "30"]
    )
    assert result.exit_code == 0
    assert "200.00" in result.output  # basis = 200


def test_futures_basis_backwardation():
    """futures basis detects backwardation (futures < spot)."""
    result = runner.invoke(
        app, ["futures", "basis", "NIFTY", "22400", "22500", "--dte", "15"]
    )
    assert result.exit_code == 0
    assert "-100.00" in result.output  # basis = -100


# ── futures costs ───────────────────────────────────────────────


def test_futures_costs_buy():
    """futures costs calculates buy-side costs."""
    result = runner.invoke(
        app, ["futures", "costs", "22500", "--lots", "1", "--lot-size", "65"]
    )
    assert result.exit_code == 0
    assert "Brokerage" in result.output
    assert "Round-Trip" in result.output
    assert "Breakeven" in result.output


def test_futures_costs_sell():
    """futures costs shows STT on sell side."""
    result = runner.invoke(
        app,
        ["futures", "costs", "22500", "--lots", "2", "--lot-size", "65", "--action", "SELL"],
    )
    assert result.exit_code == 0
    assert "STT" in result.output
    assert "SELL" in result.output


def test_futures_costs_custom_lot_size():
    """futures costs works with custom lot size."""
    result = runner.invoke(
        app, ["futures", "costs", "2800", "--lots", "1", "--lot-size", "250"]
    )
    assert result.exit_code == 0
    assert "250" in result.output


def test_futures_costs_turnover_shown():
    """futures costs shows turnover."""
    result = runner.invoke(
        app, ["futures", "costs", "22500", "--lots", "1", "--lot-size", "65"]
    )
    assert result.exit_code == 0
    assert "Turnover" in result.output


# ── futures contracts ───────────────────────────────────────────


def test_futures_contracts_all():
    """futures contracts lists indices and stocks."""
    result = runner.invoke(app, ["futures", "contracts"])
    assert result.exit_code == 0
    assert "NIFTY" in result.output
    assert "BANKNIFTY" in result.output
    assert "Indices" in result.output
    assert "Stocks" in result.output


def test_futures_contracts_specific_index():
    """futures contracts shows details for a specific index."""
    result = runner.invoke(app, ["futures", "contracts", "NIFTY"])
    assert result.exit_code == 0
    assert "Index" in result.output
    assert "Cash" in result.output
    assert "Weekly" in result.output
    assert "65" in result.output


def test_futures_contracts_specific_stock():
    """futures contracts shows details for a specific stock."""
    result = runner.invoke(app, ["futures", "contracts", "RELIANCE"])
    assert result.exit_code == 0
    assert "Stock" in result.output
    assert "Physical delivery" in result.output
    assert "Monthly" in result.output
    assert "250" in result.output


def test_futures_contracts_invalid_symbol():
    """futures contracts for unknown symbol shows stock type with default margin."""
    result = runner.invoke(app, ["futures", "contracts", "UNKNOWN"])
    assert result.exit_code == 0
    assert "Stock" in result.output


# ── CLI structure ───────────────────────────────────────────────


def test_futures_help():
    """futures subcommand shows help."""
    result = runner.invoke(app, ["futures", "--help"])
    assert result.exit_code == 0
    assert "status" in result.output
    assert "chain" in result.output
    assert "basis" in result.output
    assert "costs" in result.output
    assert "contracts" in result.output


def test_options_commands_still_work():
    """Existing options commands are not broken."""
    result = runner.invoke(app, ["expiry"])
    assert result.exit_code == 0
    assert "Expiries" in result.output


def test_app_help_shows_futures():
    """Main app help shows futures subcommand."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "futures" in result.output
