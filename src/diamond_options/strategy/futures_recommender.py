"""Futures strategy recommender — trade suggestion engine.

Combines market conditions, basis analysis, and strategy scoring to produce
actionable futures trade recommendations with sizing, costs, and P&L targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from diamond_options.data.costs import futures_pnl, futures_breakeven
from diamond_options.data.universe import (
    get_futures_margin_pct,
    get_futures_margin_estimate,
    get_index_lot_size,
    get_lot_size,
)
from diamond_options.pricing.futures_pricing import (
    theoretical_futures_price,
    futures_mispricing,
)
from diamond_options.pricing.basis_analysis import analyze_basis
from diamond_options.strategy.futures_scanner import (
    FuturesMarketCondition,
    FuturesStrategySignal,
    TrendDirection,
    OIBuildupSignal,
    scan_futures_strategies,
    FuturesStrategyCategory,
)
from diamond_options.strategy.futures_strategies import (
    FuturesStrategySpec,
    FuturesOutlook,
)
from diamond_options.strategy.sizing import (
    PositionSize,
    fixed_risk_size,
    vix_adjusted_multiplier,
)


@dataclass(frozen=True)
class FuturesRecommendation:
    """A complete, actionable futures trade recommendation."""

    strategy: FuturesStrategySpec
    signal: FuturesStrategySignal
    symbol: str
    entry_price: float  # Futures entry price
    target: float  # Target exit price
    stop_loss: float  # Stop loss price
    lots: int
    lot_size: int
    margin_required: float
    max_loss: float  # Loss at stop_loss
    risk_reward: float  # target P&L / stop P&L
    costs: float  # Round-trip estimated costs
    breakeven: float  # Breakeven after costs
    confidence_score: int  # 0-100 from scanner
    rationale: str


def recommend_futures_trades(
    condition: FuturesMarketCondition,
    symbol: str = "NIFTY",
    capital: float = 500000.0,
    max_risk_pct: float = 2.0,
    max_results: int = 3,
    defined_risk_only: bool = False,
    category: FuturesStrategyCategory | None = None,
    risk_free_rate: float = 0.065,
) -> list[FuturesRecommendation]:
    """Generate ranked futures trade recommendations.

    Pipeline:
    1. Scan strategies against conditions
    2. For each strategy, calculate entry/target/stop
    3. Size position using risk management
    4. Calculate costs, breakeven, risk-reward
    5. Return ranked recommendations

    Args:
        condition: Current market snapshot.
        symbol: Underlying symbol (for lot size / margin lookup).
        capital: Available trading capital.
        max_risk_pct: Max risk per trade as % of capital.
        max_results: Number of recommendations.
        defined_risk_only: Only defined-risk strategies.
        category: Filter to specific category.
        risk_free_rate: For fair value calculation.

    Returns:
        List of FuturesRecommendation sorted by signal score.
    """
    # 1. Scan strategies
    signals = scan_futures_strategies(
        condition,
        min_score=35,
        max_results=max_results * 2,
        category=category,
        defined_risk_only=defined_risk_only,
    )

    if not signals:
        return []

    # Resolve lot size
    lot_size = get_lot_size(symbol)
    if lot_size == 0:
        lot_size = get_index_lot_size(symbol)
    if lot_size == 0:
        lot_size = 65  # Default

    margin_pct = get_futures_margin_pct(symbol)
    vix_mult = vix_adjusted_multiplier(condition.vix)

    recommendations = []

    for signal in signals:
        strategy = signal.strategy

        # 2. Calculate entry, target, stop based on strategy
        trade_params = _calculate_trade_params(
            strategy, condition, symbol, lot_size, margin_pct,
        )
        if trade_params is None:
            continue

        entry = trade_params["entry"]
        target = trade_params["target"]
        stop = trade_params["stop"]

        # 3. Size position
        # Max loss per lot = |entry - stop| × lot_size
        stop_distance = abs(entry - stop)
        max_loss_per_lot = stop_distance * lot_size
        if max_loss_per_lot <= 0:
            continue

        margin_per_lot = entry * lot_size * margin_pct

        sizing = fixed_risk_size(
            capital=capital,
            max_risk_pct=max_risk_pct,
            max_loss_per_lot=max_loss_per_lot,
            lot_size=lot_size,
            margin_per_lot=margin_per_lot,
            vix_multiplier=vix_mult,
        )

        if sizing.lots == 0:
            continue

        # 4. Costs and breakeven
        action = "BUY" if strategy.outlook == FuturesOutlook.BULLISH else "SELL"
        if strategy.outlook in (FuturesOutlook.NEUTRAL, FuturesOutlook.CARRY):
            action = "BUY"  # Default to long leg

        be = futures_breakeven(entry, sizing.lots, lot_size, action)

        pnl_at_stop = futures_pnl(entry, stop, sizing.lots, lot_size, action)
        pnl_at_target = futures_pnl(entry, target, sizing.lots, lot_size, action)

        total_costs = pnl_at_target["total_costs"]

        # Risk-reward
        target_net = pnl_at_target["net_pnl"]
        stop_net = abs(pnl_at_stop["net_pnl"])
        rr = (target_net / stop_net) if stop_net > 0 else 0.0

        # 5. Build rationale
        rationale = _build_rationale(signal, condition, entry, target, stop, sizing)

        recommendations.append(FuturesRecommendation(
            strategy=strategy,
            signal=signal,
            symbol=symbol,
            entry_price=round(entry, 2),
            target=round(target, 2),
            stop_loss=round(stop, 2),
            lots=sizing.lots,
            lot_size=lot_size,
            margin_required=round(sizing.margin_required, 2),
            max_loss=round(pnl_at_stop["net_pnl"], 2),
            risk_reward=round(rr, 2),
            costs=round(total_costs, 2),
            breakeven=be,
            confidence_score=signal.score,
            rationale=rationale,
        ))

    recommendations.sort(key=lambda r: r.confidence_score, reverse=True)
    return recommendations[:max_results]


def _calculate_trade_params(
    strategy: FuturesStrategySpec,
    condition: FuturesMarketCondition,
    symbol: str,
    lot_size: int,
    margin_pct: float,
) -> dict | None:
    """Calculate entry, target, stop for a strategy.

    Returns dict with entry, target, stop or None if not applicable.
    """
    spot = condition.spot
    near = condition.near_futures
    rv = condition.realized_vol

    # Default stop/target distances based on realized vol
    # 1-day move ≈ spot × rv / √252
    daily_move = spot * rv / 15.87 if rv > 0 else spot * 0.01
    target_distance = daily_move * 3  # 3-day move target
    stop_distance = daily_move * 2  # 2-day move stop

    if strategy.outlook == FuturesOutlook.BULLISH:
        return {
            "entry": near,
            "target": round(near + target_distance, 2),
            "stop": round(near - stop_distance, 2),
        }

    if strategy.outlook == FuturesOutlook.BEARISH:
        return {
            "entry": near,
            "target": round(near - target_distance, 2),
            "stop": round(near + stop_distance, 2),
        }

    if strategy.outlook == FuturesOutlook.NEUTRAL:
        # For pair trades, hedges — use smaller moves
        return {
            "entry": near,
            "target": round(near + daily_move, 2),
            "stop": round(near - daily_move * 1.5, 2),
        }

    if strategy.outlook == FuturesOutlook.CARRY:
        # Calendar spread — target is basis convergence
        basis = near - spot
        return {
            "entry": near,
            "target": round(near - basis * 0.5, 2),  # Half basis convergence
            "stop": round(near + abs(basis) * 0.5, 2),  # Basis widens
        }

    return None


def _build_rationale(
    signal: FuturesStrategySignal,
    condition: FuturesMarketCondition,
    entry: float,
    target: float,
    stop: float,
    sizing: PositionSize,
) -> str:
    """Build human-readable rationale."""
    parts = [
        f"{signal.strategy.name} (score: {signal.score}/100, {signal.confidence})",
        f"Market: spot={condition.spot:.0f}, VIX={condition.vix:.1f}, "
        f"basis={condition.basis_pct:.3f}%, trend={condition.trend.value}",
    ]

    # Top reasons
    good_reasons = [r for r in signal.reasons if "ideal" in r.lower()
                    or "strong" in r.lower() or "suits" in r.lower()
                    or "buildup" in r.lower()]
    if good_reasons:
        parts.append("Edge: " + "; ".join(good_reasons[:2]))

    parts.append(f"Entry={entry:.0f}, Target={target:.0f}, Stop={stop:.0f}")
    parts.append(f"Size: {sizing.lots} lots, risk ₹{sizing.capital_at_risk:,.0f} "
                 f"({sizing.capital_at_risk_pct:.1f}% of capital)")

    return " | ".join(parts)


def quick_futures_recommendation(
    spot: float,
    near_futures: float,
    vix: float,
    realized_vol: float,
    days_to_expiry: int = 20,
    trend: str = "neutral",
    oi_buildup: str = "neutral",
    symbol: str = "NIFTY",
    capital: float = 500000.0,
    next_futures: float = 0.0,
    rollover_pct: float = 0.0,
    defined_risk_only: bool = False,
) -> list[dict]:
    """Simplified entry point for futures recommendations.

    Converts simple inputs to FuturesMarketCondition and returns
    structured recommendations. Ideal for MCP tool usage.
    """
    trend_map = {
        "strong_bullish": TrendDirection.STRONG_BULLISH,
        "bullish": TrendDirection.BULLISH,
        "neutral": TrendDirection.NEUTRAL,
        "bearish": TrendDirection.BEARISH,
        "strong_bearish": TrendDirection.STRONG_BEARISH,
    }

    oi_map = {
        "long_buildup": OIBuildupSignal.LONG_BUILDUP,
        "short_buildup": OIBuildupSignal.SHORT_BUILDUP,
        "long_unwinding": OIBuildupSignal.LONG_UNWINDING,
        "short_covering": OIBuildupSignal.SHORT_COVERING,
        "neutral": OIBuildupSignal.NEUTRAL,
    }

    basis_pct = ((near_futures - spot) / spot * 100) if spot > 0 else 0.0
    ann_basis = (basis_pct / days_to_expiry * 365) if days_to_expiry > 0 else 0.0

    condition = FuturesMarketCondition(
        spot=spot,
        near_futures=near_futures,
        next_futures=next_futures,
        basis_pct=basis_pct,
        annualized_basis=ann_basis,
        vix=vix,
        trend=trend_map.get(trend, TrendDirection.NEUTRAL),
        realized_vol=realized_vol,
        days_to_expiry=days_to_expiry,
        oi_buildup=oi_map.get(oi_buildup, OIBuildupSignal.NEUTRAL),
        rollover_pct=rollover_pct,
    )

    recs = recommend_futures_trades(
        condition,
        symbol=symbol,
        capital=capital,
        defined_risk_only=defined_risk_only,
    )

    results = []
    for rec in recs:
        results.append({
            "strategy": rec.strategy.name,
            "category": rec.strategy.category.value,
            "score": rec.confidence_score,
            "confidence": rec.signal.confidence,
            "outlook": rec.strategy.outlook.value,
            "risk_profile": rec.strategy.risk_profile.value,
            "symbol": rec.symbol,
            "entry_price": rec.entry_price,
            "target": rec.target,
            "stop_loss": rec.stop_loss,
            "lots": rec.lots,
            "lot_size": rec.lot_size,
            "margin_required": rec.margin_required,
            "max_loss": rec.max_loss,
            "risk_reward": rec.risk_reward,
            "costs": rec.costs,
            "breakeven": rec.breakeven,
            "rationale": rec.rationale,
            "reasons": rec.signal.reasons,
        })

    return results
