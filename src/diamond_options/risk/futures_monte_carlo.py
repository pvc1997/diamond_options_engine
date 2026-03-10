"""Monte Carlo simulation for futures positions.

Simulates GBM price paths and computes P&L distribution for futures.
Simpler than options MC because futures have linear payoff:
  P&L = (S_T - entry) × lots × lot_size × direction

Features:
- VaR / CVaR at multiple confidence levels
- Probability of hitting stop/target
- Multi-horizon analysis (daily, weekly, monthly)
- Margin call probability estimation
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FuturesMonteCarloResult:
    """Results of a futures Monte Carlo simulation."""
    expected_pnl: float
    median_pnl: float
    std_pnl: float
    prob_profit: float  # Percentage (0-100)
    var_95: float  # Value at Risk (5th percentile)
    var_99: float
    cvar_95: float  # Conditional VaR (Expected Shortfall)
    best_case: float
    worst_case: float
    prob_stop_loss: float  # P(hit stop loss) as %
    prob_target: float  # P(hit target) as %
    prob_margin_call: float  # P(loss > margin) as %
    percentiles: dict[int, float]


def simulate_futures_position(
    entry_price: float,
    lots: int,
    lot_size: int,
    action: str,
    spot: float,
    T: float,
    sigma: float,
    r: float = 0.065,
    stop_loss: float = 0.0,
    target: float = 0.0,
    margin: float = 0.0,
    num_paths: int = 10000,
    seed: int | None = 42,
) -> FuturesMonteCarloResult:
    """Monte Carlo simulation for a futures position.

    Simulates terminal spot prices and computes P&L distribution.
    Futures P&L is linear: (S_T - entry) × qty × direction

    Args:
        entry_price: Futures entry price.
        lots: Number of lots.
        lot_size: Shares per lot.
        action: "BUY" or "SELL".
        spot: Current spot price for GBM starting point.
        T: Time horizon in years.
        sigma: Annualized volatility.
        r: Risk-free rate (drift component).
        stop_loss: Stop loss price (0 = none).
        target: Target price (0 = none).
        margin: Margin deposited (for margin call probability).
        num_paths: Number of simulation paths.
        seed: Random seed.

    Returns:
        FuturesMonteCarloResult with distribution analysis.
    """
    rng = np.random.default_rng(seed)
    direction = 1.0 if action.upper() == "BUY" else -1.0
    qty = lots * lot_size

    # Simulate terminal prices using GBM
    drift = (r - 0.5 * sigma**2) * T
    diffusion = sigma * np.sqrt(T) * rng.standard_normal(num_paths)
    terminal_prices = spot * np.exp(drift + diffusion)

    # Linear P&L
    pnls = (terminal_prices - entry_price) * qty * direction

    # Statistics
    profitable = np.sum(pnls > 0)
    var_95 = float(np.percentile(pnls, 5))
    var_99 = float(np.percentile(pnls, 1))

    # CVaR (expected shortfall)
    tail = pnls[pnls <= var_95]
    cvar_95 = float(np.mean(tail)) if len(tail) > 0 else var_95

    # Stop loss probability
    if stop_loss > 0:
        if action.upper() == "BUY":
            prob_stop = float(np.mean(terminal_prices <= stop_loss) * 100)
        else:
            prob_stop = float(np.mean(terminal_prices >= stop_loss) * 100)
    else:
        prob_stop = 0.0

    # Target probability
    if target > 0:
        if action.upper() == "BUY":
            prob_target = float(np.mean(terminal_prices >= target) * 100)
        else:
            prob_target = float(np.mean(terminal_prices <= target) * 100)
    else:
        prob_target = float(np.mean(pnls > 0) * 100)

    # Margin call probability (loss exceeds margin)
    if margin > 0:
        prob_margin_call = float(np.mean(pnls < -margin) * 100)
    else:
        prob_margin_call = 0.0

    # Percentiles
    pct_keys = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    percentiles = {p: round(float(np.percentile(pnls, p)), 2) for p in pct_keys}

    return FuturesMonteCarloResult(
        expected_pnl=round(float(np.mean(pnls)), 2),
        median_pnl=round(float(np.median(pnls)), 2),
        std_pnl=round(float(np.std(pnls)), 2),
        prob_profit=round(profitable / num_paths * 100, 1),
        var_95=round(var_95, 2),
        var_99=round(var_99, 2),
        cvar_95=round(cvar_95, 2),
        best_case=round(float(np.max(pnls)), 2),
        worst_case=round(float(np.min(pnls)), 2),
        prob_stop_loss=round(prob_stop, 1),
        prob_target=round(prob_target, 1),
        prob_margin_call=round(prob_margin_call, 1),
        percentiles=percentiles,
    )


def simulate_futures_multi_horizon(
    entry_price: float,
    lots: int,
    lot_size: int,
    action: str,
    spot: float,
    T: float,
    sigma: float,
    r: float = 0.065,
    horizons: list[float] | None = None,
    num_paths: int = 5000,
    seed: int | None = 42,
) -> list[dict]:
    """Simulate P&L at multiple time horizons.

    Args:
        entry_price: Futures entry price.
        lots: Number of lots.
        lot_size: Shares per lot.
        action: "BUY" or "SELL".
        spot: Current spot price.
        T: Maximum time horizon in years.
        sigma: Annualized volatility.
        r: Risk-free rate.
        horizons: Fractions of T to check (default: [0.25, 0.5, 0.75, 1.0]).
        num_paths: Simulation paths.
        seed: Random seed.

    Returns:
        List of dicts with P&L stats at each horizon.
    """
    if horizons is None:
        horizons = [0.25, 0.5, 0.75, 1.0]

    results = []
    for frac in horizons:
        t = T * frac
        mc = simulate_futures_position(
            entry_price, lots, lot_size, action, spot,
            t, sigma, r, num_paths=num_paths, seed=seed,
        )
        results.append({
            "time_fraction": frac,
            "days": round(t * 365),
            "expected_pnl": mc.expected_pnl,
            "prob_profit": mc.prob_profit,
            "var_95": mc.var_95,
            "cvar_95": mc.cvar_95,
            "best_case": mc.best_case,
            "worst_case": mc.worst_case,
        })

    return results


def futures_stress_test(
    entry_price: float,
    lots: int,
    lot_size: int,
    action: str,
    scenarios: list[dict] | None = None,
) -> list[dict]:
    """Run stress test scenarios on a futures position.

    Args:
        entry_price: Futures entry price.
        lots: Number of lots.
        lot_size: Shares per lot.
        action: "BUY" or "SELL".
        scenarios: Custom scenarios. Uses standard set if None.

    Returns:
        List of scenario results with P&L impact.
    """
    if scenarios is None:
        scenarios = [
            {"name": "Crash -10%", "move_pct": -10.0},
            {"name": "Sharp drop -5%", "move_pct": -5.0},
            {"name": "Down -3%", "move_pct": -3.0},
            {"name": "Down -1%", "move_pct": -1.0},
            {"name": "Unchanged", "move_pct": 0.0},
            {"name": "Up +1%", "move_pct": 1.0},
            {"name": "Up +3%", "move_pct": 3.0},
            {"name": "Rally +5%", "move_pct": 5.0},
            {"name": "Melt-up +10%", "move_pct": 10.0},
        ]

    direction = 1.0 if action.upper() == "BUY" else -1.0
    qty = lots * lot_size

    results = []
    for scenario in scenarios:
        pct = scenario["move_pct"]
        new_price = entry_price * (1 + pct / 100.0)
        pnl = (new_price - entry_price) * qty * direction

        results.append({
            "scenario": scenario["name"],
            "move_pct": pct,
            "new_price": round(new_price, 2),
            "pnl": round(pnl, 2),
            "pnl_per_lot": round(pnl / lots, 2) if lots > 0 else 0,
        })

    return results
