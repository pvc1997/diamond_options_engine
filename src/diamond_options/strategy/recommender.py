"""Strategy recommender — high-level trade suggestion engine.

Combines market conditions, VIX regime, IV analysis, and strategy scoring
to produce actionable trade recommendations with mathematical backing.

This is the main entry point for "suggest me a trade" requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from diamond_options.strategy.definitions import (
    STRATEGIES,
    StrategySpec,
    BUILDERS,
    StrategyCategory,
)
from diamond_options.strategy.scanner import (
    MarketCondition,
    StrategySignal,
    TrendDirection,
    scan_strategies,
    suggest_strikes,
    score_strategy,
)
from diamond_options.strategy.sizing import (
    PositionSize,
    fixed_risk_size,
    kelly_size,
    vix_adjusted_multiplier,
)
from diamond_options.pricing.payoff import Leg, analyze_payoff, expected_value


@dataclass(frozen=True)
class TradeRecommendation:
    """A complete, actionable trade recommendation."""
    strategy: StrategySpec
    signal: StrategySignal
    legs: list[Leg]
    strikes: dict
    position_size: PositionSize
    max_profit: float
    max_loss: float
    breakevens: list[float]
    risk_reward: float
    expected_pnl: float
    prob_profit: float
    margin_required: float
    net_premium: float
    rationale: str


def recommend_trades(
    condition: MarketCondition,
    capital: float = 500000.0,
    max_risk_pct: float = 2.0,
    lot_size: int = 65,
    strike_step: float = 50.0,
    max_results: int = 3,
    defined_risk_only: bool = False,
    category: StrategyCategory | None = None,
) -> list[TradeRecommendation]:
    """Generate ranked trade recommendations for current conditions.

    This is the primary function for trade suggestions. It:
    1. Scans all strategies against market conditions
    2. Builds optimal legs with suggested strikes
    3. Sizes positions using risk management
    4. Computes payoff analysis and expected value
    5. Returns ranked, actionable recommendations

    Args:
        condition: Current market snapshot.
        capital: Available trading capital in INR.
        max_risk_pct: Max risk per trade as % of capital.
        lot_size: Lot size for the instrument.
        strike_step: Strike price interval (50 for NIFTY).
        max_results: Number of recommendations to return.
        defined_risk_only: Only suggest defined-risk strategies.
        category: Filter to specific strategy category.

    Returns:
        List of TradeRecommendation sorted by signal score.
    """
    # 1. Scan and rank strategies
    signals = scan_strategies(
        condition,
        min_score=40,
        max_results=max_results * 2,  # Get more, filter later
        category=category,
        defined_risk_only=defined_risk_only,
    )

    if not signals:
        return []

    vix_mult = vix_adjusted_multiplier(condition.vix)
    recommendations = []

    for signal in signals:
        slug = signal.strategy.slug
        if slug not in BUILDERS:
            continue

        # 2. Get suggested strikes
        strikes = suggest_strikes(slug, condition.spot, strike_step)

        # 3. Build legs with synthetic premiums
        legs = _build_legs_with_premiums(
            slug, strikes, condition, lot_size,
        )
        if not legs:
            continue

        # 4. Payoff analysis
        try:
            analysis = analyze_payoff(legs, condition.spot)
        except Exception:
            continue

        max_loss = analysis.max_loss
        if max_loss == float("-inf"):
            # For undefined risk, estimate max loss as 2× notional delta
            max_loss = -condition.spot * 0.15 * lot_size

        # 5. Position sizing
        max_loss_per_lot = abs(max_loss) if max_loss != 0 else condition.spot * lot_size * 0.1
        sizing = fixed_risk_size(
            capital=capital,
            max_risk_pct=max_risk_pct,
            max_loss_per_lot=max_loss_per_lot,
            lot_size=lot_size,
            margin_per_lot=analysis.margin_required,
            vix_multiplier=vix_mult,
        )

        if sizing.lots == 0:
            continue

        # 6. Expected value (Monte Carlo)
        T = condition.days_to_expiry / 365.0
        try:
            ev = expected_value(
                legs, condition.spot, T,
                r=0.065, sigma=condition.implied_vol,
                num_simulations=5000,
            )
        except Exception:
            ev = {"expected_pnl": 0, "prob_profit": 50.0}

        # 7. Build rationale
        rationale = _build_rationale(signal, condition, analysis, ev)

        recommendations.append(TradeRecommendation(
            strategy=signal.strategy,
            signal=signal,
            legs=legs,
            strikes=strikes,
            position_size=sizing,
            max_profit=analysis.max_profit,
            max_loss=analysis.max_loss,
            breakevens=analysis.breakevens,
            risk_reward=analysis.risk_reward,
            expected_pnl=ev["expected_pnl"],
            prob_profit=ev["prob_profit"],
            margin_required=analysis.margin_required,
            net_premium=analysis.net_premium,
            rationale=rationale,
        ))

    # Sort by signal score, take top results
    recommendations.sort(key=lambda r: r.signal.score, reverse=True)
    return recommendations[:max_results]


def _build_legs_with_premiums(
    slug: str,
    strikes: dict,
    condition: MarketCondition,
    lot_size: int,
) -> list[Leg]:
    """Build strategy legs with estimated premiums from Black-Scholes.

    Uses BS pricing to estimate fair premiums for each leg.
    """
    from diamond_options.pricing.black_scholes import call_price, put_price

    T = condition.days_to_expiry / 365.0
    r = 0.065
    sigma = condition.implied_vol
    spot = condition.spot

    def _price(strike: float, opt_type: str) -> float:
        if opt_type in ("CE", "CALL", "C"):
            return call_price(spot, strike, T, r, sigma).price
        return put_price(spot, strike, T, r, sigma).price

    try:
        if slug == "long_call":
            p = _price(strikes["strike"], "CE")
            return [Leg(strikes["strike"], "CE", "BUY", p, 1, lot_size)]

        elif slug == "long_put":
            p = _price(strikes["strike"], "PE")
            return [Leg(strikes["strike"], "PE", "BUY", p, 1, lot_size)]

        elif slug == "bull_call_spread":
            p1 = _price(strikes["lower_strike"], "CE")
            p2 = _price(strikes["upper_strike"], "CE")
            return [
                Leg(strikes["lower_strike"], "CE", "BUY", p1, 1, lot_size),
                Leg(strikes["upper_strike"], "CE", "SELL", p2, 1, lot_size),
            ]

        elif slug == "bear_put_spread":
            p1 = _price(strikes["upper_strike"], "PE")
            p2 = _price(strikes["lower_strike"], "PE")
            return [
                Leg(strikes["upper_strike"], "PE", "BUY", p1, 1, lot_size),
                Leg(strikes["lower_strike"], "PE", "SELL", p2, 1, lot_size),
            ]

        elif slug == "bull_put_spread":
            p1 = _price(strikes["upper_strike"], "PE")
            p2 = _price(strikes["lower_strike"], "PE")
            return [
                Leg(strikes["upper_strike"], "PE", "SELL", p1, 1, lot_size),
                Leg(strikes["lower_strike"], "PE", "BUY", p2, 1, lot_size),
            ]

        elif slug == "bear_call_spread":
            p1 = _price(strikes["lower_strike"], "CE")
            p2 = _price(strikes["upper_strike"], "CE")
            return [
                Leg(strikes["lower_strike"], "CE", "SELL", p1, 1, lot_size),
                Leg(strikes["upper_strike"], "CE", "BUY", p2, 1, lot_size),
            ]

        elif slug == "short_straddle":
            pc = _price(strikes["strike"], "CE")
            pp = _price(strikes["strike"], "PE")
            return [
                Leg(strikes["strike"], "CE", "SELL", pc, 1, lot_size),
                Leg(strikes["strike"], "PE", "SELL", pp, 1, lot_size),
            ]

        elif slug == "long_straddle":
            pc = _price(strikes["strike"], "CE")
            pp = _price(strikes["strike"], "PE")
            return [
                Leg(strikes["strike"], "CE", "BUY", pc, 1, lot_size),
                Leg(strikes["strike"], "PE", "BUY", pp, 1, lot_size),
            ]

        elif slug == "short_strangle":
            pc = _price(strikes["call_strike"], "CE")
            pp = _price(strikes["put_strike"], "PE")
            return [
                Leg(strikes["call_strike"], "CE", "SELL", pc, 1, lot_size),
                Leg(strikes["put_strike"], "PE", "SELL", pp, 1, lot_size),
            ]

        elif slug == "long_strangle":
            pc = _price(strikes["call_strike"], "CE")
            pp = _price(strikes["put_strike"], "PE")
            return [
                Leg(strikes["call_strike"], "CE", "BUY", pc, 1, lot_size),
                Leg(strikes["put_strike"], "PE", "BUY", pp, 1, lot_size),
            ]

        elif slug == "iron_condor":
            return [
                Leg(strikes["put_buy_strike"], "PE", "BUY",
                    _price(strikes["put_buy_strike"], "PE"), 1, lot_size),
                Leg(strikes["put_sell_strike"], "PE", "SELL",
                    _price(strikes["put_sell_strike"], "PE"), 1, lot_size),
                Leg(strikes["call_sell_strike"], "CE", "SELL",
                    _price(strikes["call_sell_strike"], "CE"), 1, lot_size),
                Leg(strikes["call_buy_strike"], "CE", "BUY",
                    _price(strikes["call_buy_strike"], "CE"), 1, lot_size),
            ]

        elif slug == "iron_butterfly":
            return [
                Leg(strikes["put_wing"], "PE", "BUY",
                    _price(strikes["put_wing"], "PE"), 1, lot_size),
                Leg(strikes["strike"], "PE", "SELL",
                    _price(strikes["strike"], "PE"), 1, lot_size),
                Leg(strikes["strike"], "CE", "SELL",
                    _price(strikes["strike"], "CE"), 1, lot_size),
                Leg(strikes["call_wing"], "CE", "BUY",
                    _price(strikes["call_wing"], "CE"), 1, lot_size),
            ]

        elif slug == "ratio_spread":
            p1 = _price(strikes["buy_strike"], "CE")
            p2 = _price(strikes["sell_strike"], "CE")
            return [
                Leg(strikes["buy_strike"], "CE", "BUY", p1, 1, lot_size),
                Leg(strikes["sell_strike"], "CE", "SELL", p2, 2, lot_size),
            ]

        elif slug == "jade_lizard":
            return [
                Leg(strikes["put_strike"], "PE", "SELL",
                    _price(strikes["put_strike"], "PE"), 1, lot_size),
                Leg(strikes["call_sell_strike"], "CE", "SELL",
                    _price(strikes["call_sell_strike"], "CE"), 1, lot_size),
                Leg(strikes["call_buy_strike"], "CE", "BUY",
                    _price(strikes["call_buy_strike"], "CE"), 1, lot_size),
            ]

        elif slug == "collar":
            return [
                Leg(strikes["put_strike"], "PE", "BUY",
                    _price(strikes["put_strike"], "PE"), 1, lot_size),
                Leg(strikes["call_strike"], "CE", "SELL",
                    _price(strikes["call_strike"], "CE"), 1, lot_size),
            ]

    except Exception:
        return []

    return []


def _build_rationale(
    signal: StrategySignal,
    condition: MarketCondition,
    analysis,
    ev: dict,
) -> str:
    """Build a human-readable rationale for the recommendation."""
    parts = [f"{signal.strategy.name} (score: {signal.score}/100, {signal.confidence})"]

    # Market context
    parts.append(f"Market: VIX={condition.vix:.1f}, IV rank={condition.iv_rank:.0f}, "
                 f"Trend={condition.trend.value}")

    # Top reasons
    top_reasons = [r for r in signal.reasons if "ideal" in r.lower() or "excellent" in r.lower()
                   or "aligns" in r.lower() or "suits" in r.lower()]
    if top_reasons:
        parts.append("Edge: " + "; ".join(top_reasons[:2]))

    # Expected value
    if ev.get("expected_pnl", 0) != 0:
        parts.append(f"Expected P&L: ₹{ev['expected_pnl']:,.0f} "
                     f"(PoP: {ev['prob_profit']:.0f}%)")

    # Risk
    mp = analysis.max_profit
    ml = analysis.max_loss
    mp_str = f"₹{mp:,.0f}" if mp != float("inf") else "Unlimited"
    ml_str = f"₹{abs(ml):,.0f}" if ml != float("-inf") else "Unlimited"
    parts.append(f"Risk: Max profit={mp_str}, Max loss={ml_str}")

    return " | ".join(parts)


def quick_recommendation(
    spot: float,
    vix: float,
    iv_rank: float,
    realized_vol: float,
    implied_vol: float,
    days_to_expiry: int = 7,
    trend: str = "neutral",
    capital: float = 500000.0,
    lot_size: int = 65,
    strike_step: float = 50.0,
    defined_risk_only: bool = True,
) -> list[dict]:
    """Simplified entry point for trade recommendations.

    Converts simple inputs to MarketCondition and returns
    structured recommendations. Ideal for MCP tool usage.

    Returns:
        List of recommendation dicts ready for display.
    """
    trend_map = {
        "strong_bullish": TrendDirection.STRONG_BULLISH,
        "bullish": TrendDirection.BULLISH,
        "neutral": TrendDirection.NEUTRAL,
        "bearish": TrendDirection.BEARISH,
        "strong_bearish": TrendDirection.STRONG_BEARISH,
    }

    condition = MarketCondition(
        spot=spot,
        vix=vix,
        iv_rank=iv_rank,
        iv_percentile=iv_rank,  # Approximate
        trend=trend_map.get(trend, TrendDirection.NEUTRAL),
        realized_vol=realized_vol,
        implied_vol=implied_vol,
        days_to_expiry=days_to_expiry,
    )

    recs = recommend_trades(
        condition,
        capital=capital,
        lot_size=lot_size,
        strike_step=strike_step,
        defined_risk_only=defined_risk_only,
    )

    results = []
    for rec in recs:
        mp = rec.max_profit
        ml = rec.max_loss

        results.append({
            "strategy": rec.strategy.name,
            "category": rec.strategy.category.value,
            "score": rec.signal.score,
            "confidence": rec.signal.confidence,
            "outlook": rec.strategy.outlook.value,
            "risk_profile": rec.strategy.risk_profile.value,
            "legs": [
                {
                    "strike": leg.strike,
                    "type": leg.option_type,
                    "action": leg.action,
                    "premium": round(leg.premium, 2),
                }
                for leg in rec.legs
            ],
            "strikes": {k: v for k, v in rec.strikes.items()
                        if k not in ("atm", "step")},
            "max_profit": round(mp, 2) if mp != float("inf") else "Unlimited",
            "max_loss": round(ml, 2) if ml != float("-inf") else "Unlimited",
            "breakevens": rec.breakevens,
            "risk_reward": round(rec.risk_reward, 2) if rec.risk_reward != float("inf") else "Unlimited",
            "net_premium": round(rec.net_premium, 2),
            "expected_pnl": round(rec.expected_pnl, 2),
            "prob_profit": round(rec.prob_profit, 1),
            "position_size": {
                "lots": rec.position_size.lots,
                "capital_at_risk": rec.position_size.capital_at_risk,
                "capital_at_risk_pct": rec.position_size.capital_at_risk_pct,
            },
            "margin_required": round(rec.margin_required, 2),
            "rationale": rec.rationale,
            "reasons": rec.signal.reasons,
        })

    return results
