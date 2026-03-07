"""Options trade ledger backed by SQLite.

Tracks individual option legs, multi-leg strategies, P&L, and margin usage.
Supports paper and live trading modes with separate databases.
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
class OptionTrade:
    """A single option leg trade."""
    timestamp: str
    action: str              # BUY or SELL
    symbol: str              # Underlying (e.g., "NIFTY")
    strike: float
    option_type: str         # CE or PE
    expiry: str              # ISO date string
    lots: int                # Number of lots
    lot_size: int            # Lot size at time of trade
    price: float             # Premium per share
    total_cost: float        # Transaction costs
    strategy_tag: str        # e.g., "iron_condor", "straddle", "single"
    trade_group: str         # Groups legs of the same spread
    rationale: str


@dataclass
class Position:
    """A current option position."""
    symbol: str
    strike: float
    option_type: str         # CE or PE
    expiry: str
    lots: int                # Positive = long, negative = short
    lot_size: int
    avg_price: float         # Average premium
    strategy_tag: str
    trade_group: str

    @property
    def quantity(self) -> int:
        """Total shares = lots * lot_size."""
        return self.lots * self.lot_size

    @property
    def is_long(self) -> bool:
        return self.lots > 0

    @property
    def is_short(self) -> bool:
        return self.lots < 0

    @property
    def notional_value(self) -> float:
        """Premium * quantity (absolute)."""
        return abs(self.avg_price * self.quantity)


class OptionsLedger:
    """SQLite-backed options trade ledger."""

    def __init__(self, name: str = "default", db_path: Path | None = None):
        self.name = name
        self.db_path = db_path or get_config().ledger_path(f"options_{name}")
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
                    strike REAL NOT NULL,
                    option_type TEXT NOT NULL CHECK(option_type IN ('CE', 'PE')),
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
                    strike REAL NOT NULL,
                    option_type TEXT NOT NULL CHECK(option_type IN ('CE', 'PE')),
                    expiry TEXT NOT NULL,
                    lots INTEGER NOT NULL DEFAULT 0,
                    lot_size INTEGER NOT NULL,
                    avg_price REAL NOT NULL DEFAULT 0,
                    strategy_tag TEXT DEFAULT 'single',
                    trade_group TEXT DEFAULT '',
                    UNIQUE(symbol, strike, option_type, expiry, trade_group)
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
            row = conn.execute("SELECT value FROM state WHERE key = 'margin_used'").fetchone()
            return float(row[0]) if row else 0.0

    def set_margin_used(self, amount: float) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE state SET value = ? WHERE key = 'margin_used'", (str(amount),)
            )

    def get_initial_capital(self) -> float:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM state WHERE key = 'initial_capital'"
            ).fetchone()
            return float(row[0]) if row else get_config().risk.initial_capital

    # --- Positions ---

    def get_positions(self) -> list[Position]:
        """Return all open positions (lots != 0)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT symbol, strike, option_type, expiry, lots, lot_size, "
                "avg_price, strategy_tag, trade_group "
                "FROM positions WHERE lots != 0"
            ).fetchall()
            return [
                Position(
                    symbol=r[0], strike=r[1], option_type=r[2], expiry=r[3],
                    lots=r[4], lot_size=r[5], avg_price=r[6],
                    strategy_tag=r[7], trade_group=r[8],
                )
                for r in rows
            ]

    def get_positions_by_group(self, trade_group: str) -> list[Position]:
        """Return positions belonging to a specific trade group (spread legs)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT symbol, strike, option_type, expiry, lots, lot_size, "
                "avg_price, strategy_tag, trade_group "
                "FROM positions WHERE lots != 0 AND trade_group = ?",
                (trade_group,),
            ).fetchall()
            return [
                Position(
                    symbol=r[0], strike=r[1], option_type=r[2], expiry=r[3],
                    lots=r[4], lot_size=r[5], avg_price=r[6],
                    strategy_tag=r[7], trade_group=r[8],
                )
                for r in rows
            ]

    def get_expiring_positions(self, expiry: str) -> list[Position]:
        """Return positions expiring on a specific date."""
        return [p for p in self.get_positions() if p.expiry == expiry]

    # --- Trading ---

    def record_trade(self, trade: OptionTrade) -> None:
        """Record a trade and update positions + cash."""
        with self._write_lock():
            with self._conn() as conn:
                # Record the trade
                conn.execute(
                    """INSERT INTO trades
                       (timestamp, action, symbol, strike, option_type, expiry,
                        lots, lot_size, price, total_cost, strategy_tag, trade_group, rationale)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        trade.timestamp, trade.action, trade.symbol,
                        trade.strike, trade.option_type, trade.expiry,
                        trade.lots, trade.lot_size, trade.price,
                        trade.total_cost, trade.strategy_tag,
                        trade.trade_group, trade.rationale,
                    ),
                )

            # Update position
            self._update_position(trade)

            # Update cash
            cash = self.get_cash()
            premium = trade.price * trade.lots * trade.lot_size
            if trade.action == "BUY":
                # Buying: pay premium + costs
                cash -= premium + trade.total_cost
            else:
                # Selling: receive premium - costs
                cash += premium - trade.total_cost
            self.set_cash(cash)

    def _update_position(self, trade: OptionTrade) -> None:
        """Update or create position after a trade."""
        lots_delta = trade.lots if trade.action == "BUY" else -trade.lots

        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, lots, avg_price FROM positions "
                "WHERE symbol = ? AND strike = ? AND option_type = ? "
                "AND expiry = ? AND trade_group = ?",
                (trade.symbol, trade.strike, trade.option_type,
                 trade.expiry, trade.trade_group),
            ).fetchone()

            if row:
                pos_id, old_lots, old_avg = row
                new_lots = old_lots + lots_delta

                if new_lots == 0:
                    # Position closed
                    conn.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
                else:
                    # Update average price on same-direction trades
                    if (lots_delta > 0 and old_lots >= 0) or (lots_delta < 0 and old_lots <= 0):
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
                    "(symbol, strike, option_type, expiry, lots, lot_size, "
                    "avg_price, strategy_tag, trade_group) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        trade.symbol, trade.strike, trade.option_type,
                        trade.expiry, lots_delta, trade.lot_size,
                        trade.price, trade.strategy_tag, trade.trade_group,
                    ),
                )

    # --- Queries ---

    def get_trades(self, since: str | None = None) -> list[OptionTrade]:
        """Return trade history."""
        with self._conn() as conn:
            if since:
                rows = conn.execute(
                    "SELECT timestamp, action, symbol, strike, option_type, expiry, "
                    "lots, lot_size, price, total_cost, strategy_tag, trade_group, rationale "
                    "FROM trades WHERE timestamp >= ? ORDER BY timestamp",
                    (since,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT timestamp, action, symbol, strike, option_type, expiry, "
                    "lots, lot_size, price, total_cost, strategy_tag, trade_group, rationale "
                    "FROM trades ORDER BY timestamp"
                ).fetchall()
            return [
                OptionTrade(
                    timestamp=r[0], action=r[1], symbol=r[2], strike=r[3],
                    option_type=r[4], expiry=r[5], lots=r[6], lot_size=r[7],
                    price=r[8], total_cost=r[9], strategy_tag=r[10],
                    trade_group=r[11], rationale=r[12],
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

        Sums up all premium flows (buys negative, sells positive) minus costs
        for positions where lots = 0 (fully closed).
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
            premium = price * lots * lot_size
            if action == "SELL":
                pnl += premium - cost
            else:
                pnl -= premium + cost
        return pnl

    def count_open_positions(self) -> int:
        """Count distinct trade groups with open positions."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT trade_group) FROM positions WHERE lots != 0"
            ).fetchone()
            return row[0] if row else 0

    def expire_positions(self, expiry: str, settlement_prices: dict[str, float] | None = None) -> float:
        """Expire all positions for a given expiry date.

        For ITM options, records settlement. For OTM, expires worthless.

        Args:
            expiry: ISO date string of expiry.
            settlement_prices: {f"{symbol}_{strike}_{type}": settlement_price}

        Returns:
            Total settlement P&L.
        """
        positions = self.get_expiring_positions(expiry)
        total_settlement = 0.0

        for pos in positions:
            key = f"{pos.symbol}_{pos.strike}_{pos.option_type}"
            settle_price = (settlement_prices or {}).get(key, 0.0)

            # Record closing trade at settlement
            close_action = "SELL" if pos.is_long else "BUY"
            trade = OptionTrade(
                timestamp=f"{expiry} 15:30:00",
                action=close_action,
                symbol=pos.symbol,
                strike=pos.strike,
                option_type=pos.option_type,
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
            settlement = settle_price * abs(pos.lots) * pos.lot_size
            if pos.is_long:
                total_settlement += settlement
            else:
                total_settlement -= settlement

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
