"""Futures strategy backtester.

Tests futures strategies over historical price data using walk-forward
simulation. Simpler than options backtesting — no strike selection or
premium pricing needed, just entry/exit at futures prices.

Features:
- Strategy-agnostic: long, short, calendar spread, mean reversion
- Walk-forward: enters at regular intervals
- Cost-aware: includes STT, brokerage, exchange fees
- Statistics: win rate, Sharpe, drawdown, profit factor
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from diamond_options.data.costs import futures_pnl


@dataclass(frozen=True)
class FuturesBacktestTrade:
    """A single backtested futures trade."""
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    action: str  # "BUY" or "SELL"
    lots: int
    lot_size: int
    gross_pnl: float
    net_pnl: float  # After costs
    costs: float
    pnl_pct: float  # As % of margin
    won: bool


@dataclass(frozen=True)
class FuturesBacktestResult:
    """Complete futures backtest results."""
    strategy: str
    total_trades: int
    winners: int
    losers: int
    win_rate: float  # Percentage
    avg_pnl: float
    total_pnl: float
    total_costs: float
    max_win: float
    max_loss: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    expectancy: float
    trades: list[FuturesBacktestTrade] = field(default_factory=list)


def backtest_futures_strategy(
    strategy: str,
    prices: list[float],
    dates: list[str],
    lot_size: int = 65,
    lots: int = 1,
    entry_interval: int = 7,
    holding_period: int = 7,
    stop_pct: float = 2.0,
    target_pct: float = 3.0,
    use_stops: bool = True,
) -> FuturesBacktestResult:
    """Backtest a futures strategy over historical prices.

    Supported strategies:
    - "long_futures": Buy and hold for holding_period
    - "short_futures": Short and hold
    - "mean_reversion": Buy on dip, sell on rally (±1σ entry)
    - "momentum": Buy on breakout above recent high, sell below low
    - "calendar_spread": Simulated near/next spread (uses price + premium proxy)

    Args:
        strategy: Strategy slug.
        prices: Historical daily closing prices.
        dates: Corresponding date strings (ISO format).
        lot_size: Shares per lot.
        lots: Lots per trade.
        entry_interval: Days between entries.
        holding_period: Days held before exit.
        stop_pct: Stop loss as % move (used if use_stops=True).
        target_pct: Target as % move (used if use_stops=True).
        use_stops: Whether to use stop/target exits.

    Returns:
        FuturesBacktestResult with full trade log and statistics.
    """
    if len(prices) < holding_period + 1:
        return _empty_result(strategy)

    trades: list[FuturesBacktestTrade] = []

    i = 0
    while i + holding_period < len(prices):
        entry_price = prices[i]
        entry_date = dates[i]

        # Determine action based on strategy
        action = _determine_action(strategy, prices, i)
        if action is None:
            i += entry_interval
            continue

        # Find exit (by holding period, stop, or target)
        exit_idx, exit_price = _find_exit(
            prices, i, holding_period, action, entry_price,
            stop_pct if use_stops else 0, target_pct if use_stops else 0,
        )
        exit_date = dates[exit_idx]

        # Calculate P&L using cost model
        pnl_result = futures_pnl(
            entry_price, exit_price, lots, lot_size, action,
        )

        margin = entry_price * lots * lot_size * 0.12  # ~12% margin estimate

        trades.append(FuturesBacktestTrade(
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=round(entry_price, 2),
            exit_price=round(exit_price, 2),
            action=action,
            lots=lots,
            lot_size=lot_size,
            gross_pnl=round(pnl_result["gross_pnl"], 2),
            net_pnl=round(pnl_result["net_pnl"], 2),
            costs=round(pnl_result["total_costs"], 2),
            pnl_pct=round(pnl_result["net_pnl"] / margin * 100, 1) if margin > 0 else 0,
            won=pnl_result["net_pnl"] > 0,
        ))

        i += entry_interval

    return _compute_futures_statistics(strategy, trades)


def _determine_action(
    strategy: str,
    prices: list[float],
    idx: int,
) -> str | None:
    """Determine trade direction based on strategy."""
    if strategy == "long_futures":
        return "BUY"
    elif strategy == "short_futures":
        return "SELL"
    elif strategy == "mean_reversion":
        # Buy when price is below 20-day mean, sell when above
        if idx < 20:
            return None
        window = prices[idx - 20:idx]
        mean = sum(window) / len(window)
        std = (sum((p - mean) ** 2 for p in window) / len(window)) ** 0.5
        if std == 0:
            return None
        z = (prices[idx] - mean) / std
        if z < -1.0:
            return "BUY"  # Oversold
        elif z > 1.0:
            return "SELL"  # Overbought
        return None
    elif strategy == "momentum":
        # Buy on 10-day high, sell on 10-day low
        if idx < 10:
            return None
        window = prices[idx - 10:idx]
        if prices[idx] > max(window):
            return "BUY"
        elif prices[idx] < min(window):
            return "SELL"
        return None
    elif strategy == "calendar_spread":
        # Simplified: always BUY (long near, short far)
        return "BUY"
    else:
        return "BUY"  # Default long


def _find_exit(
    prices: list[float],
    entry_idx: int,
    holding_period: int,
    action: str,
    entry_price: float,
    stop_pct: float,
    target_pct: float,
) -> tuple[int, float]:
    """Find exit point (stop, target, or holding period).

    Returns (exit_index, exit_price).
    """
    direction = 1.0 if action == "BUY" else -1.0
    max_idx = min(entry_idx + holding_period, len(prices) - 1)

    for j in range(entry_idx + 1, max_idx + 1):
        move_pct = (prices[j] - entry_price) / entry_price * 100 * direction

        # Check stop
        if stop_pct > 0 and move_pct < -stop_pct:
            return j, prices[j]

        # Check target
        if target_pct > 0 and move_pct > target_pct:
            return j, prices[j]

    # Exit at holding period
    return max_idx, prices[max_idx]


def _compute_futures_statistics(
    strategy: str,
    trades: list[FuturesBacktestTrade],
) -> FuturesBacktestResult:
    """Compute backtest statistics from trade list."""
    if not trades:
        return _empty_result(strategy)

    pnls = [t.net_pnl for t in trades]
    costs = [t.costs for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_pnl = sum(pnls)
    total_costs = sum(costs)
    avg_pnl = total_pnl / len(pnls)
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0
    win_rate = len(wins) / len(pnls) * 100

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown
    cumulative = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumulative)
    drawdown = cumulative - peak
    max_drawdown = float(np.min(drawdown)) if len(drawdown) > 0 else 0

    # Sharpe ratio (annualized)
    if len(pnls) > 1:
        pnl_std = float(np.std(pnls))
        if pnl_std > 0:
            trades_per_year = 252 / max(1, 7)  # ~36 trades/year at weekly
            sharpe = (avg_pnl / pnl_std) * math.sqrt(trades_per_year)
        else:
            sharpe = 0
    else:
        sharpe = 0

    # Expectancy
    loss_rate = 1 - win_rate / 100
    expectancy = (avg_win * win_rate / 100) - (avg_loss * loss_rate)

    return FuturesBacktestResult(
        strategy=strategy,
        total_trades=len(trades),
        winners=len(wins),
        losers=len(losses),
        win_rate=round(win_rate, 1),
        avg_pnl=round(avg_pnl, 2),
        total_pnl=round(total_pnl, 2),
        total_costs=round(total_costs, 2),
        max_win=round(max(pnls), 2) if pnls else 0,
        max_loss=round(min(pnls), 2) if pnls else 0,
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        profit_factor=round(profit_factor, 2),
        max_drawdown=round(max_drawdown, 2),
        sharpe_ratio=round(sharpe, 2),
        expectancy=round(expectancy, 2),
        trades=trades,
    )


def _empty_result(strategy: str) -> FuturesBacktestResult:
    """Return empty result for insufficient data."""
    return FuturesBacktestResult(
        strategy=strategy, total_trades=0, winners=0, losers=0,
        win_rate=0, avg_pnl=0, total_pnl=0, total_costs=0,
        max_win=0, max_loss=0, avg_win=0, avg_loss=0,
        profit_factor=0, max_drawdown=0, sharpe_ratio=0, expectancy=0,
    )
