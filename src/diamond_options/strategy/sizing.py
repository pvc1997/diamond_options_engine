"""Position sizing — risk-based and Kelly criterion sizing.

Determines optimal number of lots based on:
1. Fixed-risk per trade (% of capital at risk)
2. Kelly criterion (edge-based optimal sizing)
3. VIX regime adjustment (reduce size in high vol)
4. Portfolio constraints (max margin, max positions)

Indian F&O specifics:
- Sizes in lots (NIFTY: 25, BANKNIFTY: 15, etc.)
- Minimum: 1 lot, must be whole number
- Margin-aware: can't exceed available margin
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSize:
    """Recommended position size with rationale."""
    lots: int                    # Number of lots to trade
    lot_size: int                # Shares per lot
    total_quantity: int          # lots * lot_size
    capital_at_risk: float       # Max loss in INR
    capital_at_risk_pct: float   # As % of portfolio
    margin_required: float       # Estimated margin needed
    margin_pct: float            # As % of available capital
    method: str                  # "fixed_risk", "kelly", "max_constraint"
    notes: str                   # Sizing rationale


def fixed_risk_size(
    capital: float,
    max_risk_pct: float,
    max_loss_per_lot: float,
    lot_size: int,
    margin_per_lot: float = 0.0,
    max_margin_pct: float = 0.30,
    vix_multiplier: float = 1.0,
    max_lots: int = 50,
) -> PositionSize:
    """Size position by risking a fixed percentage of capital.

    The most common and safest sizing method. Ensures no single trade
    can cause more than X% drawdown.

    Args:
        capital: Total available capital (INR).
        max_risk_pct: Max % of capital to risk per trade (e.g., 2.0 for 2%).
        max_loss_per_lot: Maximum loss per lot in INR.
        lot_size: Shares per lot.
        margin_per_lot: Margin required per lot (0 for long options).
        max_margin_pct: Maximum margin utilization (default 30%).
        vix_multiplier: VIX regime multiplier (0.25-1.0). Reduces size in high vol.
        max_lots: Hard cap on lot count.

    Returns:
        PositionSize with recommended lots.
    """
    if max_loss_per_lot <= 0 or capital <= 0:
        return PositionSize(
            lots=0, lot_size=lot_size, total_quantity=0,
            capital_at_risk=0, capital_at_risk_pct=0,
            margin_required=0, margin_pct=0,
            method="fixed_risk",
            notes="Invalid inputs: max_loss_per_lot and capital must be positive",
        )

    # Max risk amount
    risk_budget = capital * (max_risk_pct / 100.0) * vix_multiplier
    lots_by_risk = int(risk_budget / max_loss_per_lot)

    # Margin constraint
    if margin_per_lot > 0:
        max_margin_amount = capital * max_margin_pct
        lots_by_margin = int(max_margin_amount / margin_per_lot)
    else:
        lots_by_margin = max_lots

    # Take the minimum of all constraints
    lots = max(1, min(lots_by_risk, lots_by_margin, max_lots))

    actual_risk = lots * max_loss_per_lot
    actual_margin = lots * margin_per_lot

    notes_parts = [f"Risk budget: ₹{risk_budget:,.0f} ({max_risk_pct}% of ₹{capital:,.0f})"]
    if vix_multiplier < 1.0:
        notes_parts.append(f"VIX adjusted: ×{vix_multiplier:.2f}")
    if lots_by_margin < lots_by_risk:
        notes_parts.append(f"Margin-constrained to {lots_by_margin} lots")

    return PositionSize(
        lots=lots,
        lot_size=lot_size,
        total_quantity=lots * lot_size,
        capital_at_risk=round(actual_risk, 2),
        capital_at_risk_pct=round(actual_risk / capital * 100, 2),
        margin_required=round(actual_margin, 2),
        margin_pct=round(actual_margin / capital * 100, 2) if capital > 0 else 0,
        method="fixed_risk",
        notes="; ".join(notes_parts),
    )


def kelly_size(
    capital: float,
    win_probability: float,
    avg_win: float,
    avg_loss: float,
    lot_size: int,
    max_loss_per_lot: float,
    fraction: float = 0.5,
    max_lots: int = 50,
) -> PositionSize:
    """Size position using Kelly criterion (fractional).

    Kelly formula: f* = (p * b - q) / b
    where:
      p = probability of winning
      q = 1 - p
      b = win/loss ratio (avg_win / avg_loss)

    Full Kelly is too aggressive for options trading. Half-Kelly (fraction=0.5)
    is the industry standard for smoother equity curves.

    Args:
        capital: Total capital.
        win_probability: P(profit), 0-1.
        avg_win: Average winning trade P&L (positive).
        avg_loss: Average losing trade P&L (positive, will be used as magnitude).
        lot_size: Shares per lot.
        max_loss_per_lot: Max loss per lot for sizing.
        fraction: Kelly fraction (0.5 = half-Kelly, recommended).
        max_lots: Hard cap.

    Returns:
        PositionSize with Kelly-optimal lots.
    """
    if avg_loss <= 0 or capital <= 0 or win_probability <= 0 or win_probability >= 1:
        return PositionSize(
            lots=0, lot_size=lot_size, total_quantity=0,
            capital_at_risk=0, capital_at_risk_pct=0,
            margin_required=0, margin_pct=0,
            method="kelly",
            notes="Invalid inputs for Kelly calculation",
        )

    p = win_probability
    q = 1.0 - p
    b = avg_win / avg_loss  # Win/loss ratio

    kelly_pct = (p * b - q) / b
    kelly_pct = max(0.0, kelly_pct)  # Never go negative

    # Apply fractional Kelly
    adjusted_pct = kelly_pct * fraction

    # Convert to lots
    risk_budget = capital * adjusted_pct
    lots = max(0, min(int(risk_budget / max_loss_per_lot), max_lots))

    actual_risk = lots * max_loss_per_lot

    return PositionSize(
        lots=lots,
        lot_size=lot_size,
        total_quantity=lots * lot_size,
        capital_at_risk=round(actual_risk, 2),
        capital_at_risk_pct=round(actual_risk / capital * 100, 2) if capital > 0 else 0,
        margin_required=0,
        margin_pct=0,
        method="kelly",
        notes=(
            f"Kelly f*={kelly_pct:.1%}, {fraction:.0%}-Kelly={adjusted_pct:.1%}; "
            f"Win rate={p:.0%}, Win/Loss ratio={b:.2f}"
        ),
    )


def vix_adjusted_multiplier(vix: float) -> float:
    """Return position sizing multiplier based on VIX regime.

    Lower multiplier in high VIX → smaller positions → less exposure
    when markets are volatile.

    Args:
        vix: Current India VIX value.

    Returns:
        Multiplier between 0.25 and 1.0.
    """
    if vix < 12:
        return 0.75   # Low vol — slightly reduced (complacency risk)
    elif vix < 18:
        return 1.0    # Normal — full size
    elif vix < 25:
        return 0.80   # Elevated — reduce 20%
    elif vix < 35:
        return 0.50   # High — half size
    else:
        return 0.25   # Crisis — quarter size


def max_lots_by_capital(
    capital: float,
    premium_per_share: float,
    lot_size: int,
    max_allocation_pct: float = 5.0,
) -> int:
    """Maximum lots affordable for a long option position.

    For long options, the max loss is the premium paid.

    Args:
        capital: Available capital.
        premium_per_share: Option premium per share.
        lot_size: Shares per lot.
        max_allocation_pct: Max % of capital to allocate (default 5%).

    Returns:
        Maximum number of lots.
    """
    if premium_per_share <= 0 or capital <= 0:
        return 0

    max_spend = capital * (max_allocation_pct / 100.0)
    cost_per_lot = premium_per_share * lot_size
    return max(0, int(max_spend / cost_per_lot))
