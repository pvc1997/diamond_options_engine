"""Option strategy definitions — 18+ strategies with leg construction.

Each strategy is defined declaratively: its legs, category, market outlook,
ideal conditions, and risk profile. Strategies build Leg objects for payoff
analysis and margin estimation.

Strategy Categories:
- Directional: Profit from price movement (bullish/bearish)
- Neutral: Profit from range-bound markets or time decay
- Volatility: Profit from vol expansion or contraction
- Income: Systematic premium selling
- Hedge: Portfolio protection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from diamond_options.pricing.payoff import Leg


class StrategyCategory(str, Enum):
    DIRECTIONAL = "directional"
    NEUTRAL = "neutral"
    VOLATILITY = "volatility"
    INCOME = "income"
    HEDGE = "hedge"


class MarketOutlook(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    VOL_UP = "vol_up"         # Expect volatility increase
    VOL_DOWN = "vol_down"     # Expect volatility decrease


class RiskProfile(str, Enum):
    DEFINED = "defined"       # Max loss is capped
    UNDEFINED = "undefined"   # Unlimited loss possible


@dataclass(frozen=True)
class StrategySpec:
    """Complete specification of an option strategy."""
    name: str
    slug: str                              # Machine-readable ID
    category: StrategyCategory
    outlook: MarketOutlook
    risk_profile: RiskProfile
    num_legs: int
    description: str
    ideal_iv: str                          # "high", "low", "any"
    ideal_dte: str                         # "weekly", "monthly", "45dte", "any"
    vix_regimes: list[str] = field(default_factory=list)  # Suitable VIX regimes
    max_loss_type: str = ""                # "premium_paid", "spread_width", "unlimited"
    max_profit_type: str = ""              # "premium_received", "spread_width", "unlimited"
    tags: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# STRATEGY CATALOG
# ═══════════════════════════════════════════════════════════════

STRATEGIES: dict[str, StrategySpec] = {}


def _register(spec: StrategySpec) -> StrategySpec:
    STRATEGIES[spec.slug] = spec
    return spec


# --- Directional ---

LONG_CALL = _register(StrategySpec(
    name="Long Call",
    slug="long_call",
    category=StrategyCategory.DIRECTIONAL,
    outlook=MarketOutlook.BULLISH,
    risk_profile=RiskProfile.DEFINED,
    num_legs=1,
    description="Buy a call option. Profit from upside with limited risk.",
    ideal_iv="low",
    ideal_dte="monthly",
    vix_regimes=["low", "normal"],
    max_loss_type="premium_paid",
    max_profit_type="unlimited",
    tags=["beginner", "leverage"],
))

LONG_PUT = _register(StrategySpec(
    name="Long Put",
    slug="long_put",
    category=StrategyCategory.DIRECTIONAL,
    outlook=MarketOutlook.BEARISH,
    risk_profile=RiskProfile.DEFINED,
    num_legs=1,
    description="Buy a put option. Profit from downside with limited risk.",
    ideal_iv="low",
    ideal_dte="monthly",
    vix_regimes=["low", "normal"],
    max_loss_type="premium_paid",
    max_profit_type="unlimited",
    tags=["beginner", "hedge"],
))

BULL_CALL_SPREAD = _register(StrategySpec(
    name="Bull Call Spread",
    slug="bull_call_spread",
    category=StrategyCategory.DIRECTIONAL,
    outlook=MarketOutlook.BULLISH,
    risk_profile=RiskProfile.DEFINED,
    num_legs=2,
    description="Buy lower call, sell higher call. Reduced cost bullish play.",
    ideal_iv="any",
    ideal_dte="monthly",
    vix_regimes=["normal", "elevated"],
    max_loss_type="premium_paid",
    max_profit_type="spread_width",
    tags=["debit_spread", "popular"],
))

BEAR_PUT_SPREAD = _register(StrategySpec(
    name="Bear Put Spread",
    slug="bear_put_spread",
    category=StrategyCategory.DIRECTIONAL,
    outlook=MarketOutlook.BEARISH,
    risk_profile=RiskProfile.DEFINED,
    num_legs=2,
    description="Buy higher put, sell lower put. Reduced cost bearish play.",
    ideal_iv="any",
    ideal_dte="monthly",
    vix_regimes=["normal", "elevated"],
    max_loss_type="premium_paid",
    max_profit_type="spread_width",
    tags=["debit_spread"],
))

BULL_PUT_SPREAD = _register(StrategySpec(
    name="Bull Put Spread",
    slug="bull_put_spread",
    category=StrategyCategory.DIRECTIONAL,
    outlook=MarketOutlook.BULLISH,
    risk_profile=RiskProfile.DEFINED,
    num_legs=2,
    description="Sell higher put, buy lower put. Credit spread, profit if price stays above short strike.",
    ideal_iv="high",
    ideal_dte="weekly",
    vix_regimes=["elevated", "high"],
    max_loss_type="spread_width",
    max_profit_type="premium_received",
    tags=["credit_spread", "income", "popular"],
))

BEAR_CALL_SPREAD = _register(StrategySpec(
    name="Bear Call Spread",
    slug="bear_call_spread",
    category=StrategyCategory.DIRECTIONAL,
    outlook=MarketOutlook.BEARISH,
    risk_profile=RiskProfile.DEFINED,
    num_legs=2,
    description="Sell lower call, buy higher call. Credit spread, profit if price stays below short strike.",
    ideal_iv="high",
    ideal_dte="weekly",
    vix_regimes=["elevated", "high"],
    max_loss_type="spread_width",
    max_profit_type="premium_received",
    tags=["credit_spread", "income"],
))

# --- Neutral / Range-bound ---

SHORT_STRADDLE = _register(StrategySpec(
    name="Short Straddle",
    slug="short_straddle",
    category=StrategyCategory.NEUTRAL,
    outlook=MarketOutlook.NEUTRAL,
    risk_profile=RiskProfile.UNDEFINED,
    num_legs=2,
    description="Sell ATM call + ATM put. Max profit if price stays at strike. Unlimited risk.",
    ideal_iv="high",
    ideal_dte="weekly",
    vix_regimes=["elevated", "high"],
    max_loss_type="unlimited",
    max_profit_type="premium_received",
    tags=["income", "high_risk", "advanced"],
))

SHORT_STRANGLE = _register(StrategySpec(
    name="Short Strangle",
    slug="short_strangle",
    category=StrategyCategory.NEUTRAL,
    outlook=MarketOutlook.NEUTRAL,
    risk_profile=RiskProfile.UNDEFINED,
    num_legs=2,
    description="Sell OTM call + OTM put. Wider profit zone than straddle. Unlimited risk.",
    ideal_iv="high",
    ideal_dte="weekly",
    vix_regimes=["elevated", "high"],
    max_loss_type="unlimited",
    max_profit_type="premium_received",
    tags=["income", "high_risk", "popular"],
))

IRON_CONDOR = _register(StrategySpec(
    name="Iron Condor",
    slug="iron_condor",
    category=StrategyCategory.NEUTRAL,
    outlook=MarketOutlook.NEUTRAL,
    risk_profile=RiskProfile.DEFINED,
    num_legs=4,
    description="Bull put spread + bear call spread. Profit if price stays in range. Defined risk.",
    ideal_iv="high",
    ideal_dte="weekly",
    vix_regimes=["normal", "elevated", "high"],
    max_loss_type="spread_width",
    max_profit_type="premium_received",
    tags=["income", "popular", "defined_risk"],
))

IRON_BUTTERFLY = _register(StrategySpec(
    name="Iron Butterfly",
    slug="iron_butterfly",
    category=StrategyCategory.NEUTRAL,
    outlook=MarketOutlook.NEUTRAL,
    risk_profile=RiskProfile.DEFINED,
    num_legs=4,
    description="Short straddle + long wings. Defined risk version of straddle.",
    ideal_iv="high",
    ideal_dte="weekly",
    vix_regimes=["elevated", "high"],
    max_loss_type="spread_width",
    max_profit_type="premium_received",
    tags=["income", "defined_risk"],
))

# --- Volatility ---

LONG_STRADDLE = _register(StrategySpec(
    name="Long Straddle",
    slug="long_straddle",
    category=StrategyCategory.VOLATILITY,
    outlook=MarketOutlook.VOL_UP,
    risk_profile=RiskProfile.DEFINED,
    num_legs=2,
    description="Buy ATM call + ATM put. Profit from large move in either direction.",
    ideal_iv="low",
    ideal_dte="monthly",
    vix_regimes=["low", "normal"],
    max_loss_type="premium_paid",
    max_profit_type="unlimited",
    tags=["event_play", "earnings"],
))

LONG_STRANGLE = _register(StrategySpec(
    name="Long Strangle",
    slug="long_strangle",
    category=StrategyCategory.VOLATILITY,
    outlook=MarketOutlook.VOL_UP,
    risk_profile=RiskProfile.DEFINED,
    num_legs=2,
    description="Buy OTM call + OTM put. Cheaper than straddle, needs bigger move.",
    ideal_iv="low",
    ideal_dte="monthly",
    vix_regimes=["low", "normal"],
    max_loss_type="premium_paid",
    max_profit_type="unlimited",
    tags=["event_play"],
))

# --- Income ---

COVERED_CALL = _register(StrategySpec(
    name="Covered Call",
    slug="covered_call",
    category=StrategyCategory.INCOME,
    outlook=MarketOutlook.NEUTRAL,
    risk_profile=RiskProfile.DEFINED,
    num_legs=1,  # Option leg only (stock assumed held)
    description="Sell OTM call against stock holding. Income with upside cap.",
    ideal_iv="high",
    ideal_dte="monthly",
    vix_regimes=["normal", "elevated"],
    max_loss_type="stock_decline",
    max_profit_type="premium_plus_appreciation",
    tags=["income", "beginner", "stock_required"],
))

CASH_SECURED_PUT = _register(StrategySpec(
    name="Cash Secured Put",
    slug="cash_secured_put",
    category=StrategyCategory.INCOME,
    outlook=MarketOutlook.BULLISH,
    risk_profile=RiskProfile.DEFINED,
    num_legs=1,
    description="Sell OTM put with cash to buy shares. Income or cheaper entry.",
    ideal_iv="high",
    ideal_dte="monthly",
    vix_regimes=["normal", "elevated"],
    max_loss_type="assignment_risk",
    max_profit_type="premium_received",
    tags=["income", "beginner"],
))

JADE_LIZARD = _register(StrategySpec(
    name="Jade Lizard",
    slug="jade_lizard",
    category=StrategyCategory.INCOME,
    outlook=MarketOutlook.BULLISH,
    risk_profile=RiskProfile.DEFINED,
    num_legs=3,
    description="Short put + bear call spread. No upside risk if constructed properly.",
    ideal_iv="high",
    ideal_dte="monthly",
    vix_regimes=["elevated", "high"],
    max_loss_type="put_side",
    max_profit_type="premium_received",
    tags=["income", "advanced"],
))

# --- Hedge ---

PROTECTIVE_PUT = _register(StrategySpec(
    name="Protective Put",
    slug="protective_put",
    category=StrategyCategory.HEDGE,
    outlook=MarketOutlook.BEARISH,
    risk_profile=RiskProfile.DEFINED,
    num_legs=1,
    description="Buy put to protect long stock position. Insurance against crash.",
    ideal_iv="low",
    ideal_dte="monthly",
    vix_regimes=["low", "normal"],
    max_loss_type="premium_paid",
    max_profit_type="unlimited",
    tags=["hedge", "insurance"],
))

COLLAR = _register(StrategySpec(
    name="Collar",
    slug="collar",
    category=StrategyCategory.HEDGE,
    outlook=MarketOutlook.NEUTRAL,
    risk_profile=RiskProfile.DEFINED,
    num_legs=2,  # Option legs only (stock assumed held)
    description="Buy put + sell call around stock. Zero-cost or low-cost hedge.",
    ideal_iv="any",
    ideal_dte="monthly",
    vix_regimes=["normal", "elevated", "high"],
    max_loss_type="defined",
    max_profit_type="defined",
    tags=["hedge", "stock_required"],
))

RATIO_SPREAD = _register(StrategySpec(
    name="Ratio Spread",
    slug="ratio_spread",
    category=StrategyCategory.VOLATILITY,
    outlook=MarketOutlook.VOL_DOWN,
    risk_profile=RiskProfile.UNDEFINED,
    num_legs=3,
    description="Buy 1 ATM, sell 2 OTM (same type). Profit from moderate move + vol crush.",
    ideal_iv="high",
    ideal_dte="monthly",
    vix_regimes=["elevated", "high"],
    max_loss_type="unlimited_one_side",
    max_profit_type="spread_width_plus_credit",
    tags=["advanced", "vol_play"],
))


# ═══════════════════════════════════════════════════════════════
# LEG BUILDERS
# ═══════════════════════════════════════════════════════════════


def build_long_call(
    strike: float, premium: float, lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [Leg(strike, "CE", "BUY", premium, lots, lot_size)]


def build_long_put(
    strike: float, premium: float, lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [Leg(strike, "PE", "BUY", premium, lots, lot_size)]


def build_bull_call_spread(
    lower_strike: float, upper_strike: float,
    lower_premium: float, upper_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(lower_strike, "CE", "BUY", lower_premium, lots, lot_size),
        Leg(upper_strike, "CE", "SELL", upper_premium, lots, lot_size),
    ]


def build_bear_put_spread(
    upper_strike: float, lower_strike: float,
    upper_premium: float, lower_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(upper_strike, "PE", "BUY", upper_premium, lots, lot_size),
        Leg(lower_strike, "PE", "SELL", lower_premium, lots, lot_size),
    ]


def build_bull_put_spread(
    upper_strike: float, lower_strike: float,
    upper_premium: float, lower_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(upper_strike, "PE", "SELL", upper_premium, lots, lot_size),
        Leg(lower_strike, "PE", "BUY", lower_premium, lots, lot_size),
    ]


def build_bear_call_spread(
    lower_strike: float, upper_strike: float,
    lower_premium: float, upper_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(lower_strike, "CE", "SELL", lower_premium, lots, lot_size),
        Leg(upper_strike, "CE", "BUY", upper_premium, lots, lot_size),
    ]


def build_short_straddle(
    strike: float, call_premium: float, put_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(strike, "CE", "SELL", call_premium, lots, lot_size),
        Leg(strike, "PE", "SELL", put_premium, lots, lot_size),
    ]


def build_long_straddle(
    strike: float, call_premium: float, put_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(strike, "CE", "BUY", call_premium, lots, lot_size),
        Leg(strike, "PE", "BUY", put_premium, lots, lot_size),
    ]


def build_short_strangle(
    call_strike: float, put_strike: float,
    call_premium: float, put_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(call_strike, "CE", "SELL", call_premium, lots, lot_size),
        Leg(put_strike, "PE", "SELL", put_premium, lots, lot_size),
    ]


def build_long_strangle(
    call_strike: float, put_strike: float,
    call_premium: float, put_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(call_strike, "CE", "BUY", call_premium, lots, lot_size),
        Leg(put_strike, "PE", "BUY", put_premium, lots, lot_size),
    ]


def build_iron_condor(
    put_buy_strike: float, put_sell_strike: float,
    call_sell_strike: float, call_buy_strike: float,
    put_buy_premium: float, put_sell_premium: float,
    call_sell_premium: float, call_buy_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(put_buy_strike, "PE", "BUY", put_buy_premium, lots, lot_size),
        Leg(put_sell_strike, "PE", "SELL", put_sell_premium, lots, lot_size),
        Leg(call_sell_strike, "CE", "SELL", call_sell_premium, lots, lot_size),
        Leg(call_buy_strike, "CE", "BUY", call_buy_premium, lots, lot_size),
    ]


def build_iron_butterfly(
    strike: float, put_wing: float, call_wing: float,
    atm_call_premium: float, atm_put_premium: float,
    wing_call_premium: float, wing_put_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(put_wing, "PE", "BUY", wing_put_premium, lots, lot_size),
        Leg(strike, "PE", "SELL", atm_put_premium, lots, lot_size),
        Leg(strike, "CE", "SELL", atm_call_premium, lots, lot_size),
        Leg(call_wing, "CE", "BUY", wing_call_premium, lots, lot_size),
    ]


def build_ratio_spread(
    buy_strike: float, sell_strike: float,
    buy_premium: float, sell_premium: float,
    option_type: str = "CE",
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    """1x2 ratio spread: buy 1 ATM, sell 2 OTM."""
    return [
        Leg(buy_strike, option_type, "BUY", buy_premium, lots, lot_size),
        Leg(sell_strike, option_type, "SELL", sell_premium, lots * 2, lot_size),
    ]


def build_jade_lizard(
    put_strike: float, call_sell_strike: float, call_buy_strike: float,
    put_premium: float, call_sell_premium: float, call_buy_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(put_strike, "PE", "SELL", put_premium, lots, lot_size),
        Leg(call_sell_strike, "CE", "SELL", call_sell_premium, lots, lot_size),
        Leg(call_buy_strike, "CE", "BUY", call_buy_premium, lots, lot_size),
    ]


def build_collar(
    put_strike: float, call_strike: float,
    put_premium: float, call_premium: float,
    lots: int = 1, lot_size: int = 65,
) -> list[Leg]:
    return [
        Leg(put_strike, "PE", "BUY", put_premium, lots, lot_size),
        Leg(call_strike, "CE", "SELL", call_premium, lots, lot_size),
    ]


# ═══════════════════════════════════════════════════════════════
# LOOKUPS
# ═══════════════════════════════════════════════════════════════


# Map slug → builder function
BUILDERS: dict[str, callable] = {
    "long_call": build_long_call,
    "long_put": build_long_put,
    "bull_call_spread": build_bull_call_spread,
    "bear_put_spread": build_bear_put_spread,
    "bull_put_spread": build_bull_put_spread,
    "bear_call_spread": build_bear_call_spread,
    "short_straddle": build_short_straddle,
    "long_straddle": build_long_straddle,
    "short_strangle": build_short_strangle,
    "long_strangle": build_long_strangle,
    "iron_condor": build_iron_condor,
    "iron_butterfly": build_iron_butterfly,
    "ratio_spread": build_ratio_spread,
    "jade_lizard": build_jade_lizard,
    "collar": build_collar,
}


def get_strategy(slug: str) -> StrategySpec | None:
    return STRATEGIES.get(slug)


def list_strategies(
    category: StrategyCategory | None = None,
    outlook: MarketOutlook | None = None,
    risk_profile: RiskProfile | None = None,
) -> list[StrategySpec]:
    """Filter strategies by criteria."""
    result = list(STRATEGIES.values())
    if category:
        result = [s for s in result if s.category == category]
    if outlook:
        result = [s for s in result if s.outlook == outlook]
    if risk_profile:
        result = [s for s in result if s.risk_profile == risk_profile]
    return result


def strategies_for_regime(vix_regime: str) -> list[StrategySpec]:
    """Return strategies suitable for a given VIX regime."""
    return [s for s in STRATEGIES.values() if vix_regime in s.vix_regimes]
