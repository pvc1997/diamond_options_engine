"""Futures position adjustment advisor.

Recommends adjustments for futures positions based on P&L,
expiry proximity, basis changes, and risk limits.

Adjustment Types:
- Roll: Move to next expiry (near-expiry rollover)
- Scale down: Reduce position size
- Add hedge: Add opposite futures or options protection
- Convert to spread: Turn naked into calendar/pair
- Close: Exit the position
- Reverse: Flip direction on trend change
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FuturesAdjustmentType(str, Enum):
    ROLL_NEXT = "roll_next"          # Roll to next month expiry
    SCALE_DOWN = "scale_down"        # Reduce lot count
    ADD_HEDGE = "add_hedge"          # Add protective position
    CONVERT_SPREAD = "convert_spread"  # Convert to calendar spread
    CLOSE = "close"                  # Exit position
    CLOSE_PARTIAL = "close_partial"  # Partial exit
    REVERSE = "reverse"             # Flip long to short or vice versa
    ADD_STOP = "add_stop"           # Add/tighten stop loss


@dataclass(frozen=True)
class FuturesAdjustment:
    """A recommended futures position adjustment."""
    type: FuturesAdjustmentType
    urgency: str  # "immediate", "soon", "optional"
    description: str
    action_steps: list[str]
    estimated_cost: float  # Net cost/credit of adjustment
    risk_reduction: str
    trade_off: str


@dataclass(frozen=True)
class FuturesAdjustmentAnalysis:
    """Complete adjustment analysis for a futures position."""
    position_status: str  # "healthy", "challenged", "at_risk", "in_trouble"
    trigger: str
    adjustments: list[FuturesAdjustment]
    do_nothing_risk: str


def analyze_futures_position(
    symbol: str,
    action: str,
    lots: int,
    lot_size: int,
    entry_price: float,
    current_price: float,
    spot_price: float,
    days_to_expiry: int,
    basis_pct: float = 0.0,
    stop_loss: float = 0.0,
    target: float = 0.0,
    capital: float = 500000.0,
) -> FuturesAdjustmentAnalysis:
    """Analyze a futures position and recommend adjustments.

    Args:
        symbol: Underlying symbol.
        action: "BUY" or "SELL".
        lots: Number of lots.
        lot_size: Shares per lot.
        entry_price: Entry futures price.
        current_price: Current futures price.
        spot_price: Current spot price.
        days_to_expiry: Calendar DTE.
        basis_pct: Current basis as % of spot.
        stop_loss: Stop loss price (0 = none set).
        target: Target price (0 = none set).
        capital: Total trading capital.

    Returns:
        FuturesAdjustmentAnalysis with ranked recommendations.
    """
    direction = 1.0 if action.upper() == "BUY" else -1.0
    qty = lots * lot_size
    pnl = (current_price - entry_price) * qty * direction
    pnl_pct = (pnl / capital * 100) if capital > 0 else 0.0
    move_pct = (current_price - entry_price) / entry_price * 100 * direction

    status = _assess_futures_status(
        move_pct, pnl_pct, days_to_expiry, stop_loss, current_price, action,
    )
    trigger = _determine_futures_trigger(
        status, move_pct, pnl_pct, days_to_expiry, basis_pct,
    )
    adjustments = _generate_futures_adjustments(
        symbol, action, lots, lot_size, entry_price, current_price,
        spot_price, days_to_expiry, move_pct, pnl_pct, basis_pct,
        stop_loss, target, capital, status,
    )
    do_nothing = _assess_futures_do_nothing(status, days_to_expiry, pnl_pct)

    return FuturesAdjustmentAnalysis(
        position_status=status,
        trigger=trigger,
        adjustments=adjustments,
        do_nothing_risk=do_nothing,
    )


def _assess_futures_status(
    move_pct: float,
    pnl_pct: float,
    dte: int,
    stop_loss: float,
    current_price: float,
    action: str,
) -> str:
    """Determine position health status."""
    # Check stop loss proximity
    stop_hit = False
    if stop_loss > 0:
        if action.upper() == "BUY" and current_price <= stop_loss:
            stop_hit = True
        elif action.upper() == "SELL" and current_price >= stop_loss:
            stop_hit = True

    if stop_hit or pnl_pct < -3.0:
        return "in_trouble"
    elif move_pct < -2.0 or pnl_pct < -1.5:
        return "at_risk"
    elif move_pct < -1.0 or (dte <= 2 and abs(move_pct) < 0.5):
        return "challenged"
    else:
        return "healthy"


def _determine_futures_trigger(
    status: str,
    move_pct: float,
    pnl_pct: float,
    dte: int,
    basis_pct: float,
) -> str:
    """Determine what triggered the analysis."""
    triggers = []
    if status == "in_trouble":
        triggers.append(f"Position in trouble (P&L: {pnl_pct:.1f}% of capital)")
    if move_pct < -2.0:
        triggers.append(f"Adverse move {abs(move_pct):.1f}%")
    if pnl_pct < -1.0:
        triggers.append(f"Unrealized loss {abs(pnl_pct):.1f}% of capital")
    if dte <= 3:
        triggers.append(f"Only {dte} days to expiry")
    if abs(basis_pct) > 1.5:
        triggers.append(f"Basis deviation {basis_pct:.3f}%")
    if not triggers:
        triggers.append("Routine check")
    return "; ".join(triggers)


def _generate_futures_adjustments(
    symbol: str,
    action: str,
    lots: int,
    lot_size: int,
    entry_price: float,
    current_price: float,
    spot_price: float,
    dte: int,
    move_pct: float,
    pnl_pct: float,
    basis_pct: float,
    stop_loss: float,
    target: float,
    capital: float,
    status: str,
) -> list[FuturesAdjustment]:
    """Generate adjustment recommendations."""
    adjustments: list[FuturesAdjustment] = []
    qty = lots * lot_size
    cost_per_roll = round(current_price * qty * 0.0005, 0)  # ~0.05% round trip

    # 1. Profit taking
    if status == "healthy" and move_pct > 2.0:
        adjustments.append(FuturesAdjustment(
            type=FuturesAdjustmentType.CLOSE,
            urgency="optional",
            description="Take profit — position has moved >2% in your favor",
            action_steps=[
                f"Close {lots} lots at market (~₹{current_price:.0f})",
                f"Lock in P&L of {pnl_pct:.1f}% of capital",
                "Re-enter on pullback if trend continues",
            ],
            estimated_cost=cost_per_roll,
            risk_reduction="Eliminates all position risk",
            trade_off="Gives up further upside potential",
        ))

    # 2. Target hit
    if target > 0:
        if (action.upper() == "BUY" and current_price >= target) or \
           (action.upper() == "SELL" and current_price <= target):
            adjustments.append(FuturesAdjustment(
                type=FuturesAdjustmentType.CLOSE,
                urgency="soon",
                description="Target reached — book profits",
                action_steps=[
                    f"Close {lots} lots at market",
                    "Target price achieved",
                ],
                estimated_cost=cost_per_roll,
                risk_reduction="Locks in profit at target",
                trade_off="None — plan followed",
            ))

    # 3. Roll near expiry
    if dte <= 3:
        adjustments.append(FuturesAdjustment(
            type=FuturesAdjustmentType.ROLL_NEXT,
            urgency="soon" if dte <= 1 else "optional",
            description=f"Roll to next month — only {dte} DTE remaining",
            action_steps=[
                f"Close current {action} at ₹{current_price:.0f}",
                f"Open same direction in next month futures",
                "Check basis spread before rolling — aim for narrow spread",
            ],
            estimated_cost=cost_per_roll,
            risk_reduction="Avoids physical settlement risk and last-day volatility",
            trade_off=f"Roll cost ~₹{cost_per_roll:,.0f}; new month may have different basis",
        ))

    # 4. Cut losses
    if status in ("at_risk", "in_trouble"):
        urgency = "immediate" if status == "in_trouble" else "soon"
        adjustments.append(FuturesAdjustment(
            type=FuturesAdjustmentType.CLOSE,
            urgency=urgency,
            description="Close position to limit further losses",
            action_steps=[
                f"Close {lots} lots at market immediately",
                f"Accept current loss ({pnl_pct:.1f}% of capital)",
                "Preserve capital for next opportunity",
            ],
            estimated_cost=cost_per_roll,
            risk_reduction="Eliminates all remaining risk",
            trade_off="Locks in the current loss",
        ))

    # 5. Scale down
    if status in ("challenged", "at_risk") and lots > 1:
        reduce_lots = max(1, lots // 2)
        adjustments.append(FuturesAdjustment(
            type=FuturesAdjustmentType.SCALE_DOWN,
            urgency="optional",
            description=f"Reduce to {lots - reduce_lots} lots — lower exposure",
            action_steps=[
                f"Close {reduce_lots} of {lots} lots",
                f"Reduces notional by {reduce_lots / lots * 100:.0f}%",
            ],
            estimated_cost=round(cost_per_roll * reduce_lots / lots, 0),
            risk_reduction=f"Cuts exposure by {reduce_lots / lots * 100:.0f}%",
            trade_off="Reduces both potential profit and loss proportionally",
        ))

    # 6. Add hedge
    if status in ("challenged", "at_risk"):
        hedge_action = "SELL" if action.upper() == "BUY" else "BUY"
        adjustments.append(FuturesAdjustment(
            type=FuturesAdjustmentType.ADD_HEDGE,
            urgency="optional",
            description=f"Add {hedge_action.lower()} hedge to cap downside",
            action_steps=[
                f"Buy OTM {'put' if action.upper() == 'BUY' else 'call'} for protection",
                "Or add partial opposite futures to reduce net exposure",
                "Creates a synthetic spread with defined risk",
            ],
            estimated_cost=round(spot_price * lot_size * 0.005, 0),
            risk_reduction="Caps maximum loss at hedge level",
            trade_off="Hedge cost reduces net profit",
        ))

    # 7. Convert to calendar spread
    if status == "challenged" and dte > 5:
        adjustments.append(FuturesAdjustment(
            type=FuturesAdjustmentType.CONVERT_SPREAD,
            urgency="optional",
            description="Convert to calendar spread — reduce directional risk",
            action_steps=[
                f"Keep current {action} in near month",
                f"Add opposite position in next month",
                "Converts to a basis/carry trade",
            ],
            estimated_cost=cost_per_roll,
            risk_reduction="Reduces directional risk to basis risk only",
            trade_off="Gives up directional upside; adds margin for second leg",
        ))

    # 8. Add/tighten stop
    if status == "healthy" and stop_loss == 0 and move_pct > 0:
        adjustments.append(FuturesAdjustment(
            type=FuturesAdjustmentType.ADD_STOP,
            urgency="optional",
            description="Set trailing stop to protect profits",
            action_steps=[
                f"Set stop at entry ₹{entry_price:.0f} (breakeven stop)",
                "Or trail stop 1-2% below current price",
                "Locks in gains while allowing room to run",
            ],
            estimated_cost=0,
            risk_reduction="Protects accumulated profit",
            trade_off="May get stopped out on normal volatility",
        ))

    return adjustments


def _assess_futures_do_nothing(status: str, dte: int, pnl_pct: float) -> str:
    """Describe the risk of not adjusting."""
    if status == "in_trouble":
        return (
            "HIGH RISK: Position has significant unrealized loss. Futures have "
            "unlimited risk — further adverse moves directly increase loss. "
            "Consider closing or hedging immediately."
        )
    elif status == "at_risk":
        return (
            f"MODERATE-HIGH RISK: Position underwater ({pnl_pct:.1f}% of capital). "
            f"With {dte} DTE, basis convergence or further adverse move possible. "
            "Monitor margin requirements — may face margin call."
        )
    elif status == "challenged":
        return (
            f"MODERATE RISK: Position mildly adverse ({pnl_pct:.1f}% of capital). "
            f"{dte} DTE remaining. May recover but needs monitoring. "
            "Set stop loss if not already in place."
        )
    else:
        return "LOW RISK: Position is healthy. Continue monitoring."


def futures_expiry_checklist(
    symbol: str,
    action: str,
    lots: int,
    lot_size: int,
    entry_price: float,
    current_price: float,
    spot_price: float,
    days_to_expiry: int,
) -> list[str]:
    """Generate futures expiry-day checklist.

    On expiry day, futures positions need attention for:
    - Physical settlement (stock futures)
    - Cash settlement (index futures)
    - Rollover decisions
    - Basis convergence

    Returns:
        List of action items for expiry management.
    """
    checklist: list[str] = []
    direction = 1.0 if action.upper() == "BUY" else -1.0
    qty = lots * lot_size
    pnl = (current_price - entry_price) * qty * direction

    is_index = symbol.upper() in ("NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY")

    if days_to_expiry == 0:
        if is_index:
            checklist.append(
                f"INDEX FUTURES: {symbol} will cash-settle today at closing price. "
                f"Current P&L: ₹{pnl:,.0f}"
            )
        else:
            checklist.append(
                f"⚠ STOCK FUTURES: {symbol} will physically settle. "
                f"Ensure sufficient funds/shares for delivery. "
                f"Delivery margin ~40-50% of contract value."
            )
            notional = current_price * qty
            checklist.append(
                f"Contract value: ₹{notional:,.0f}. "
                f"Delivery margin needed: ~₹{notional * 0.45:,.0f}"
            )

    if days_to_expiry <= 1 and not is_index:
        checklist.append(
            "If you don't want physical delivery, close before 3:00 PM today."
        )

    if days_to_expiry <= 2:
        checklist.append(
            f"Consider rolling to next month if you want to maintain the position. "
            f"Roll cost depends on calendar spread."
        )

    basis = current_price - spot_price
    if days_to_expiry <= 1 and abs(basis) > spot_price * 0.002:
        checklist.append(
            f"Basis still at ₹{basis:.2f} ({basis/spot_price*100:.3f}%). "
            f"Should converge to near zero by close."
        )

    if pnl > 0:
        checklist.append(
            f"Position is profitable (₹{pnl:,.0f}). "
            f"Book profit or roll — don't let a winner turn into a loser."
        )
    elif pnl < 0:
        checklist.append(
            f"Position has unrealized loss (₹{pnl:,.0f}). "
            f"Decide: accept settlement or roll to next month."
        )

    if not checklist:
        checklist.append(f"Position has {days_to_expiry} DTE. No immediate action required.")

    return checklist
