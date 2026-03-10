"""Futures trade ledger backed by SQLite.

Tracks futures trades, positions, P&L, and margin usage.
Supports paper and live trading modes with separate databases.
Same patterns as OptionsLedger: WAL mode, file locking, dataclass records.
"""

from __future__ import annotations

import fcntl
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from diamond_options.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class FuturesTrade:
    """A single futures trade record."""

    timestamp: str
    action: str  # BUY or SELL
    symbol: str  # Underlying (e.g., "NIFTY", "RELIANCE")
    expiry: str  # ISO date string
    lots: int  # Number of lots
    lot_size: int  # Lot size at time of trade
    price: float  # Price per unit (not per lot)
    total_cost: float  # Transaction costs
    strategy_tag: str  # e.g., "trend_long", "calendar_spread", "hedge"
    trade_group: str  # Groups legs of the same spread
    rationale: str

    @property
    def turnover(self) -> float:
        """Total trade value = price * lots * lot_size."""
        return self.price * self.lots * self.lot_size

    @property
    def quantity(self) -> int:
        """Total units = lots * lot_size."""
        return self.lots * self.lot_size


@dataclass
class FuturesPosition:
    """A current futures position."""

    symbol: str
    expiry: str  # ISO date string
    lots: int  # Positive = long, negative = short
    lot_size: int
    avg_price: float
    strategy_tag: str
    trade_group: str

    @property
    def quantity(self) -> int:
        """Total units = lots * lot_size."""
        return self.lots * self.lot_size

    @property
    def is_long(self) -> bool:
        return self.lots > 0

    @property
    def is_short(self) -> bool:
        return self.lots < 0

    @property
    def notional_value(self) -> float:
        """Notional exposure = avg_price * |quantity|."""
        return abs(self.avg_price * self.quantity)

    def unrealized_pnl(self, current_price: float) -> float:
        """P&L at a given current price.

        Long: (current - avg) * quantity
        Short: (avg - current) * |quantity|
        """
        return (current_price - self.avg_price) * self.quantity

    def margin_estimate(self, margin_pct: float = 0.15) -> float:
        """Rough margin estimate as % of notional.

        Args:
            margin_pct: SPAN margin percentage (default 15% for stocks).

        Returns:
            Estimated margin requirement in ₹.
        """
        return self.notional_value * margin_pct


