"""Portfolio-level Monte Carlo simulation.

Simulates multiple GBM price paths to estimate portfolio-level metrics:
- Value at Risk (VaR) at various confidence levels
- Conditional VaR (Expected Shortfall)
- Probability of hitting stop-loss or target
- Distribution of outcomes at expiry

Uses vectorized numpy for performance (~10K paths in <1 second).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from diamond_options.pricing.payoff import Leg, position_payoff_at_expiry


@dataclass(frozen=True)
class MonteCarloResult:
    """Results of a Monte Carlo simulation."""
    expected_pnl: float
    median_pnl: float
    std_pnl: float
    prob_profit: float             # Percentage (0-100)
    var_95: float                  # Value at Risk (5th percentile)
    var_99: float                  # VaR at 99%
    cvar_95: float                 # Conditional VaR (expected shortfall)
    best_case: float               # Maximum P&L
    worst_case: float              # Minimum P&L
    prob_max_loss: float           # P(P&L < 90% of max loss)
    prob_target: float             # P(P&L > target) if target specified
    percentiles: dict[int, float]  # P&L at key percentiles


def simulate_position(
    legs: list[Leg],
    spot: float,
    T: float,
    r: float,
    sigma: float,
    num_paths: int = 10000,
    target_pnl: float = 0.0,
    seed: int | None = 42,
) -> MonteCarloResult:
    """Monte Carlo simulation for a multi-leg option position.

    Generates terminal prices using GBM and computes payoff distribution.

    S_T = S_0 * exp((r - σ²/2)*T + σ*√T*Z), Z ~ N(0,1)

    Args:
        legs: Option legs.
        spot: Current spot price.
        T: Time to expiry in years.
        r: Risk-free rate.
        sigma: Volatility (annualized).
        num_paths: Number of simulation paths.
        target_pnl: Target P&L for probability calculation.
        seed: Random seed for reproducibility.

    Returns:
        MonteCarloResult with full distribution analysis.
    """
    rng = np.random.default_rng(seed)

    # Simulate terminal prices
    drift = (r - 0.5 * sigma ** 2) * T
    diffusion = sigma * np.sqrt(T) * rng.standard_normal(num_paths)
    terminal_prices = spot * np.exp(drift + diffusion)

    # Compute payoffs
    pnls = np.array([
        position_payoff_at_expiry(legs, float(p))
        for p in terminal_prices
    ])

    # Statistics
    profitable = np.sum(pnls > 0)
    var_95 = float(np.percentile(pnls, 5))
    var_99 = float(np.percentile(pnls, 1))

    # Conditional VaR (Expected Shortfall): mean of losses beyond VaR
    tail = pnls[pnls <= var_95]
    cvar_95 = float(np.mean(tail)) if len(tail) > 0 else var_95

    # Max loss probability (within 90% of worst case)
    worst = float(np.min(pnls))
    max_loss_threshold = worst * 0.9 if worst < 0 else worst * 1.1
    prob_max_loss = float(np.mean(pnls <= max_loss_threshold) * 100)

    # Target probability
    prob_target = float(np.mean(pnls >= target_pnl) * 100)

    # Percentiles
    pct_keys = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    percentiles = {p: round(float(np.percentile(pnls, p)), 2) for p in pct_keys}

    return MonteCarloResult(
        expected_pnl=round(float(np.mean(pnls)), 2),
        median_pnl=round(float(np.median(pnls)), 2),
        std_pnl=round(float(np.std(pnls)), 2),
        prob_profit=round(profitable / num_paths * 100, 1),
        var_95=round(var_95, 2),
        var_99=round(var_99, 2),
        cvar_95=round(cvar_95, 2),
        best_case=round(float(np.max(pnls)), 2),
        worst_case=round(worst, 2),
        prob_max_loss=round(prob_max_loss, 1),
        prob_target=round(prob_target, 1),
        percentiles=percentiles,
    )


def simulate_multi_expiry(
    legs: list[Leg],
    spot: float,
    T: float,
    r: float,
    sigma: float,
    check_points: list[float] | None = None,
    num_paths: int = 5000,
    seed: int | None = 42,
) -> list[dict]:
    """Simulate P&L at multiple time horizons.

    Shows how the position P&L distribution evolves over time,
    not just at expiry. Useful for understanding early exit opportunities.

    Args:
        legs: Option legs.
        spot: Current spot price.
        T: Total time to expiry.
        r: Risk-free rate.
        sigma: Volatility.
        check_points: Fractions of T to check (e.g., [0.25, 0.5, 0.75, 1.0]).
        num_paths: Simulation paths.
        seed: Random seed.

    Returns:
        List of dicts with P&L stats at each checkpoint.
    """
    if check_points is None:
        check_points = [0.25, 0.5, 0.75, 1.0]

    results = []
    for frac in check_points:
        t = T * frac
        mc = simulate_position(legs, spot, t, r, sigma, num_paths, seed=seed)
        results.append({
            "time_fraction": frac,
            "days_elapsed": round(t * 365),
            "days_remaining": round((T - t) * 365),
            "expected_pnl": mc.expected_pnl,
            "prob_profit": mc.prob_profit,
            "var_95": mc.var_95,
            "best_case": mc.best_case,
            "worst_case": mc.worst_case,
        })

    return results


def stress_test(
    legs: list[Leg],
    spot: float,
    scenarios: list[dict] | None = None,
) -> list[dict]:
    """Run stress test scenarios on a position.

    Tests P&L under extreme but plausible market moves.

    Args:
        legs: Option legs.
        spot: Current spot price.
        scenarios: Custom scenarios. If None, uses standard set.
            Each scenario: {"name": str, "spot_move_pct": float}

    Returns:
        List of scenario results with P&L impact.
    """
    if scenarios is None:
        scenarios = [
            {"name": "Crash -10%", "spot_move_pct": -10.0},
            {"name": "Sharp drop -5%", "spot_move_pct": -5.0},
            {"name": "Down -3%", "spot_move_pct": -3.0},
            {"name": "Down -1%", "spot_move_pct": -1.0},
            {"name": "Unchanged", "spot_move_pct": 0.0},
            {"name": "Up +1%", "spot_move_pct": 1.0},
            {"name": "Up +3%", "spot_move_pct": 3.0},
            {"name": "Rally +5%", "spot_move_pct": 5.0},
            {"name": "Melt-up +10%", "spot_move_pct": 10.0},
        ]

    results = []
    for scenario in scenarios:
        pct = scenario["spot_move_pct"]
        new_spot = spot * (1 + pct / 100.0)
        pnl = position_payoff_at_expiry(legs, new_spot)

        results.append({
            "scenario": scenario["name"],
            "spot_move_pct": pct,
            "new_spot": round(new_spot, 2),
            "pnl": round(pnl, 2),
        })

    return results
