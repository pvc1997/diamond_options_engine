"""Position adjustment advisor — roll, widen, convert, close recommendations.

When a position is challenged (moving against you, breaching a limit,
or approaching expiry), this module suggests adjustments to manage risk.

Adjustment Types:
- Roll: Move to different strike or expiry (roll up/down/out)
- Widen: Increase spread width for more room
- Convert: Transform one strategy into another
- Close: Exit the position (partial or full)
- Hedge: Add a hedging leg
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AdjustmentType(str, Enum):
    ROLL_OUT = "roll_out"           # Move to later expiry
    ROLL_UP = "roll_up"             # Move to higher strike
    ROLL_DOWN = "roll_down"         # Move to lower strike
    WIDEN = "widen"                 # Increase spread width
    CLOSE = "close"                 # Exit the position
    CLOSE_PARTIAL = "close_partial" # Reduce size
    ADD_HEDGE = "add_hedge"         # Add protective leg
    CONVERT = "convert"             # Transform strategy


@dataclass(frozen=True)
class Adjustment:
    """A recommended position adjustment."""
    type: AdjustmentType
    urgency: str                    # "immediate", "soon", "optional"
    description: str
    action_steps: list[str]         # Step-by-step instructions
    estimated_cost: float           # Net debit/credit of adjustment (INR)
    risk_reduction: str             # Qualitative risk impact
    trade_off: str                  # What you give up


@dataclass(frozen=True)
class AdjustmentAnalysis:
    """Complete adjustment analysis for a position."""
    position_status: str            # "healthy", "challenged", "at_risk", "in_trouble"
    trigger: str                    # What triggered the analysis
    adjustments: list[Adjustment]   # Ranked by recommendation strength
    do_nothing_risk: str            # Risk of taking no action


def analyze_position(
    symbol: str,
    strategy: str,
    spot: float,
    entry_spot: float,
    strikes: list[float],
    option_types: list[str],
    actions: list[str],
    premiums: list[float],
    days_to_expiry: int,
    current_pnl: float,
    max_loss: float,
    lot_size: int = 65,
    strike_step: float = 50.0,
) -> AdjustmentAnalysis:
    """Analyze a position and recommend adjustments.

    Args:
        symbol: Underlying symbol.
        strategy: Strategy slug (e.g., "iron_condor").
        spot: Current spot price.
        entry_spot: Spot at entry.
        strikes: List of strike prices for each leg.
        option_types: List of "CE"/"PE" for each leg.
        actions: List of "BUY"/"SELL" for each leg.
        premiums: List of entry premiums per share.
        days_to_expiry: Calendar DTE remaining.
        current_pnl: Current P&L in INR.
        max_loss: Maximum possible loss in INR.
        lot_size: Shares per lot.
        strike_step: Strike interval.

    Returns:
        AdjustmentAnalysis with ranked recommendations.
    """
    move_pct = (spot - entry_spot) / entry_spot * 100
    pnl_pct = (current_pnl / abs(max_loss) * 100) if max_loss != 0 else 0

    # Determine position status
    status = _assess_status(strategy, spot, strikes, option_types, actions,
                            days_to_expiry, pnl_pct, move_pct)

    trigger = _determine_trigger(status, move_pct, pnl_pct, days_to_expiry)

    adjustments = _generate_adjustments(
        strategy, status, spot, strikes, option_types, actions,
        premiums, days_to_expiry, move_pct, pnl_pct, lot_size, strike_step,
    )

    do_nothing = _assess_do_nothing_risk(status, days_to_expiry, pnl_pct)

    return AdjustmentAnalysis(
        position_status=status,
        trigger=trigger,
        adjustments=adjustments,
        do_nothing_risk=do_nothing,
    )


def _assess_status(
    strategy: str, spot: float, strikes: list[float],
    option_types: list[str], actions: list[str],
    dte: int, pnl_pct: float, move_pct: float,
) -> str:
    """Determine position health status."""
    # Check if any short strike is breached
    short_breached = False
    for strike, ot, action in zip(strikes, option_types, actions):
        if action.upper() == "SELL":
            if ot.upper() == "CE" and spot > strike:
                short_breached = True
            elif ot.upper() == "PE" and spot < strike:
                short_breached = True

    if pnl_pct < -70 or (short_breached and dte <= 2):
        return "in_trouble"
    elif short_breached or pnl_pct < -40:
        return "at_risk"
    elif abs(move_pct) > 2 or pnl_pct < -20:
        return "challenged"
    else:
        return "healthy"


def _determine_trigger(
    status: str, move_pct: float, pnl_pct: float, dte: int,
) -> str:
    """Determine what triggered the adjustment analysis."""
    triggers = []
    if status == "in_trouble":
        triggers.append(f"Position in trouble (P&L: {pnl_pct:.0f}%)")
    if abs(move_pct) > 3:
        direction = "up" if move_pct > 0 else "down"
        triggers.append(f"Underlying moved {abs(move_pct):.1f}% {direction}")
    if pnl_pct < -30:
        triggers.append(f"P&L at {pnl_pct:.0f}% of max loss")
    if dte <= 3:
        triggers.append(f"Only {dte} days to expiry")
    if not triggers:
        triggers.append("Routine check")
    return "; ".join(triggers)


def _generate_adjustments(
    strategy: str, status: str, spot: float, strikes: list[float],
    option_types: list[str], actions: list[str], premiums: list[float],
    dte: int, move_pct: float, pnl_pct: float,
    lot_size: int, step: float,
) -> list[Adjustment]:
    """Generate adjustment recommendations based on position status."""
    adjustments: list[Adjustment] = []

    if status == "healthy" and pnl_pct > 50:
        # Take profit
        adjustments.append(Adjustment(
            type=AdjustmentType.CLOSE,
            urgency="optional",
            description="Take profit — position has captured >50% of max profit",
            action_steps=[
                "Close all legs at market",
                f"Current P&L: {pnl_pct:.0f}% of max profit",
                "Re-enter if conditions still favorable",
            ],
            estimated_cost=0,
            risk_reduction="Eliminates all remaining risk",
            trade_off="Gives up remaining profit potential",
        ))

    if status in ("challenged", "at_risk", "in_trouble"):
        # Roll out (more time)
        if dte <= 14:
            adjustments.append(Adjustment(
                type=AdjustmentType.ROLL_OUT,
                urgency="soon" if status == "at_risk" else "optional",
                description="Roll to next expiry — buy more time for position to recover",
                action_steps=[
                    "Close current position",
                    "Re-open same strikes in next weekly/monthly expiry",
                    "Collect additional time value premium",
                ],
                estimated_cost=round(-spot * 0.001 * lot_size, 0),  # Approximate
                risk_reduction="Extends time for mean reversion",
                trade_off="Ties up margin for longer; additional transaction costs",
            ))

    if status in ("at_risk", "in_trouble"):
        # Close to cut losses
        urgency = "immediate" if status == "in_trouble" else "soon"
        adjustments.append(Adjustment(
            type=AdjustmentType.CLOSE,
            urgency=urgency,
            description="Close position to limit further losses",
            action_steps=[
                "Close all legs at market immediately",
                f"Accept current loss ({pnl_pct:.0f}% of max loss)",
                "Preserve capital for next opportunity",
            ],
            estimated_cost=0,
            risk_reduction="Eliminates all remaining risk",
            trade_off="Locks in the current loss",
        ))

    if status in ("challenged", "at_risk"):
        # Widen the spread
        if strategy in ("iron_condor", "bull_put_spread", "bear_call_spread",
                        "bull_call_spread", "bear_put_spread"):
            direction = "up" if move_pct > 0 else "down"
            adjustments.append(Adjustment(
                type=AdjustmentType.WIDEN,
                urgency="optional",
                description=f"Widen the {direction}side — move tested strike further OTM",
                action_steps=[
                    f"Close the tested short leg",
                    f"Re-sell at a strike {step:.0f} further OTM",
                    "Adjust long protection leg accordingly",
                    "Accept reduced credit for wider safety zone",
                ],
                estimated_cost=round(-step * 0.3 * lot_size, 0),
                risk_reduction="Gives more room before breach",
                trade_off="Reduces net credit / increases max loss",
            ))

    if status in ("challenged", "at_risk") and strategy in (
        "short_strangle", "short_straddle",
    ):
        # Add hedge
        adjustments.append(Adjustment(
            type=AdjustmentType.ADD_HEDGE,
            urgency="soon",
            description="Add a protective wing to cap risk",
            action_steps=[
                f"Buy a {'call' if move_pct > 0 else 'put'} {2*step:.0f} points OTM",
                "Converts naked position into a defined-risk spread",
            ],
            estimated_cost=round(-spot * 0.002 * lot_size, 0),
            risk_reduction="Converts to defined risk — caps max loss",
            trade_off="Costs premium to add protection",
        ))

    if status == "challenged" and dte > 7:
        # Partial close
        adjustments.append(Adjustment(
            type=AdjustmentType.CLOSE_PARTIAL,
            urgency="optional",
            description="Reduce position size — close 50% to lower exposure",
            action_steps=[
                "Close half of each leg",
                "Maintains position with lower risk",
            ],
            estimated_cost=0,
            risk_reduction="Cuts exposure by 50%",
            trade_off="Reduces both potential profit and loss by half",
        ))

    return adjustments


def _assess_do_nothing_risk(status: str, dte: int, pnl_pct: float) -> str:
    """Describe the risk of not adjusting."""
    if status == "in_trouble":
        return (
            "HIGH RISK: Position near max loss. Further adverse move could "
            "result in total loss. Assignment risk if short options are deep ITM."
        )
    elif status == "at_risk":
        return (
            f"MODERATE RISK: Short strike tested ({pnl_pct:.0f}% of max loss). "
            f"May recover if underlying reverses, but {dte} DTE remaining. "
            "Gamma risk increases as expiry approaches."
        )
    elif status == "challenged":
        return (
            f"LOW-MODERATE RISK: Position underwater ({pnl_pct:.0f}% of max loss) "
            f"but not yet critical. Time ({dte} DTE) may allow recovery. "
            "Monitor closely."
        )
    else:
        return "LOW RISK: Position is healthy. No adjustment needed."


def expiry_day_checklist(
    strategy: str,
    spot: float,
    strikes: list[float],
    option_types: list[str],
    actions: list[str],
    lot_size: int = 65,
) -> list[str]:
    """Generate expiry-day action checklist.

    On expiry day, positions need special attention due to:
    - Pin risk (spot near strike)
    - STT on ITM options exercised
    - Last-minute gamma exposure

    Returns:
        List of action items for expiry day management.
    """
    checklist: list[str] = []
    atm_zone = spot * 0.005  # 0.5% around spot = near-ATM

    for strike, ot, action in zip(strikes, option_types, actions):
        is_short = action.upper() == "SELL"
        is_call = ot.upper() in ("CE", "CALL", "C")

        itm = (is_call and spot > strike) or (not is_call and spot < strike)
        near_atm = abs(spot - strike) < atm_zone

        if is_short and itm:
            checklist.append(
                f"⚠ SHORT {strike}{ot} is ITM — close before 3:00 PM to avoid "
                f"exercise STT (0.125% on notional = ₹{spot * lot_size * 0.00125:,.0f})"
            )
        elif is_short and near_atm:
            checklist.append(
                f"⚠ SHORT {strike}{ot} is near ATM — pin risk, monitor closely. "
                "Close before 3:00 PM if uncertain."
            )
        elif not is_short and itm:
            checklist.append(
                f"LONG {strike}{ot} is ITM — will be auto-exercised. "
                "Consider closing to avoid exercise STT if intrinsic is small."
            )

    if not checklist:
        checklist.append("All positions are OTM — will expire worthless, no action needed.")

    checklist.append("Deadline: Close positions by 3:00 PM IST to avoid exercise.")

    return checklist
