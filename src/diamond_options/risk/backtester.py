"""Options strategy backtester.

Tests a strategy's historical performance by simulating trades
at regular intervals using historical price data.

Features:
- Strategy-agnostic: backtest any strategy defined in definitions.py
- Walk-forward: enters positions at regular intervals
- P&L tracking: tracks each trade's outcome at expiry
- Statistics: win rate, average P&L, max drawdown, Sharpe ratio
- Supports weekly and monthly entry cadence

Limitations (by design):
- Uses close-to-close prices (no intraday)
- Assumes fills at theoretical BS prices (no slippage modeled)
- Single underlying at a time
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from diamond_options.pricing.black_scholes import call_price, put_price
from diamond_options.pricing.payoff import Leg, position_payoff_at_expiry


@dataclass(frozen=True)
class BacktestTrade:
    """A single backtested trade."""
    entry_date: str
    expiry_date: str
    entry_spot: float
    expiry_spot: float
    strategy: str
    legs: list[dict]       # Leg specs
    net_premium: float     # Net premium paid/received
    pnl: float             # P&L at expiry
    pnl_pct: float         # P&L as % of margin/premium
    won: bool


@dataclass(frozen=True)
class BacktestResult:
    """Complete backtest results."""
    strategy: str
    total_trades: int
    winners: int
    losers: int
    win_rate: float                # Percentage
    avg_pnl: float                 # Average P&L per trade
    total_pnl: float
    max_win: float
    max_loss: float
    avg_win: float
    avg_loss: float
    profit_factor: float           # Gross profit / Gross loss
    max_drawdown: float            # Maximum peak-to-trough drawdown
    sharpe_ratio: float            # Annualized Sharpe
    expectancy: float              # avg_win * win_rate - avg_loss * loss_rate
    trades: list[BacktestTrade] = field(default_factory=list)


def backtest_strategy(
    strategy: str,
    prices: list[float],
    dates: list[str],
    sigma: float,
    r: float = 0.065,
    lot_size: int = 65,
    strike_step: float = 50.0,
    otm_distance: int = 2,
    entry_interval: int = 7,
    holding_period: int = 7,
) -> BacktestResult:
    """Backtest a strategy over historical prices.

    Enters a new position every `entry_interval` days and holds
    until expiry (or `holding_period` days).

    Args:
        strategy: Strategy slug (e.g., "iron_condor", "bull_put_spread").
        prices: Historical daily closing prices.
        dates: Corresponding date strings (ISO format).
        sigma: Assumed volatility for pricing (annualized).
        r: Risk-free rate.
        lot_size: Lot size.
        strike_step: Strike interval.
        otm_distance: OTM distance in strike steps.
        entry_interval: Days between entries.
        holding_period: Days held before exit.

    Returns:
        BacktestResult with full trade log and statistics.
    """
    if len(prices) < holding_period + 1:
        return BacktestResult(
            strategy=strategy, total_trades=0, winners=0, losers=0,
            win_rate=0, avg_pnl=0, total_pnl=0, max_win=0, max_loss=0,
            avg_win=0, avg_loss=0, profit_factor=0, max_drawdown=0,
            sharpe_ratio=0, expectancy=0,
        )

    trades: list[BacktestTrade] = []

    i = 0
    while i + holding_period < len(prices):
        entry_spot = prices[i]
        expiry_spot = prices[i + holding_period]
        entry_date = dates[i]
        expiry_date = dates[i + holding_period]
        T = holding_period / 365.0

        # Build legs at entry
        legs, leg_specs = _build_strategy_legs(
            strategy, entry_spot, sigma, T, r, lot_size, strike_step, otm_distance,
        )

        if not legs:
            i += entry_interval
            continue

        # Calculate P&L at expiry
        pnl = position_payoff_at_expiry(legs, expiry_spot)

        # Net premium
        net_prem = sum(
            (-leg.premium if leg.action == "BUY" else leg.premium)
            * leg.lots * leg.lot_size
            for leg in legs
        )

        # P&L as percentage of capital at risk
        risk = abs(net_prem) if abs(net_prem) > 0 else entry_spot * lot_size * 0.15
        pnl_pct = (pnl / risk * 100) if risk > 0 else 0

        trades.append(BacktestTrade(
            entry_date=entry_date,
            expiry_date=expiry_date,
            entry_spot=round(entry_spot, 2),
            expiry_spot=round(expiry_spot, 2),
            strategy=strategy,
            legs=leg_specs,
            net_premium=round(net_prem, 2),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 1),
            won=pnl > 0,
        ))

        i += entry_interval

    return _compute_statistics(strategy, trades)


def _build_strategy_legs(
    strategy: str, spot: float, sigma: float, T: float, r: float,
    lot_size: int, step: float, otm_dist: int,
) -> tuple[list[Leg], list[dict]]:
    """Build strategy legs with BS-priced premiums."""
    atm = round(spot / step) * step
    otm_up = atm + step * otm_dist
    otm_down = atm - step * otm_dist
    wing_up = atm + step * (otm_dist + 2)
    wing_down = atm - step * (otm_dist + 2)

    def cp(strike: float) -> float:
        return call_price(spot, strike, T, r, sigma).price

    def pp(strike: float) -> float:
        return put_price(spot, strike, T, r, sigma).price

    legs: list[Leg] = []
    specs: list[dict] = []

    try:
        if strategy == "iron_condor":
            legs = [
                Leg(wing_down, "PE", "BUY", pp(wing_down), 1, lot_size),
                Leg(otm_down, "PE", "SELL", pp(otm_down), 1, lot_size),
                Leg(otm_up, "CE", "SELL", cp(otm_up), 1, lot_size),
                Leg(wing_up, "CE", "BUY", cp(wing_up), 1, lot_size),
            ]
        elif strategy == "bull_put_spread":
            legs = [
                Leg(otm_down, "PE", "SELL", pp(otm_down), 1, lot_size),
                Leg(wing_down, "PE", "BUY", pp(wing_down), 1, lot_size),
            ]
        elif strategy == "bear_call_spread":
            legs = [
                Leg(otm_up, "CE", "SELL", cp(otm_up), 1, lot_size),
                Leg(wing_up, "CE", "BUY", cp(wing_up), 1, lot_size),
            ]
        elif strategy == "short_strangle":
            legs = [
                Leg(otm_up, "CE", "SELL", cp(otm_up), 1, lot_size),
                Leg(otm_down, "PE", "SELL", pp(otm_down), 1, lot_size),
            ]
        elif strategy == "short_straddle":
            legs = [
                Leg(atm, "CE", "SELL", cp(atm), 1, lot_size),
                Leg(atm, "PE", "SELL", pp(atm), 1, lot_size),
            ]
        elif strategy == "long_straddle":
            legs = [
                Leg(atm, "CE", "BUY", cp(atm), 1, lot_size),
                Leg(atm, "PE", "BUY", pp(atm), 1, lot_size),
            ]
        elif strategy == "long_call":
            legs = [Leg(atm, "CE", "BUY", cp(atm), 1, lot_size)]
        elif strategy == "long_put":
            legs = [Leg(atm, "PE", "BUY", pp(atm), 1, lot_size)]
        elif strategy == "bull_call_spread":
            legs = [
                Leg(atm, "CE", "BUY", cp(atm), 1, lot_size),
                Leg(otm_up, "CE", "SELL", cp(otm_up), 1, lot_size),
            ]
        elif strategy == "bear_put_spread":
            legs = [
                Leg(atm, "PE", "BUY", pp(atm), 1, lot_size),
                Leg(otm_down, "PE", "SELL", pp(otm_down), 1, lot_size),
            ]
        elif strategy == "iron_butterfly":
            legs = [
                Leg(otm_down, "PE", "BUY", pp(otm_down), 1, lot_size),
                Leg(atm, "PE", "SELL", pp(atm), 1, lot_size),
                Leg(atm, "CE", "SELL", cp(atm), 1, lot_size),
                Leg(otm_up, "CE", "BUY", cp(otm_up), 1, lot_size),
            ]
        else:
            return [], []

        specs = [
            {"strike": l.strike, "type": l.option_type, "action": l.action,
             "premium": round(l.premium, 2)}
            for l in legs
        ]
    except Exception:
        return [], []

    return legs, specs


def _compute_statistics(
    strategy: str,
    trades: list[BacktestTrade],
) -> BacktestResult:
    """Compute backtest statistics from trade list."""
    if not trades:
        return BacktestResult(
            strategy=strategy, total_trades=0, winners=0, losers=0,
            win_rate=0, avg_pnl=0, total_pnl=0, max_win=0, max_loss=0,
            avg_win=0, avg_loss=0, profit_factor=0, max_drawdown=0,
            sharpe_ratio=0, expectancy=0,
        )

    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    total_pnl = sum(pnls)
    avg_pnl = total_pnl / len(pnls)
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0
    win_rate = len(wins) / len(pnls) * 100

    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 1  # Avoid division by zero
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown (cumulative P&L)
    cumulative = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumulative)
    drawdown = cumulative - peak
    max_drawdown = float(np.min(drawdown)) if len(drawdown) > 0 else 0

    # Sharpe ratio (annualized, assuming weekly trades)
    if len(pnls) > 1:
        pnl_std = float(np.std(pnls))
        if pnl_std > 0:
            trades_per_year = 52  # Weekly
            sharpe = (avg_pnl / pnl_std) * math.sqrt(trades_per_year)
        else:
            sharpe = 0
    else:
        sharpe = 0

    # Expectancy
    loss_rate = 1 - win_rate / 100
    expectancy = (avg_win * win_rate / 100) - (avg_loss * loss_rate)

    return BacktestResult(
        strategy=strategy,
        total_trades=len(trades),
        winners=len(wins),
        losers=len(losses),
        win_rate=round(win_rate, 1),
        avg_pnl=round(avg_pnl, 2),
        total_pnl=round(total_pnl, 2),
        max_win=round(max(pnls), 2),
        max_loss=round(min(pnls), 2),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        profit_factor=round(profit_factor, 2),
        max_drawdown=round(max_drawdown, 2),
        sharpe_ratio=round(sharpe, 2),
        expectancy=round(expectancy, 2),
        trades=trades,
    )