class FuturesLedger:
    """SQLite-backed futures trade ledger."""

    def __init__(self, name: str = "default", db_path: Path | None = None):
        self.name = name
        self.db_path = db_path or get_config().ledger_path(f"futures_{name}")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL')),
                    symbol TEXT NOT NULL,
                    expiry TEXT NOT NULL,
                    lots INTEGER NOT NULL,
                    lot_size INTEGER NOT NULL,
                    price REAL NOT NULL,
                    total_cost REAL NOT NULL DEFAULT 0,
                    strategy_tag TEXT DEFAULT 'single',
                    trade_group TEXT DEFAULT '',
                    rationale TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    expiry TEXT NOT NULL,
                    lots INTEGER NOT NULL DEFAULT 0,
                    lot_size INTEGER NOT NULL,
                    avg_price REAL NOT NULL DEFAULT 0,
                    strategy_tag TEXT DEFAULT 'single',
                    trade_group TEXT DEFAULT '',
                    UNIQUE(symbol, expiry, trade_group)
                );

                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            # Initialize cash if not present
            cur = conn.execute("SELECT value FROM state WHERE key = 'cash'")
            if cur.fetchone() is None:
                capital = get_config().risk.initial_capital
                conn.execute(
                    "INSERT INTO state (key, value) VALUES ('cash', ?)",
                    (str(capital),),
                )
                conn.execute(
                    "INSERT INTO state (key, value) VALUES ('initial_capital', ?)",
                    (str(capital),),
                )
                conn.execute(
                    "INSERT INTO state (key, value) VALUES ('margin_used', '0')",
                )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    @contextmanager
    def _write_lock(self, timeout: float = 10.0):
        """Acquire an exclusive file lock for write operations."""
        lock_path = Path(f"{self.db_path}.lock")
        lock_file = open(lock_path, "w")
        deadline = time.monotonic() + timeout
        try:
            while True:
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except (IOError, OSError):
                    if time.monotonic() >= deadline:
                        lock_file.close()
                        raise TimeoutError(
                            f"Could not acquire ledger write lock on {self.db_path} "
                            f"within {timeout}s"
                        )
                    time.sleep(0.05)
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()

    # --- State ---

    def get_cash(self) -> float:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM state WHERE key = 'cash'").fetchone()
            return float(row[0]) if row else 0.0

    def set_cash(self, amount: float) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE state SET value = ? WHERE key = 'cash'", (str(amount),))

    def get_margin_used(self) -> float:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM state WHERE key = 'margin_used'"
            ).fetchone()
            return float(row[0]) if row else 0.0

    def set_margin_used(self, amount: float) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE state SET value = ? WHERE key = 'margin_used'",
                (str(amount),),
            )

    def get_initial_capital(self) -> float:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM state WHERE key = 'initial_capital'"
            ).fetchone()
            return float(row[0]) if row else get_config().risk.initial_capital

    # --- Positions ---

    def get_positions(self) -> list[FuturesPosition]:
        """Return all open positions (lots != 0)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT symbol, expiry, lots, lot_size, "
                "avg_price, strategy_tag, trade_group "
                "FROM positions WHERE lots != 0"
            ).fetchall()
            return [
                FuturesPosition(
                    symbol=r[0],
                    expiry=r[1],
                    lots=r[2],
                    lot_size=r[3],
                    avg_price=r[4],
                    strategy_tag=r[5],
                    trade_group=r[6],
                )
                for r in rows
            ]

    def get_positions_by_symbol(self, symbol: str) -> list[FuturesPosition]:
        """Return open positions for a specific symbol."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT symbol, expiry, lots, lot_size, "
                "avg_price, strategy_tag, trade_group "
                "FROM positions WHERE lots != 0 AND symbol = ?",
                (symbol,),
            ).fetchall()
            return [
                FuturesPosition(
                    symbol=r[0],
                    expiry=r[1],
                    lots=r[2],
                    lot_size=r[3],
                    avg_price=r[4],
                    strategy_tag=r[5],
                    trade_group=r[6],
                )
                for r in rows
            ]

    def get_positions_by_group(self, trade_group: str) -> list[FuturesPosition]:
        """Return positions belonging to a specific trade group (spread legs)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT symbol, expiry, lots, lot_size, "
                "avg_price, strategy_tag, trade_group "
                "FROM positions WHERE lots != 0 AND trade_group = ?",
                (trade_group,),
            ).fetchall()
            return [
                FuturesPosition(
                    symbol=r[0],
                    expiry=r[1],
                    lots=r[2],
                    lot_size=r[3],
                    avg_price=r[4],
                    strategy_tag=r[5],
                    trade_group=r[6],
                )
                for r in rows
            ]

    def get_expiring_positions(self, expiry: str) -> list[FuturesPosition]:
        """Return positions expiring on a specific date."""
        return [p for p in self.get_positions() if p.expiry == expiry]

    # --- Trading ---

    def record_trade(self, trade: FuturesTrade) -> None:
        """Record a trade and update positions + cash.

        For futures, cash impact is only the transaction costs (not the notional).
        Margin is tracked separately.
        """
        with self._write_lock():
            with self._conn() as conn:
                conn.execute(
                    """INSERT INTO trades
                       (timestamp, action, symbol, expiry,
                        lots, lot_size, price, total_cost,
                        strategy_tag, trade_group, rationale)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        trade.timestamp,
                        trade.action,
                        trade.symbol,
                        trade.expiry,
                        trade.lots,
                        trade.lot_size,
                        trade.price,
                        trade.total_cost,
                        trade.strategy_tag,
                        trade.trade_group,
                        trade.rationale,
                    ),
                )

            # Update position
            self._update_position(trade)

            # Update cash: only deduct transaction costs for futures
            # (margin is separate from cash in futures trading)
            cash = self.get_cash()
            cash -= trade.total_cost
            self.set_cash(cash)

    def _update_position(self, trade: FuturesTrade) -> None:
        """Update or create position after a trade."""
        lots_delta = trade.lots if trade.action == "BUY" else -trade.lots

        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, lots, avg_price FROM positions "
                "WHERE symbol = ? AND expiry = ? AND trade_group = ?",
                (trade.symbol, trade.expiry, trade.trade_group),
            ).fetchone()

            if row:
                pos_id, old_lots, old_avg = row
                new_lots = old_lots + lots_delta

                if new_lots == 0:
                    # Position closed — record realized P&L
                    conn.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
                else:
                    # Update average price on same-direction trades
                    if (lots_delta > 0 and old_lots >= 0) or (
                        lots_delta < 0 and old_lots <= 0
                    ):
                        # Adding to position
                        total_old = abs(old_lots) * old_avg
                        total_new = abs(lots_delta) * trade.price
                        new_avg = (total_old + total_new) / abs(new_lots)
                    else:
                        new_avg = old_avg  # Closing doesn't change avg

                    conn.execute(
                        "UPDATE positions SET lots = ?, avg_price = ? WHERE id = ?",
                        (new_lots, new_avg, pos_id),
                    )
            else:
                # New position
                conn.execute(
                    "INSERT INTO positions "
                    "(symbol, expiry, lots, lot_size, "
                    "avg_price, strategy_tag, trade_group) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        trade.symbol,
                        trade.expiry,
                        lots_delta,
                        trade.lot_size,
                        trade.price,
                        trade.strategy_tag,
                        trade.trade_group,
                    ),
                )

    # --- Queries ---

    def get_trades(self, since: str | None = None) -> list[FuturesTrade]:
        """Return trade history."""
        with self._conn() as conn:
            if since:
                rows = conn.execute(
                    "SELECT timestamp, action, symbol, expiry, "
                    "lots, lot_size, price, total_cost, "
                    "strategy_tag, trade_group, rationale "
                    "FROM trades WHERE timestamp >= ? ORDER BY timestamp",
                    (since,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT timestamp, action, symbol, expiry, "
                    "lots, lot_size, price, total_cost, "
                    "strategy_tag, trade_group, rationale "
                    "FROM trades ORDER BY timestamp"
                ).fetchall()
            return [
                FuturesTrade(
                    timestamp=r[0],
                    action=r[1],
                    symbol=r[2],
                    expiry=r[3],
                    lots=r[4],
                    lot_size=r[5],
                    price=r[6],
                    total_cost=r[7],
                    strategy_tag=r[8],
                    trade_group=r[9],
                    rationale=r[10],
                )
                for r in rows
            ]

    def get_trades_by_symbol(self, symbol: str) -> list[FuturesTrade]:
        """Return trade history for a specific symbol."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT timestamp, action, symbol, expiry, "
                "lots, lot_size, price, total_cost, "
                "strategy_tag, trade_group, rationale "
                "FROM trades WHERE symbol = ? ORDER BY timestamp",
                (symbol,),
            ).fetchall()
            return [
                FuturesTrade(
                    timestamp=r[0],
                    action=r[1],
                    symbol=r[2],
                    expiry=r[3],
                    lots=r[4],
                    lot_size=r[5],
                    price=r[6],
                    total_cost=r[7],
                    strategy_tag=r[8],
                    trade_group=r[9],
                    rationale=r[10],
                )
                for r in rows
            ]

    def get_total_fees(self) -> float:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(total_cost), 0) FROM trades"
            ).fetchone()
            return row[0]

    def get_realized_pnl(self, trade_group: str | None = None) -> float:
        """Calculate realized P&L for closed positions.

        For futures, P&L = (sell_price - buy_price) * lots * lot_size - costs.
        """
        with self._conn() as conn:
            if trade_group:
                rows = conn.execute(
                    "SELECT action, lots, lot_size, price, total_cost "
                    "FROM trades WHERE trade_group = ? ORDER BY timestamp",
                    (trade_group,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT action, lots, lot_size, price, total_cost "
                    "FROM trades ORDER BY timestamp"
                ).fetchall()

        pnl = 0.0
        for action, lots, lot_size, price, cost in rows:
            value = price * lots * lot_size
            if action == "SELL":
                pnl += value - cost
            else:
                pnl -= value + cost
        return pnl

    def count_open_positions(self) -> int:
        """Count distinct trade groups with open positions."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT trade_group) FROM positions WHERE lots != 0"
            ).fetchone()
            return row[0] if row else 0

    def expire_positions(
        self,
        expiry: str,
        settlement_prices: dict[str, float] | None = None,
    ) -> float:
        """Expire all positions for a given expiry date.

        Futures settle at the settlement price (typically closing spot).

        Args:
            expiry: ISO date string of expiry.
            settlement_prices: {symbol: settlement_price}

        Returns:
            Total settlement P&L.
        """
        positions = self.get_expiring_positions(expiry)
        total_settlement = 0.0

        for pos in positions:
            settle_price = (settlement_prices or {}).get(pos.symbol, 0.0)

            # Record closing trade at settlement
            close_action = "SELL" if pos.is_long else "BUY"
            trade = FuturesTrade(
                timestamp=f"{expiry} 15:30:00",
                action=close_action,
                symbol=pos.symbol,
                expiry=expiry,
                lots=abs(pos.lots),
                lot_size=pos.lot_size,
                price=settle_price,
                total_cost=0.0,  # No costs on expiry settlement
                strategy_tag=pos.strategy_tag,
                trade_group=pos.trade_group,
                rationale=f"Expiry settlement at {settle_price}",
            )
            self.record_trade(trade)

            # P&L = (settle - avg) * quantity for long, (avg - settle) * |qty| for short
            pnl = (settle_price - pos.avg_price) * pos.quantity
            total_settlement += pnl

        return total_settlement

    def reset(self, initial_capital: float | None = None) -> None:
        """Reset ledger to initial state."""
        capital = initial_capital or get_config().risk.initial_capital
        with self._conn() as conn:
            conn.executescript(f"""
                DELETE FROM trades;
                DELETE FROM positions;
                UPDATE state SET value = '{capital}' WHERE key = 'cash';
                UPDATE state SET value = '{capital}' WHERE key = 'initial_capital';
                UPDATE state SET value = '0' WHERE key = 'margin_used';
            """)
