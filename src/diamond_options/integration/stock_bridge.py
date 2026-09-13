"""Bridge to diamond_stock_engine — reads equity holdings for options overlay.

Provides a clean interface to the stock engine's ledger without importing it.
Reads directly from SQLite to avoid dependency coupling.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StockHolding:
    """A single equity holding from the stock engine."""
    ticker: str          # Yahoo Finance ticker (e.g., RELIANCE.NS)
    fno_symbol: str      # NSE F&O symbol (e.g., RELIANCE)
    shares: int
    avg_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight_pct: float    # % of portfolio


@dataclass(frozen=True)
class StockPortfolio:
    """Snapshot of equity portfolio from the stock engine."""
    strategy: str
    holdings: list[StockHolding]
    total_value: float
    cash: float
    nav: float
    num_stocks: int
    fno_eligible: list[StockHolding]  # Holdings that are F&O eligible
    fno_eligible_value: float
    fno_eligible_pct: float


def _ticker_to_fno_symbol(ticker: str) -> str:
    """Convert Yahoo Finance ticker to NSE F&O symbol.

    RELIANCE.NS -> RELIANCE
    TCS.NS -> TCS
    """
    return ticker.replace(".NS", "").replace(".BO", "")


def _find_stock_engine_db(strategy: str) -> Path | None:
    """Locate the stock engine's ledger database.

    Checks standard locations used by diamond_stock_engine.
    """
    home = Path.home()
    rel = Path("data") / "ledgers" / f"{strategy}.db"
    candidates: list[Path] = []
    # Explicit override via environment variable (path to the stock engine repo root)
    env_root = os.environ.get("DIAMOND_STOCK_ENGINE_DIR")
    if env_root:
        candidates.append(Path(env_root).expanduser() / rel)
    candidates += [
        # Sibling checkout next to this repo (default layout)
        Path(__file__).resolve().parents[3].parent / "diamond_stock_engine" / rel,
        Path.cwd().parent / "diamond_stock_engine" / rel,
        home / ".diamond" / "ledgers" / f"{strategy}.db",
        home / ".diamond_stock" / "ledgers" / f"{strategy}.db",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def get_stock_holdings(
    strategy: str = "gods_plan",
    current_prices: dict[str, float] | None = None,
    db_path: Path | str | None = None,
) -> StockPortfolio:
    """Read equity holdings from diamond_stock_engine's ledger.

    Args:
        strategy: Stock engine strategy name (default: gods_plan).
        current_prices: {ticker: price} for current values. If None, uses avg_price.
        db_path: Explicit path to the .db file (overrides auto-detection).

    Returns:
        StockPortfolio with all holdings and F&O eligibility.
    """
    from diamond_options.data.universe import is_fno_stock, get_lot_size

    if db_path:
        path = Path(db_path)
    else:
        path = _find_stock_engine_db(strategy)

    if path is None or not path.exists():
        return StockPortfolio(
            strategy=strategy, holdings=[], total_value=0, cash=0,
            nav=0, num_stocks=0, fno_eligible=[], fno_eligible_value=0,
            fno_eligible_pct=0,
        )

    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT ticker, shares, avg_price FROM holdings WHERE shares > 0"
        ).fetchall()

        cash_row = conn.execute(
            "SELECT value FROM state WHERE key = 'cash'"
        ).fetchone()
        cash = float(cash_row[0]) if cash_row else 0.0
    finally:
        conn.close()

    prices = current_prices or {}
    holdings = []
    total_equity_value = 0.0

    for ticker, shares, avg_price in rows:
        price = prices.get(ticker, avg_price)
        market_value = shares * price
        total_equity_value += market_value

        pnl = (price - avg_price) * shares
        pnl_pct = ((price - avg_price) / avg_price * 100) if avg_price > 0 else 0.0

        holdings.append(StockHolding(
            ticker=ticker,
            fno_symbol=_ticker_to_fno_symbol(ticker),
            shares=shares,
            avg_price=avg_price,
            current_price=price,
            market_value=market_value,
            unrealized_pnl=round(pnl, 2),
            unrealized_pnl_pct=round(pnl_pct, 2),
            weight_pct=0,  # Filled below
        ))

    nav = cash + total_equity_value

    # Calculate weights and identify F&O eligible
    final_holdings = []
    fno_eligible = []

    for h in holdings:
        weight = (h.market_value / nav * 100) if nav > 0 else 0
        holding = StockHolding(
            ticker=h.ticker,
            fno_symbol=h.fno_symbol,
            shares=h.shares,
            avg_price=h.avg_price,
            current_price=h.current_price,
            market_value=h.market_value,
            unrealized_pnl=h.unrealized_pnl,
            unrealized_pnl_pct=h.unrealized_pnl_pct,
            weight_pct=round(weight, 2),
        )
        final_holdings.append(holding)

        if is_fno_stock(holding.fno_symbol):
            fno_eligible.append(holding)

    fno_value = sum(h.market_value for h in fno_eligible)

    return StockPortfolio(
        strategy=strategy,
        holdings=final_holdings,
        total_value=round(total_equity_value, 2),
        cash=round(cash, 2),
        nav=round(nav, 2),
        num_stocks=len(final_holdings),
        fno_eligible=fno_eligible,
        fno_eligible_value=round(fno_value, 2),
        fno_eligible_pct=round(fno_value / nav * 100, 2) if nav > 0 else 0,
    )
