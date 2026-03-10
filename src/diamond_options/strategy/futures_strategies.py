"""Futures strategy definitions — pure futures and hybrid (futures + options).

Each strategy is defined declaratively with category, outlook, ideal conditions,
and risk profile. Futures strategies differ from options in:
- Linear payoff (no strike, no premium in the options sense)
- Margin-based (not premium-based)
- Delta always ±1.0 per lot
- Calendar spreads reduce margin via offset

Strategy Categories:
- Directional: Long/short futures for trend following
- Spread: Calendar spreads for carry/roll yield
- Arbitrage: Cash-futures, conversion/reversal
- Hedge: Portfolio hedging with futures
- Hybrid: Futures + options combinations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FuturesStrategyCategory(str, Enum):
    DIRECTIONAL = "directional"
    SPREAD = "spread"
    ARBITRAGE = "arbitrage"
    HEDGE = "hedge"
    HYBRID = "hybrid"


class FuturesOutlook(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    CARRY = "carry"  # Profit from basis/roll yield


class FuturesRiskProfile(str, Enum):
    UNLIMITED = "unlimited"  # Naked long/short
    DEFINED = "defined"  # Spread or hedged
    LOW_RISK = "low_risk"  # Arbitrage


@dataclass(frozen=True)
class FuturesStrategySpec:
    """Complete specification of a futures strategy."""

    name: str
    slug: str
    category: FuturesStrategyCategory
    outlook: FuturesOutlook
    risk_profile: FuturesRiskProfile
    num_legs: int  # Number of instrument legs
    description: str
    margin_type: str  # "full" or "spread" (reduced margin)
    ideal_basis_regime: str  # "contango", "backwardation", "any"
    ideal_vix_regime: list[str] = field(default_factory=list)
    ideal_dte_range: tuple[int, int] = (0, 90)  # (min, max) DTE
    tags: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# STRATEGY CATALOG
# ═══════════════════════════════════════════════════════════════

FUTURES_STRATEGIES: dict[str, FuturesStrategySpec] = {}


def _register(spec: FuturesStrategySpec) -> FuturesStrategySpec:
    FUTURES_STRATEGIES[spec.slug] = spec
    return spec


# --- Directional ---

LONG_FUTURES = _register(FuturesStrategySpec(
    name="Long Futures",
    slug="long_futures",
    category=FuturesStrategyCategory.DIRECTIONAL,
    outlook=FuturesOutlook.BULLISH,
    risk_profile=FuturesRiskProfile.UNLIMITED,
    num_legs=1,
    description="Buy futures. Delta +1.0 per lot. Unlimited profit/loss. "
    "Lower cost of entry than buying stock (margin vs. full price).",
    margin_type="full",
    ideal_basis_regime="any",
    ideal_vix_regime=["low", "normal", "elevated"],
    ideal_dte_range=(5, 60),
    tags=["beginner", "trend", "leverage"],
))

SHORT_FUTURES = _register(FuturesStrategySpec(
    name="Short Futures",
    slug="short_futures",
    category=FuturesStrategyCategory.DIRECTIONAL,
    outlook=FuturesOutlook.BEARISH,
    risk_profile=FuturesRiskProfile.UNLIMITED,
    num_legs=1,
    description="Sell futures. Delta -1.0 per lot. Unlimited profit/loss. "
    "Only way to short stocks in India without delivery obligation.",
    margin_type="full",
    ideal_basis_regime="any",
    ideal_vix_regime=["elevated", "high"],
    ideal_dte_range=(5, 60),
    tags=["trend", "leverage", "bearish"],
))

# --- Spread ---

CALENDAR_SPREAD_BULL = _register(FuturesStrategySpec(
    name="Calendar Spread (Bull)",
    slug="calendar_spread_bull",
    category=FuturesStrategyCategory.SPREAD,
    outlook=FuturesOutlook.CARRY,
    risk_profile=FuturesRiskProfile.DEFINED,
    num_legs=2,
    description="Long near-month, short far-month. Profits when contango narrows "
    "(basis compression). Reduced margin (~30% of full). Captures roll yield.",
    margin_type="spread",
    ideal_basis_regime="contango",
    ideal_vix_regime=["normal", "elevated"],
    ideal_dte_range=(5, 30),
    tags=["carry", "low_risk", "intermediate"],
))

CALENDAR_SPREAD_BEAR = _register(FuturesStrategySpec(
    name="Calendar Spread (Bear)",
    slug="calendar_spread_bear",
    category=FuturesStrategyCategory.SPREAD,
    outlook=FuturesOutlook.CARRY,
    risk_profile=FuturesRiskProfile.DEFINED,
    num_legs=2,
    description="Short near-month, long far-month. Profits when contango widens "
    "or backwardation deepens. Reduced margin.",
    margin_type="spread",
    ideal_basis_regime="backwardation",
    ideal_vix_regime=["normal", "elevated"],
    ideal_dte_range=(5, 30),
    tags=["carry", "low_risk", "intermediate"],
))

FUTURES_ROLLOVER = _register(FuturesStrategySpec(
    name="Futures Rollover",
    slug="futures_rollover",
    category=FuturesStrategyCategory.SPREAD,
    outlook=FuturesOutlook.NEUTRAL,
    risk_profile=FuturesRiskProfile.DEFINED,
    num_legs=2,
    description="Close near-month, open next-month. Manages ongoing positions "
    "through expiry. Timing matters — roll when basis is favorable.",
    margin_type="spread",
    ideal_basis_regime="any",
    ideal_vix_regime=["low", "normal", "elevated", "high"],
    ideal_dte_range=(0, 5),
    tags=["maintenance", "roll"],
))

# --- Arbitrage ---

CASH_FUTURES_ARBITRAGE = _register(FuturesStrategySpec(
    name="Cash-Futures Arbitrage",
    slug="cash_futures_arb",
    category=FuturesStrategyCategory.ARBITRAGE,
    outlook=FuturesOutlook.NEUTRAL,
    risk_profile=FuturesRiskProfile.LOW_RISK,
    num_legs=2,
    description="Buy spot, sell futures when basis > fair value. Lock in risk-free return "
    "equal to the basis. Requires cash leg (equity delivery). Popular with institutions.",
    margin_type="full",
    ideal_basis_regime="contango",
    ideal_vix_regime=["low", "normal", "elevated", "high", "crisis"],
    ideal_dte_range=(10, 60),
    tags=["arbitrage", "institutional", "low_risk"],
))

# --- Hedge ---

INDEX_FUTURES_HEDGE = _register(FuturesStrategySpec(
    name="Index Futures Hedge",
    slug="index_futures_hedge",
    category=FuturesStrategyCategory.HEDGE,
    outlook=FuturesOutlook.BEARISH,
    risk_profile=FuturesRiskProfile.DEFINED,
    num_legs=1,
    description="Short NIFTY/BANKNIFTY futures to hedge equity portfolio. "
    "Number of lots = portfolio_value × beta / lot_notional. Full delta hedge.",
    margin_type="full",
    ideal_basis_regime="any",
    ideal_vix_regime=["elevated", "high", "crisis"],
    ideal_dte_range=(5, 60),
    tags=["hedge", "portfolio", "institutional"],
))

STOCK_FUTURES_HEDGE = _register(FuturesStrategySpec(
    name="Stock Futures Hedge",
    slug="stock_futures_hedge",
    category=FuturesStrategyCategory.HEDGE,
    outlook=FuturesOutlook.BEARISH,
    risk_profile=FuturesRiskProfile.DEFINED,
    num_legs=1,
    description="Short individual stock futures to hedge stock holding. "
    "Perfect hedge if shares = lots × lot_size. No basis risk.",
    margin_type="full",
    ideal_basis_regime="any",
    ideal_vix_regime=["elevated", "high", "crisis"],
    ideal_dte_range=(5, 60),
    tags=["hedge", "single_stock"],
))

PAIR_TRADE = _register(FuturesStrategySpec(
    name="Pair Trade",
    slug="pair_trade",
    category=FuturesStrategyCategory.HEDGE,
    outlook=FuturesOutlook.NEUTRAL,
    risk_profile=FuturesRiskProfile.DEFINED,
    num_legs=2,
    description="Long one futures, short another (same sector or correlated). "
    "Market-neutral — profits from relative value convergence. "
    "E.g., long HDFCBANK, short ICICIBANK.",
    margin_type="full",
    ideal_basis_regime="any",
    ideal_vix_regime=["normal", "elevated"],
    ideal_dte_range=(10, 60),
    tags=["pairs", "market_neutral", "advanced"],
))

# --- Hybrid (Futures + Options) ---

SYNTHETIC_LONG = _register(FuturesStrategySpec(
    name="Synthetic Long (Futures + Put)",
    slug="synthetic_long",
    category=FuturesStrategyCategory.HYBRID,
    outlook=FuturesOutlook.BULLISH,
    risk_profile=FuturesRiskProfile.DEFINED,
    num_legs=2,
    description="Long futures + long put. Unlimited upside like long futures, "
    "but downside capped at put strike. Like a long call but with full delta.",
    margin_type="full",
    ideal_basis_regime="any",
    ideal_vix_regime=["normal", "elevated"],
    ideal_dte_range=(10, 45),
    tags=["hybrid", "protected", "intermediate"],
))

SYNTHETIC_SHORT = _register(FuturesStrategySpec(
    name="Synthetic Short (Futures + Call)",
    slug="synthetic_short",
    category=FuturesStrategyCategory.HYBRID,
    outlook=FuturesOutlook.BEARISH,
    risk_profile=FuturesRiskProfile.DEFINED,
    num_legs=2,
    description="Short futures + long call. Unlimited downside profit, "
    "but upside risk capped at call strike. Like a long put but with full delta.",
    margin_type="full",
    ideal_basis_regime="any",
    ideal_vix_regime=["elevated", "high"],
    ideal_dte_range=(10, 45),
    tags=["hybrid", "protected", "intermediate"],
))

FUTURES_WITH_COVERED_CALL = _register(FuturesStrategySpec(
    name="Futures with Covered Call",
    slug="futures_covered_call",
    category=FuturesStrategyCategory.HYBRID,
    outlook=FuturesOutlook.BULLISH,
    risk_profile=FuturesRiskProfile.UNLIMITED,
    num_legs=2,
    description="Long futures + sell OTM call. Generates income on long position. "
    "Caps upside at call strike but reduces cost basis.",
    margin_type="full",
    ideal_basis_regime="any",
    ideal_vix_regime=["normal", "elevated", "high"],
    ideal_dte_range=(7, 30),
    tags=["hybrid", "income", "intermediate"],
))

FUTURES_WITH_PROTECTIVE_PUT = _register(FuturesStrategySpec(
    name="Futures with Protective Put",
    slug="futures_protective_put",
    category=FuturesStrategyCategory.HYBRID,
    outlook=FuturesOutlook.BULLISH,
    risk_profile=FuturesRiskProfile.DEFINED,
    num_legs=2,
    description="Long futures + buy OTM put. Full upside participation with "
    "insurance against large drop. Put premium is the cost of protection.",
    margin_type="full",
    ideal_basis_regime="any",
    ideal_vix_regime=["normal", "elevated"],
    ideal_dte_range=(10, 45),
    tags=["hybrid", "protected", "beginner"],
))

CONVERSION = _register(FuturesStrategySpec(
    name="Conversion",
    slug="conversion",
    category=FuturesStrategyCategory.ARBITRAGE,
    outlook=FuturesOutlook.NEUTRAL,
    risk_profile=FuturesRiskProfile.LOW_RISK,
    num_legs=3,
    description="Long futures + long put + short call (same strike). "
    "Locks in risk-free rate if mispriced. Arbitrage strategy.",
    margin_type="spread",
    ideal_basis_regime="contango",
    ideal_vix_regime=["low", "normal", "elevated", "high", "crisis"],
    ideal_dte_range=(10, 60),
    tags=["arbitrage", "advanced", "institutional"],
))

REVERSAL = _register(FuturesStrategySpec(
    name="Reversal",
    slug="reversal",
    category=FuturesStrategyCategory.ARBITRAGE,
    outlook=FuturesOutlook.NEUTRAL,
    risk_profile=FuturesRiskProfile.LOW_RISK,
    num_legs=3,
    description="Short futures + long call + short put (same strike). "
    "Opposite of conversion. Exploits put-call parity violations.",
    margin_type="spread",
    ideal_basis_regime="backwardation",
    ideal_vix_regime=["low", "normal", "elevated", "high", "crisis"],
    ideal_dte_range=(10, 60),
    tags=["arbitrage", "advanced", "institutional"],
))


# ═══════════════════════════════════════════════════════════════
# LOOKUPS
# ═══════════════════════════════════════════════════════════════


def get_futures_strategy(slug: str) -> FuturesStrategySpec | None:
    return FUTURES_STRATEGIES.get(slug)


def list_futures_strategies(
    category: FuturesStrategyCategory | None = None,
    outlook: FuturesOutlook | None = None,
    risk_profile: FuturesRiskProfile | None = None,
) -> list[FuturesStrategySpec]:
    """Filter futures strategies by criteria."""
    result = list(FUTURES_STRATEGIES.values())
    if category:
        result = [s for s in result if s.category == category]
    if outlook:
        result = [s for s in result if s.outlook == outlook]
    if risk_profile:
        result = [s for s in result if s.risk_profile == risk_profile]
    return result


def futures_strategies_for_regime(vix_regime: str) -> list[FuturesStrategySpec]:
    """Return futures strategies suitable for a given VIX regime."""
    return [
        s for s in FUTURES_STRATEGIES.values()
        if vix_regime in s.ideal_vix_regime
    ]
