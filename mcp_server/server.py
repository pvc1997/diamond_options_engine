"""MCP Server for Diamond Options Engine.

Exposes options analysis and trading tools to Claude Code via FastMCP.
Phase 1: Foundation tools — chain data, universe, expiry, costs, portfolio status.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Ensure src is importable
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Diamond Options Engine")


# ═══════════════════════════════════════════════════════════════
# UNIVERSE & EXPIRY
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def fno_universe(sector: str = "") -> dict:
    """List all F&O-permitted stocks with lot sizes.

    Args:
        sector: Optional sector filter (e.g., "Technology", "Financial Services").

    Returns:
        List of F&O stocks with symbol, lot_size, sector.
    """
    from diamond_options.data.universe import FNO_STOCKS, get_fno_by_sector

    stocks = get_fno_by_sector(sector) if sector else FNO_STOCKS
    return {
        "count": len(stocks),
        "stocks": [
            {"symbol": s.symbol, "lot_size": s.lot_size, "sector": s.sector}
            for s in stocks
        ],
    }


@mcp.tool()
def index_contracts() -> dict:
    """Show index F&O contract specs (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY)."""
    from diamond_options.data.universe import INDEX_CONTRACTS
    return INDEX_CONTRACTS


@mcp.tool()
def lot_size(symbol: str) -> dict:
    """Get lot size for an F&O stock or index.

    Args:
        symbol: NSE symbol (e.g., RELIANCE, NIFTY, BANKNIFTY).
    """
    from diamond_options.data.universe import get_lot_size, get_index_lot_size, is_fno_stock

    sym = symbol.upper()
    idx_lot = get_index_lot_size(sym)
    if idx_lot > 0:
        return {"symbol": sym, "lot_size": idx_lot, "type": "index"}

    stock_lot = get_lot_size(sym)
    if stock_lot > 0:
        return {"symbol": sym, "lot_size": stock_lot, "type": "stock"}

    return {"symbol": sym, "lot_size": 0, "error": f"{sym} not in F&O universe"}


@mcp.tool()
def search_fno(query: str) -> dict:
    """Search F&O stocks by symbol prefix.

    Args:
        query: Search prefix (e.g., "REL", "TAT", "BANK").
    """
    from diamond_options.data.universe import search_symbol

    results = search_symbol(query)
    return {
        "query": query,
        "count": len(results),
        "matches": [
            {"symbol": s.symbol, "lot_size": s.lot_size, "sector": s.sector}
            for s in results
        ],
    }


@mcp.tool()
def upcoming_expiries(count: int = 8, weekly: bool = True) -> dict:
    """Show upcoming F&O expiry dates.

    Args:
        count: Number of expiries to show (default 8).
        weekly: Include weekly expiries (True) or monthly only (False).
    """
    from diamond_options.data.expiry import (
        upcoming_expiries as _upcoming,
        expiry_label,
        classify_expiry,
        days_to_expiry,
    )

    expiries = _upcoming(count=count, weekly=weekly)
    today = date.today()

    return {
        "expiries": [
            {
                "date": exp.isoformat(),
                "label": expiry_label(exp),
                "type": classify_expiry(exp),
                "days": days_to_expiry(exp, today),
            }
            for exp in expiries
        ]
    }


@mcp.tool()
def is_expiry_today() -> dict:
    """Check if today is an F&O expiry day."""
    from diamond_options.data.expiry import is_expiry_day, next_weekly_expiry, days_to_expiry

    today = date.today()
    is_exp = is_expiry_day(today)
    next_exp = next_weekly_expiry(today if not is_exp else None)

    return {
        "is_expiry_day": is_exp,
        "today": today.isoformat(),
        "next_expiry": next_exp.isoformat(),
        "days_to_next": days_to_expiry(next_exp, today),
    }


# ═══════════════════════════════════════════════════════════════
# OPTIONS CHAIN
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def options_chain_summary(symbol: str, num_strikes: int = 10) -> dict:
    """Get options chain summary for a symbol.

    Shows ATM strike, PCR, max pain, OI summary.
    Uses yfinance spot price with synthetic chain (use build_live_chain for Kite data).

    Args:
        symbol: Underlying (e.g., NIFTY, RELIANCE).
        num_strikes: OTM strikes per side (default 10).
    """
    from diamond_options.data.options_chain import generate_strikes, build_synthetic_chain
    from diamond_options.data.expiry import next_weekly_expiry
    from diamond_options.data.universe import INDEX_CONTRACTS
    from diamond_options.data.market import get_spot_price as _get_spot

    sym = symbol.upper()
    if sym in INDEX_CONTRACTS:
        step = 50 if sym == "NIFTY" else 100
    else:
        step = 50

    spot = _get_spot(sym)
    if spot is None:
        # Fallback defaults
        spot = 24000.0 if sym == "NIFTY" else 50000.0 if sym == "BANKNIFTY" else 1000.0

    expiry = next_weekly_expiry()
    strikes = generate_strikes(spot, step, num_strikes)
    chain = build_synthetic_chain(sym, spot, expiry, strikes)

    result = chain.summary()
    result["data_source"] = "yfinance" if _get_spot(sym) else "fallback"
    result["note"] = "Synthetic chain. Use build_live_chain with Kite quotes for live OI data."
    return result


@mcp.tool()
def max_pain(symbol: str) -> dict:
    """Calculate max pain strike for a symbol.

    Max pain is the strike where option writers lose the least money.
    Useful for understanding where price tends to gravitate near expiry.

    Args:
        symbol: Underlying (e.g., NIFTY).
    """
    from diamond_options.data.options_chain import generate_strikes, build_synthetic_chain
    from diamond_options.data.expiry import next_weekly_expiry
    from diamond_options.data.market import get_spot_price as _get_spot

    sym = symbol.upper()
    step = 50 if sym == "NIFTY" else 100

    spot = _get_spot(sym)
    if spot is None:
        spot = 24000.0 if sym == "NIFTY" else 50000.0 if sym == "BANKNIFTY" else 1000.0

    expiry = next_weekly_expiry()
    strikes = generate_strikes(spot, step, 15)
    chain = build_synthetic_chain(sym, spot, expiry, strikes)

    return {
        "symbol": sym,
        "spot": spot,
        "max_pain": chain.max_pain(),
        "expiry": expiry.isoformat(),
        "note": "Synthetic OI. Use live_oi_analysis with Kite data for real max pain.",
    }


# ═══════════════════════════════════════════════════════════════
# COSTS
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def options_costs(action: str, premium_amount: float, is_index: bool = False) -> dict:
    """Calculate options transaction costs for Indian markets.

    Shows itemized breakdown: brokerage, GST, STT, exchange fees, SEBI, stamp duty, slippage.

    Args:
        action: BUY or SELL.
        premium_amount: Total premium in INR (price * lot_size * lots).
        is_index: Whether this is an index option.
    """
    from diamond_options.data.costs import calculate_options_costs
    from dataclasses import asdict

    cost = calculate_options_costs(action.upper(), premium_amount, is_index)
    return asdict(cost)


@mcp.tool()
def spread_costs(legs: list[dict]) -> dict:
    """Calculate total round-trip costs for a multi-leg options spread.

    Args:
        legs: List of legs, each with keys: action, premium_amount, is_index.
              Example: [{"action": "BUY", "premium_amount": 3250}, {"action": "SELL", "premium_amount": 2000}]
    """
    from diamond_options.data.costs import spread_round_trip_cost

    total = spread_round_trip_cost(legs)
    return {
        "num_legs": len(legs),
        "total_orders": len(legs) * 2,  # Open + close
        "round_trip_cost": total,
    }


# ═══════════════════════════════════════════════════════════════
# PORTFOLIO
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def portfolio_status(ledger_name: str = "default") -> dict:
    """Show options portfolio status — positions, cash, margin, P&L.

    Args:
        ledger_name: Ledger name (default: "default", use "paper" for paper trading).
    """
    from diamond_options.data.ledger import OptionsLedger
    from diamond_options.utils.formatters import fmt_inr

    ledger = OptionsLedger(name=ledger_name)
    positions = ledger.get_positions()
    cash = ledger.get_cash()
    margin = ledger.get_margin_used()
    capital = ledger.get_initial_capital()

    return {
        "ledger": ledger_name,
        "cash": cash,
        "cash_fmt": fmt_inr(cash),
        "margin_used": margin,
        "margin_fmt": fmt_inr(margin),
        "initial_capital": capital,
        "open_positions": len(positions),
        "total_fees": ledger.get_total_fees(),
        "positions": [
            {
                "symbol": p.symbol,
                "strike": p.strike,
                "type": p.option_type,
                "expiry": p.expiry,
                "lots": p.lots,
                "lot_size": p.lot_size,
                "avg_price": p.avg_price,
                "direction": "LONG" if p.is_long else "SHORT",
                "strategy": p.strategy_tag,
                "group": p.trade_group,
            }
            for p in positions
        ],
    }


@mcp.tool()
def trade_history(ledger_name: str = "default", since: str = "") -> dict:
    """Show options trade history.

    Args:
        ledger_name: Ledger name.
        since: ISO date to filter from (e.g., "2026-03-01").
    """
    from diamond_options.data.ledger import OptionsLedger

    ledger = OptionsLedger(name=ledger_name)
    trades = ledger.get_trades(since=since or None)

    return {
        "ledger": ledger_name,
        "count": len(trades),
        "trades": [
            {
                "timestamp": t.timestamp,
                "action": t.action,
                "symbol": t.symbol,
                "strike": t.strike,
                "type": t.option_type,
                "expiry": t.expiry,
                "lots": t.lots,
                "price": t.price,
                "cost": t.total_cost,
                "strategy": t.strategy_tag,
                "group": t.trade_group,
                "rationale": t.rationale,
            }
            for t in trades
        ],
    }


# ═══════════════════════════════════════════════════════════════
# MARKET
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def market_status() -> dict:
    """Check if NSE is currently open and show next trading session."""
    from diamond_options.utils.indian_markets import (
        is_market_open,
        next_trading_day,
        is_trading_day,
    )
    from diamond_options.data.expiry import is_expiry_day, next_weekly_expiry
    from datetime import datetime

    now = datetime.now()
    today = now.date()

    return {
        "is_open": is_market_open(now),
        "is_trading_day": is_trading_day(today),
        "is_expiry_day": is_expiry_day(today),
        "next_trading_day": next_trading_day().isoformat(),
        "next_expiry": next_weekly_expiry().isoformat(),
        "timestamp": now.isoformat(),
    }


# ═══════════════════════════════════════════════════════════════
# PRICING & GREEKS (Phase 2)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def price_option(
    spot: float,
    strike: float,
    days_to_expiry: int,
    volatility: float,
    option_type: str,
    risk_free_rate: float = 0.065,
) -> dict:
    """Price a European option using Black-Scholes.

    Args:
        spot: Current underlying price.
        strike: Strike price.
        days_to_expiry: Calendar days to expiry.
        volatility: Implied/historical volatility (e.g., 0.15 for 15%).
        option_type: CE (call) or PE (put).
        risk_free_rate: Annual risk-free rate (default 6.5%).

    Returns:
        Price, intrinsic value, time value, d1, d2.
    """
    from diamond_options.pricing.black_scholes import price_option as _price
    from dataclasses import asdict

    T = days_to_expiry / 365.0
    result = _price(spot, strike, T, risk_free_rate, volatility, option_type)

    return {
        "option_type": option_type.upper(),
        "spot": spot,
        "strike": strike,
        "days_to_expiry": days_to_expiry,
        "volatility": volatility,
        "price": round(result.price, 2),
        "intrinsic": round(result.intrinsic, 2),
        "time_value": round(result.time_value, 2),
    }


@mcp.tool()
def calculate_greeks(
    spot: float,
    strike: float,
    days_to_expiry: int,
    volatility: float,
    option_type: str,
    risk_free_rate: float = 0.065,
    lot_size: int = 65,
) -> dict:
    """Calculate all Greeks for an option.

    Shows delta, gamma, theta, vega, rho + per-lot values.

    Args:
        spot: Underlying price.
        strike: Strike price.
        days_to_expiry: Calendar days to expiry.
        volatility: IV (e.g., 0.15 for 15%).
        option_type: CE or PE.
        risk_free_rate: Risk-free rate.
        lot_size: For per-lot calculations (default 25 for NIFTY).

    Returns:
        Greeks per-share and per-lot.
    """
    from diamond_options.pricing.greeks import calculate_greeks as _calc
    from diamond_options.pricing.greeks import probability_itm

    T = days_to_expiry / 365.0
    g = _calc(spot, strike, T, risk_free_rate, volatility, option_type)
    p_itm = probability_itm(spot, strike, T, risk_free_rate, volatility, option_type)

    return {
        "option_type": option_type.upper(),
        "per_share": {
            "delta": g.delta,
            "gamma": g.gamma,
            "theta": g.theta,
            "vega": g.vega,
            "rho": g.rho,
            "vanna": g.vanna,
            "charm": g.charm,
        },
        "per_lot": {
            "delta": round(g.delta * lot_size, 2),
            "gamma": round(g.gamma * lot_size, 4),
            "theta": round(g.theta * lot_size, 2),
            "vega": round(g.vega * lot_size, 2),
        },
        "probability_itm": round(p_itm * 100, 1),
        "lot_size": lot_size,
    }


@mcp.tool()
def solve_iv(
    market_price: float,
    spot: float,
    strike: float,
    days_to_expiry: int,
    option_type: str,
    risk_free_rate: float = 0.065,
) -> dict:
    """Calculate Implied Volatility from market price.

    Uses Newton-Raphson method to find the volatility that produces
    the observed market price in the Black-Scholes model.

    Args:
        market_price: Observed option premium.
        spot: Underlying price.
        strike: Strike price.
        days_to_expiry: Calendar days to expiry.
        option_type: CE or PE.
        risk_free_rate: Risk-free rate.

    Returns:
        Implied volatility and related metrics.
    """
    from diamond_options.pricing.implied_volatility import implied_volatility
    from diamond_options.pricing.greeks import probability_itm

    T = days_to_expiry / 365.0
    iv = implied_volatility(market_price, spot, strike, T, risk_free_rate, option_type)

    if iv is None:
        return {
            "error": "Could not converge on IV — check inputs",
            "market_price": market_price,
            "spot": spot,
            "strike": strike,
        }

    p_itm = probability_itm(spot, strike, T, risk_free_rate, iv, option_type)

    return {
        "implied_volatility": round(iv, 4),
        "iv_pct": f"{iv * 100:.1f}%",
        "market_price": market_price,
        "spot": spot,
        "strike": strike,
        "days_to_expiry": days_to_expiry,
        "option_type": option_type.upper(),
        "probability_itm": round(p_itm * 100, 1),
        "moneyness": round(strike / spot, 4),
    }


@mcp.tool()
def analyze_payoff(
    legs: list[dict],
    spot: float,
    lot_size: int = 65,
) -> dict:
    """Analyze payoff for a multi-leg options position.

    Shows max profit, max loss, breakevens, risk-reward ratio, and expected value.

    Args:
        legs: List of legs, each with: strike, option_type (CE/PE), action (BUY/SELL), premium.
        spot: Current underlying price.
        lot_size: Lot size (default 25 for NIFTY).

    Example legs for bull call spread:
    [
        {"strike": 22400, "option_type": "CE", "action": "BUY", "premium": 195},
        {"strike": 22600, "option_type": "CE", "action": "SELL", "premium": 80}
    ]

    Returns:
        Max profit/loss, breakevens, risk-reward, net premium, expected P&L.
    """
    from diamond_options.pricing.payoff import (
        Leg, analyze_payoff as _analyze, expected_value,
    )

    option_legs = [
        Leg(
            strike=l["strike"],
            option_type=l["option_type"],
            action=l["action"],
            premium=l["premium"],
            lots=l.get("lots", 1),
            lot_size=lot_size,
        )
        for l in legs
    ]

    analysis = _analyze(option_legs, spot)
    ev = expected_value(option_legs, spot, T=7 / 365, r=0.065, sigma=0.13)

    mp = analysis.max_profit
    ml = analysis.max_loss

    return {
        "max_profit": mp if mp != float("inf") else "Unlimited",
        "max_loss": ml if ml != float("-inf") else "Unlimited",
        "breakevens": analysis.breakevens,
        "risk_reward": analysis.risk_reward if analysis.risk_reward != float("inf") else "Unlimited",
        "net_premium": analysis.net_premium,
        "margin_required": analysis.margin_required,
        "expected_pnl": ev["expected_pnl"],
        "prob_profit": ev["prob_profit"],
        "var_95": ev["var_95"],
    }


# ═══════════════════════════════════════════════════════════════
# VOLATILITY (Phase 2)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def iv_rank_analysis(current_iv: float, historical_ivs: list[float]) -> dict:
    """Analyze IV rank and percentile relative to historical data.

    IV Rank shows where current IV sits within its 1-year range (0=low, 100=high).
    IV Percentile shows what % of days had lower IV.

    High IV rank (>50) → premium selling opportunities
    Low IV rank (<20) → premium buying opportunities

    Args:
        current_iv: Current ATM implied volatility (decimal, e.g., 0.15).
        historical_ivs: List of historical daily IV values (ideally 252 for 1 year).

    Returns:
        IV rank, percentile, regime, and statistics.
    """
    from diamond_options.pricing.iv_surface import iv_rank as _rank
    from dataclasses import asdict

    result = _rank(current_iv, historical_ivs)
    return asdict(result)


@mcp.tool()
def vix_analysis(vix_value: float) -> dict:
    """Analyze India VIX and determine trading regime.

    Classifies VIX into regimes (low/normal/elevated/high/crisis)
    and provides strategy guidance and position sizing recommendations.

    Args:
        vix_value: Current India VIX value.

    Returns:
        Regime, strategy bias, position sizing, and actionable notes.
    """
    from diamond_options.volatility.vix import classify_regime, vix_mean_reversion_signal
    from dataclasses import asdict

    regime = classify_regime(vix_value)
    signal = vix_mean_reversion_signal(vix_value)

    return {
        **asdict(regime),
        "mean_reversion": signal,
    }


@mcp.tool()
def variance_risk_premium(implied_vol: float, realized_vol: float) -> dict:
    """Calculate Variance Risk Premium (VRP).

    Compares implied volatility (what market expects) vs realized volatility
    (what actually happened). Positive spread means options are "expensive".

    VRP is the structural edge that option sellers exploit.

    Args:
        implied_vol: Current ATM IV (decimal).
        realized_vol: Current realized vol (decimal).

    Returns:
        Vol spread, signal (options_expensive/cheap/fair), and action.
    """
    from diamond_options.volatility.forecast import variance_risk_premium as _vrp

    return _vrp(implied_vol, realized_vol)


@mcp.tool()
def put_call_parity(
    call_price: float,
    put_price: float,
    spot: float,
    strike: float,
    days_to_expiry: int,
    risk_free_rate: float = 0.065,
) -> dict:
    """Check put-call parity for arbitrage detection.

    C - P should equal S - K*e^(-rT). Deviation > 1% may indicate
    mispricing or arbitrage opportunity.

    Args:
        call_price: Market call premium.
        put_price: Market put premium.
        spot: Underlying price.
        strike: Strike price.
        days_to_expiry: Calendar days to expiry.
        risk_free_rate: Risk-free rate.

    Returns:
        Parity check with deviation and whether it holds.
    """
    from diamond_options.pricing.black_scholes import put_call_parity_check

    T = days_to_expiry / 365.0
    return put_call_parity_check(call_price, put_price, spot, strike, T, risk_free_rate)


# ═══════════════════════════════════════════════════════════════
# STRATEGY ENGINE (Phase 3)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def list_strategies(
    category: str = "",
    outlook: str = "",
    risk_profile: str = "",
) -> dict:
    """List available option strategies with filtering.

    Shows all 18+ strategies with their descriptions, ideal conditions,
    and risk profiles.

    Args:
        category: Filter by category: directional, neutral, volatility, income, hedge.
        outlook: Filter by outlook: bullish, bearish, neutral, vol_up, vol_down.
        risk_profile: Filter by risk: defined, undefined.

    Returns:
        List of strategies with specs.
    """
    from diamond_options.strategy.definitions import (
        list_strategies as _list,
        StrategyCategory,
        MarketOutlook,
        RiskProfile,
    )

    cat = StrategyCategory(category) if category else None
    ol = MarketOutlook(outlook) if outlook else None
    rp = RiskProfile(risk_profile) if risk_profile else None

    strategies = _list(category=cat, outlook=ol, risk_profile=rp)

    return {
        "count": len(strategies),
        "strategies": [
            {
                "name": s.name,
                "slug": s.slug,
                "category": s.category.value,
                "outlook": s.outlook.value,
                "risk_profile": s.risk_profile.value,
                "num_legs": s.num_legs,
                "description": s.description,
                "ideal_iv": s.ideal_iv,
                "ideal_dte": s.ideal_dte,
                "vix_regimes": s.vix_regimes,
                "tags": s.tags,
            }
            for s in strategies
        ],
    }


@mcp.tool()
def strategy_details(strategy_slug: str) -> dict:
    """Get detailed specs for a specific strategy.

    Args:
        strategy_slug: Strategy ID (e.g., iron_condor, bull_call_spread, short_straddle).

    Returns:
        Full strategy specification with description, ideal conditions, and risk profile.
    """
    from diamond_options.strategy.definitions import get_strategy

    spec = get_strategy(strategy_slug)
    if not spec:
        return {"error": f"Strategy '{strategy_slug}' not found. Use list_strategies to see available."}

    return {
        "name": spec.name,
        "slug": spec.slug,
        "category": spec.category.value,
        "outlook": spec.outlook.value,
        "risk_profile": spec.risk_profile.value,
        "num_legs": spec.num_legs,
        "description": spec.description,
        "ideal_iv": spec.ideal_iv,
        "ideal_dte": spec.ideal_dte,
        "vix_regimes": spec.vix_regimes,
        "max_loss_type": spec.max_loss_type,
        "max_profit_type": spec.max_profit_type,
        "tags": spec.tags,
    }


@mcp.tool()
def suggest_strategy(
    spot: float,
    vix: float,
    iv_rank: float,
    realized_vol: float,
    implied_vol: float,
    trend: str = "neutral",
    days_to_expiry: int = 7,
    capital: float = 500000.0,
    lot_size: int = 65,
    strike_step: float = 50.0,
    defined_risk_only: bool = True,
    max_results: int = 3,
) -> dict:
    """Get trade suggestions based on current market conditions.

    This is the main trade recommendation tool. It analyzes VIX regime,
    IV rank, trend, and variance risk premium to suggest the best
    strategies with specific strikes, sizing, and expected P&L.

    Args:
        spot: Current underlying price.
        vix: India VIX value.
        iv_rank: IV rank (0-100). High = options expensive.
        realized_vol: Recent realized volatility (decimal, e.g., 0.13).
        implied_vol: Current ATM implied volatility (decimal, e.g., 0.15).
        trend: Price trend: strong_bullish, bullish, neutral, bearish, strong_bearish.
        days_to_expiry: Calendar days to target expiry.
        capital: Available trading capital in INR.
        lot_size: Lot size (25 for NIFTY, 15 for BANKNIFTY).
        strike_step: Strike interval (50 for NIFTY, 100 for BANKNIFTY).
        defined_risk_only: Only suggest defined-risk strategies (default True).
        max_results: Number of suggestions to return.

    Returns:
        Ranked list of trade recommendations with legs, sizing, and rationale.
    """
    from diamond_options.strategy.recommender import quick_recommendation

    return {
        "recommendations": quick_recommendation(
            spot=spot,
            vix=vix,
            iv_rank=iv_rank,
            realized_vol=realized_vol,
            implied_vol=implied_vol,
            days_to_expiry=days_to_expiry,
            trend=trend,
            capital=capital,
            lot_size=lot_size,
            strike_step=strike_step,
            defined_risk_only=defined_risk_only,
        )
    }


@mcp.tool()
def scan_market_signals(
    spot: float,
    vix: float,
    iv_rank: float,
    realized_vol: float,
    implied_vol: float,
    trend: str = "neutral",
    days_to_expiry: int = 7,
    min_score: int = 40,
) -> dict:
    """Scan all strategies and score them against current conditions.

    Returns a scored list showing which strategies have the best edge
    right now. Higher score = better alignment with market conditions.

    Score Components:
    - IV alignment (0-25): Does IV level suit this strategy?
    - VIX regime (0-20): Is VIX in the right range?
    - Trend (0-20): Does price trend support the outlook?
    - VRP edge (0-15): Is there a variance risk premium to exploit?
    - DTE fit (0-10): Is time-to-expiry optimal?

    Args:
        spot: Underlying price.
        vix: India VIX.
        iv_rank: IV rank (0-100).
        realized_vol: Realized volatility.
        implied_vol: Implied volatility.
        trend: Price trend direction.
        days_to_expiry: Calendar DTE.
        min_score: Minimum score to include (0-100).

    Returns:
        Scored strategy list sorted by quality.
    """
    from diamond_options.strategy.scanner import (
        MarketCondition,
        TrendDirection,
        scan_strategies,
    )

    trend_map = {
        "strong_bullish": TrendDirection.STRONG_BULLISH,
        "bullish": TrendDirection.BULLISH,
        "neutral": TrendDirection.NEUTRAL,
        "bearish": TrendDirection.BEARISH,
        "strong_bearish": TrendDirection.STRONG_BEARISH,
    }

    condition = MarketCondition(
        spot=spot, vix=vix, iv_rank=iv_rank, iv_percentile=iv_rank,
        trend=trend_map.get(trend, TrendDirection.NEUTRAL),
        realized_vol=realized_vol, implied_vol=implied_vol,
        days_to_expiry=days_to_expiry,
    )

    signals = scan_strategies(condition, min_score=min_score, max_results=10)

    return {
        "market_snapshot": {
            "spot": spot,
            "vix": vix,
            "iv_rank": iv_rank,
            "vrp": round(implied_vol - realized_vol, 4),
            "trend": trend,
        },
        "signals": [
            {
                "strategy": s.strategy.name,
                "slug": s.strategy.slug,
                "score": s.score,
                "confidence": s.confidence,
                "category": s.strategy.category.value,
                "risk_profile": s.strategy.risk_profile.value,
                "reasons": s.reasons,
                "expected_edge": s.expected_edge,
            }
            for s in signals
        ],
    }


@mcp.tool()
def position_size(
    capital: float,
    max_risk_pct: float,
    max_loss_per_lot: float,
    lot_size: int = 65,
    margin_per_lot: float = 0.0,
    vix: float = 15.0,
) -> dict:
    """Calculate optimal position size based on risk management.

    Uses fixed-risk sizing with VIX regime adjustment.
    Ensures no single trade risks more than the specified percentage.

    Args:
        capital: Available capital in INR.
        max_risk_pct: Max % of capital to risk per trade (e.g., 2.0).
        max_loss_per_lot: Maximum loss per lot in INR.
        lot_size: Shares per lot.
        margin_per_lot: Margin required per lot (0 for long options).
        vix: Current VIX for regime-based sizing adjustment.

    Returns:
        Recommended lots, capital at risk, margin, and rationale.
    """
    from diamond_options.strategy.sizing import (
        fixed_risk_size,
        vix_adjusted_multiplier,
    )
    from dataclasses import asdict

    vix_mult = vix_adjusted_multiplier(vix)
    size = fixed_risk_size(
        capital=capital,
        max_risk_pct=max_risk_pct,
        max_loss_per_lot=max_loss_per_lot,
        lot_size=lot_size,
        margin_per_lot=margin_per_lot,
        vix_multiplier=vix_mult,
    )

    return {
        **asdict(size),
        "vix": vix,
        "vix_multiplier": vix_mult,
    }


@mcp.tool()
def strategy_strikes(
    strategy_slug: str,
    spot: float,
    strike_step: float = 50.0,
    otm_distance: int = 2,
) -> dict:
    """Suggest strike prices for a strategy.

    Calculates optimal strikes based on current spot price
    and standard OTM distance conventions.

    Args:
        strategy_slug: Strategy ID (e.g., iron_condor, bull_call_spread).
        spot: Current spot price.
        strike_step: Strike interval (50 for NIFTY, 100 for BANKNIFTY).
        otm_distance: Number of strikes OTM for wings.

    Returns:
        Suggested strikes for each leg.
    """
    from diamond_options.strategy.scanner import suggest_strikes

    strikes = suggest_strikes(strategy_slug, spot, strike_step, otm_distance)
    return {
        "strategy": strategy_slug,
        "spot": spot,
        "strikes": strikes,
    }


# ═══════════════════════════════════════════════════════════════
# RISK MANAGEMENT (Phase 4)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def portfolio_greeks_analysis(
    positions: list[dict],
    spot: float,
) -> dict:
    """Calculate aggregate portfolio Greeks and check risk limits.

    Shows net delta, gamma, theta, vega across all positions.
    Flags breaches or warnings against risk limits.

    Args:
        positions: List of positions, each with:
            symbol, strike, option_type (CE/PE), action (BUY/SELL),
            lots, lot_size, days_to_expiry, iv.
        spot: Current underlying price.

    Returns:
        Portfolio Greeks, exposure summary, and any risk alerts.
    """
    from diamond_options.risk.portfolio_greeks import (
        calculate_position_greeks,
        aggregate_portfolio_greeks,
        check_risk_limits,
        portfolio_exposure_summary,
    )

    pos_greeks = [
        calculate_position_greeks(
            symbol=p["symbol"],
            spot=spot,
            strike=p["strike"],
            option_type=p["option_type"],
            action=p["action"],
            lots=p.get("lots", 1),
            lot_size=p.get("lot_size", 25),
            days_to_expiry=p.get("days_to_expiry", 7),
            iv=p.get("iv", 0.13),
        )
        for p in positions
    ]

    portfolio = aggregate_portfolio_greeks(pos_greeks)
    alerts = check_risk_limits(portfolio)
    summary = portfolio_exposure_summary(portfolio, spot)

    return {
        "portfolio": summary,
        "alerts": [
            {
                "level": a.level,
                "metric": a.metric,
                "current": a.current,
                "limit": a.limit,
                "message": a.message,
            }
            for a in alerts
        ],
        "positions": [
            {
                "symbol": p.symbol,
                "strike": p.strike,
                "type": p.option_type,
                "action": p.action,
                "delta": p.delta,
                "gamma": p.gamma,
                "theta": p.theta,
                "vega": p.vega,
            }
            for p in pos_greeks
        ],
    }


@mcp.tool()
def adjustment_advisor(
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
) -> dict:
    """Get adjustment recommendations for a challenged position.

    Analyzes position health and suggests: roll, widen, close, hedge.

    Args:
        symbol: Underlying (e.g., NIFTY).
        strategy: Strategy slug (e.g., iron_condor).
        spot: Current spot price.
        entry_spot: Spot price at entry.
        strikes: Strike price for each leg.
        option_types: CE/PE for each leg.
        actions: BUY/SELL for each leg.
        premiums: Entry premium per share for each leg.
        days_to_expiry: DTE remaining.
        current_pnl: Current P&L in INR.
        max_loss: Maximum possible loss in INR.

    Returns:
        Position status, adjustment recommendations, and do-nothing risk.
    """
    from diamond_options.risk.adjustments import analyze_position

    result = analyze_position(
        symbol=symbol, strategy=strategy,
        spot=spot, entry_spot=entry_spot,
        strikes=strikes, option_types=option_types,
        actions=actions, premiums=premiums,
        days_to_expiry=days_to_expiry,
        current_pnl=current_pnl, max_loss=max_loss,
    )

    return {
        "position_status": result.position_status,
        "trigger": result.trigger,
        "do_nothing_risk": result.do_nothing_risk,
        "adjustments": [
            {
                "type": a.type.value,
                "urgency": a.urgency,
                "description": a.description,
                "action_steps": a.action_steps,
                "estimated_cost": a.estimated_cost,
                "risk_reduction": a.risk_reduction,
                "trade_off": a.trade_off,
            }
            for a in result.adjustments
        ],
    }


@mcp.tool()
def monte_carlo_simulation(
    legs: list[dict],
    spot: float,
    days_to_expiry: int = 7,
    volatility: float = 0.13,
    lot_size: int = 65,
    num_paths: int = 10000,
) -> dict:
    """Run Monte Carlo simulation for an options position.

    Simulates 10,000 price paths to estimate P&L distribution,
    VaR, probability of profit, and expected shortfall.

    Args:
        legs: List of legs with: strike, option_type, action, premium.
        spot: Current spot price.
        days_to_expiry: Calendar DTE.
        volatility: Assumed volatility.
        lot_size: Shares per lot.
        num_paths: Simulation paths (default 10000).

    Returns:
        Expected P&L, VaR, CVaR, probability of profit, percentiles.
    """
    from diamond_options.pricing.payoff import Leg
    from diamond_options.risk.monte_carlo import simulate_position
    from dataclasses import asdict

    option_legs = [
        Leg(
            strike=l["strike"],
            option_type=l["option_type"],
            action=l["action"],
            premium=l["premium"],
            lots=l.get("lots", 1),
            lot_size=lot_size,
        )
        for l in legs
    ]

    T = days_to_expiry / 365.0
    result = simulate_position(
        option_legs, spot, T, r=0.065, sigma=volatility,
        num_paths=num_paths,
    )

    return asdict(result)


@mcp.tool()
def stress_test_position(
    legs: list[dict],
    spot: float,
    lot_size: int = 65,
) -> dict:
    """Stress test a position under extreme market scenarios.

    Tests P&L under 9 scenarios from -10% crash to +10% melt-up.

    Args:
        legs: List of legs with: strike, option_type, action, premium.
        spot: Current spot price.
        lot_size: Shares per lot.

    Returns:
        P&L under each stress scenario.
    """
    from diamond_options.pricing.payoff import Leg
    from diamond_options.risk.monte_carlo import stress_test

    option_legs = [
        Leg(
            strike=l["strike"],
            option_type=l["option_type"],
            action=l["action"],
            premium=l["premium"],
            lots=l.get("lots", 1),
            lot_size=lot_size,
        )
        for l in legs
    ]

    return {"scenarios": stress_test(option_legs, spot)}


@mcp.tool()
def backtest_strategy_tool(
    strategy: str,
    prices: list[float],
    dates: list[str],
    volatility: float = 0.13,
    lot_size: int = 65,
    entry_interval: int = 7,
    holding_period: int = 7,
) -> dict:
    """Backtest an options strategy over historical prices.

    Tests strategy performance by entering positions at regular intervals
    and calculating P&L at each expiry.

    Args:
        strategy: Strategy slug (iron_condor, bull_put_spread, etc.).
        prices: Historical daily closing prices.
        dates: Corresponding ISO date strings.
        volatility: Assumed volatility for BS pricing.
        lot_size: Shares per lot.
        entry_interval: Days between entries.
        holding_period: Days held per trade.

    Returns:
        Win rate, avg P&L, total P&L, Sharpe, max drawdown, trade log.
    """
    from diamond_options.risk.backtester import backtest_strategy

    result = backtest_strategy(
        strategy=strategy,
        prices=prices,
        dates=dates,
        sigma=volatility,
        lot_size=lot_size,
        entry_interval=entry_interval,
        holding_period=holding_period,
    )

    return {
        "strategy": result.strategy,
        "total_trades": result.total_trades,
        "winners": result.winners,
        "losers": result.losers,
        "win_rate": result.win_rate,
        "avg_pnl": result.avg_pnl,
        "total_pnl": result.total_pnl,
        "max_win": result.max_win,
        "max_loss": result.max_loss,
        "profit_factor": result.profit_factor,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "expectancy": result.expectancy,
        "trades": [
            {
                "entry_date": t.entry_date,
                "expiry_date": t.expiry_date,
                "entry_spot": t.entry_spot,
                "expiry_spot": t.expiry_spot,
                "pnl": t.pnl,
                "won": t.won,
            }
            for t in result.trades[:20]  # Limit to last 20 for readability
        ],
    }


@mcp.tool()
def expiry_checklist(
    strategy: str,
    spot: float,
    strikes: list[float],
    option_types: list[str],
    actions: list[str],
    lot_size: int = 65,
) -> dict:
    """Get expiry-day action checklist for a position.

    Checks for ITM/ATM legs that need attention on expiry day
    to avoid exercise STT and pin risk.

    Args:
        strategy: Strategy slug.
        spot: Current spot price.
        strikes: Strike for each leg.
        option_types: CE/PE for each leg.
        actions: BUY/SELL for each leg.
        lot_size: Shares per lot.

    Returns:
        Checklist of actions to take before 3:00 PM IST.
    """
    from diamond_options.risk.adjustments import expiry_day_checklist

    checklist = expiry_day_checklist(
        strategy=strategy,
        spot=spot,
        strikes=strikes,
        option_types=option_types,
        actions=actions,
        lot_size=lot_size,
    )

    return {"checklist": checklist}


# ═══════════════════════════════════════════════════════════════
# MARKET DATA (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def get_spot_price(symbol: str) -> dict:
    """Fetch current/last spot price for a stock or index.

    Args:
        symbol: NSE symbol (e.g., NIFTY, RELIANCE, BANKNIFTY).

    Returns:
        Spot price, change, and timestamp.
    """
    from diamond_options.data.market import get_spot_price as _get_spot

    sym = symbol.upper()
    price = _get_spot(sym)

    return {
        "symbol": sym,
        "spot_price": price,
    }


@mcp.tool()
def get_india_vix() -> dict:
    """Fetch current India VIX value with regime classification.

    Returns:
        VIX value, regime, and trading implications.
    """
    from diamond_options.data.market import get_india_vix as _get_vix
    from diamond_options.volatility.vix import classify_regime

    vix = _get_vix()
    regime = classify_regime(vix)

    return {
        "vix": vix,
        "regime": regime.regime,
        "strategy_bias": regime.strategy_bias,
        "position_size_multiplier": regime.position_sizing,
        "notes": regime.notes,
    }


@mcp.tool()
def download_historical_prices(
    symbol: str,
    period: str = "1y",
) -> dict:
    """Download historical prices for volatility and backtesting analysis.

    Args:
        symbol: NSE symbol (e.g., NIFTY, RELIANCE).
        period: yfinance period (1mo, 3mo, 6mo, 1y, 2y, 5y).

    Returns:
        Price count, date range, and recent prices.
    """
    from diamond_options.data.market import download_single

    prices = download_single(symbol, period=period)

    if prices is None or len(prices) == 0:
        return {"error": f"No data for {symbol}", "symbol": symbol}

    return {
        "symbol": symbol,
        "period": period,
        "count": len(prices),
        "first_date": str(prices.index[0].date()) if hasattr(prices.index[0], 'date') else str(prices.index[0]),
        "last_date": str(prices.index[-1].date()) if hasattr(prices.index[-1], 'date') else str(prices.index[-1]),
        "last_price": round(float(prices.iloc[-1]), 2),
        "recent_prices": [round(float(p), 2) for p in prices.tail(10).tolist()],
    }


@mcp.tool()
def get_ohlcv(symbol: str, period: str = "3mo") -> dict:
    """Fetch OHLCV (Open-High-Low-Close-Volume) data for a symbol.

    Needed for advanced HV estimators (Parkinson, Garman-Klass, Yang-Zhang).

    Args:
        symbol: NSE symbol.
        period: yfinance period.

    Returns:
        OHLCV summary with recent candles.
    """
    from diamond_options.data.market import get_ohlcv as _get_ohlcv

    df = _get_ohlcv(symbol, period=period)

    if df is None or len(df) == 0:
        return {"error": f"No OHLCV data for {symbol}"}

    return {
        "symbol": symbol,
        "count": len(df),
        "columns": list(df.columns),
        "recent": df.tail(5).to_dict(orient="records"),
    }


# ═══════════════════════════════════════════════════════════════
# HISTORICAL VOLATILITY (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def historical_volatility(
    prices: list[float],
    method: str = "close_to_close",
    window: int = 20,
    annualize: bool = True,
) -> dict:
    """Calculate historical volatility using various estimators.

    Methods: close_to_close, parkinson, garman_klass, yang_zhang, rogers_satchell.

    Args:
        prices: List of closing prices (min 20).
        method: Estimator method name.
        window: Rolling window size.
        annualize: Whether to annualize (default True).

    Returns:
        Volatility estimate and method details.
    """
    import numpy as np
    from diamond_options.volatility import historical as hv

    methods = {
        "close_to_close": hv.close_to_close,
        "parkinson": hv.parkinson,
        "garman_klass": hv.garman_klass,
        "yang_zhang": hv.yang_zhang,
        "rogers_satchell": hv.rogers_satchell,
    }

    fn = methods.get(method)
    if not fn:
        return {"error": f"Unknown method: {method}. Use: {list(methods.keys())}"}

    arr = np.array(prices)
    vol = fn(arr, window=window, annualize=annualize)

    return {
        "method": method,
        "volatility": round(float(vol), 6),
        "volatility_pct": f"{float(vol) * 100:.2f}%",
        "window": window,
        "annualized": annualize,
        "data_points": len(prices),
    }


@mcp.tool()
def all_hv_estimators(prices: list[float], window: int = 20) -> dict:
    """Calculate volatility using ALL 5 estimators for comparison.

    Shows close-to-close, Parkinson, Garman-Klass, Yang-Zhang, Rogers-Satchell
    side by side. Useful for understanding vol from different angles.

    Args:
        prices: List of closing prices.
        window: Rolling window.

    Returns:
        All 5 volatility estimates with comparison.
    """
    import numpy as np
    from diamond_options.volatility.historical import all_estimators

    arr = np.array(prices)
    results = all_estimators(arr, window=window)

    return {
        "window": window,
        "estimators": {k: round(v, 6) for k, v in results.items()},
        "estimators_pct": {k: f"{v * 100:.2f}%" for k, v in results.items()},
        "data_points": len(prices),
    }


@mcp.tool()
def multi_window_volatility(
    prices: list[float],
    method: str = "close_to_close",
) -> dict:
    """Calculate volatility across multiple timeframes (5, 10, 20, 60, 252 day).

    Shows how vol evolves from short-term to long-term.
    Rising short-term vs falling long-term = vol expansion.

    Args:
        prices: List of closing prices (ideally 252+).
        method: HV estimator method.

    Returns:
        Volatility at each window with trend analysis.
    """
    import numpy as np
    from diamond_options.volatility.historical import multi_window_vol

    arr = np.array(prices)
    results = multi_window_vol(arr, method=method)

    return {
        "method": method,
        "windows": results,
        "data_points": len(prices),
    }


@mcp.tool()
def rolling_volatility_series(
    prices: list[float],
    window: int = 20,
    method: str = "close_to_close",
) -> dict:
    """Calculate rolling volatility series for charting/analysis.

    Returns the full rolling vol series. Useful for vol trend analysis
    and comparing with current IV.

    Args:
        prices: List of closing prices.
        window: Rolling window.
        method: HV estimator.

    Returns:
        Rolling vol series with stats.
    """
    import numpy as np
    from diamond_options.volatility.historical import rolling_volatility

    arr = np.array(prices)
    series = rolling_volatility(arr, window=window, method=method)

    valid = [float(v) for v in series if not np.isnan(v)]

    return {
        "method": method,
        "window": window,
        "count": len(valid),
        "current": round(valid[-1], 6) if valid else None,
        "mean": round(float(np.mean(valid)), 6) if valid else None,
        "min": round(float(np.min(valid)), 6) if valid else None,
        "max": round(float(np.max(valid)), 6) if valid else None,
        "percentile_25": round(float(np.percentile(valid, 25)), 6) if valid else None,
        "percentile_75": round(float(np.percentile(valid, 75)), 6) if valid else None,
        "recent_10": [round(v, 6) for v in valid[-10:]] if valid else [],
    }


# ═══════════════════════════════════════════════════════════════
# VOLATILITY FORECASTING (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def ewma_forecast(
    prices: list[float],
    horizon_days: int = 5,
    decay: float = 0.94,
) -> dict:
    """Forecast volatility using EWMA (Exponentially Weighted Moving Average).

    RiskMetrics-style exponential weighting. Good for short-term vol forecasts.

    Args:
        prices: Historical closing prices.
        horizon_days: Forecast horizon in days.
        decay: EWMA decay factor (0.94 = RiskMetrics standard).

    Returns:
        Current EWMA vol and forecast.
    """
    import numpy as np
    from diamond_options.volatility.forecast import ewma_volatility, ewma_forecast as _forecast

    arr = np.array(prices)
    returns = np.diff(np.log(arr))
    current = ewma_volatility(returns, decay=decay)
    forecast = _forecast(returns, horizon=horizon_days, decay=decay)

    return {
        "current_ewma_vol": round(float(current), 6),
        "current_pct": f"{float(current) * 100:.2f}%",
        "forecast_vol": round(float(forecast), 6),
        "forecast_pct": f"{float(forecast) * 100:.2f}%",
        "horizon_days": horizon_days,
        "decay": decay,
    }


@mcp.tool()
def garch_forecast(
    prices: list[float],
    horizon_days: int = 5,
) -> dict:
    """Forecast volatility using GARCH(1,1) model.

    Mean-reverting volatility forecast. Better than EWMA for medium-term.

    Args:
        prices: Historical closing prices (ideally 252+).
        horizon_days: Forecast horizon.

    Returns:
        GARCH parameters, current vol, and forecast.
    """
    import numpy as np
    from diamond_options.volatility.forecast import garch_fit, garch_forecast as _forecast

    arr = np.array(prices)
    returns = np.diff(np.log(arr))

    params = garch_fit(returns)
    forecast = _forecast(returns, horizon=horizon_days)

    return {
        "garch_params": {
            "omega": round(params["omega"], 10),
            "alpha": round(params["alpha"], 6),
            "beta": round(params["beta"], 6),
            "persistence": round(params["alpha"] + params["beta"], 4),
            "long_run_vol": round(params.get("long_run_vol", 0), 6),
        },
        "current_vol": round(float(params.get("current_vol", 0)), 6),
        "forecast_vol": round(float(forecast), 6),
        "forecast_pct": f"{float(forecast) * 100:.2f}%",
        "horizon_days": horizon_days,
    }


# ═══════════════════════════════════════════════════════════════
# IV SURFACE & ANALYSIS (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def iv_smile_analysis(
    strikes: list[float],
    ivs: list[float],
    spot: float,
) -> dict:
    """Analyze IV smile/skew pattern across strikes.

    Identifies put skew (normal), call skew, or flat pattern.

    Args:
        strikes: Strike prices.
        ivs: Corresponding implied volatilities.
        spot: Current spot price.

    Returns:
        Smile shape, skew metrics, and interpretation.
    """
    if len(strikes) != len(ivs) or len(strikes) == 0:
        return {"error": "strikes and ivs must be non-empty lists of equal length"}

    # Find ATM IV (strike closest to spot)
    atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
    atm_iv = ivs[atm_idx]

    # Separate put-side (below spot) and call-side (above spot)
    put_side = [(strikes[i], ivs[i]) for i in range(len(strikes)) if strikes[i] < spot]
    call_side = [(strikes[i], ivs[i]) for i in range(len(strikes)) if strikes[i] > spot]

    put_skew = (sum(iv for _, iv in put_side) / len(put_side) - atm_iv) if put_side else 0.0
    call_skew = (sum(iv for _, iv in call_side) / len(call_side) - atm_iv) if call_side else 0.0

    # Determine smile shape
    threshold = 0.005  # 0.5% IV difference threshold
    if put_skew > threshold and call_skew > threshold:
        smile_shape = "smile"
        interpretation = "Both wings elevated — classic volatility smile, common in indices."
    elif put_skew > threshold and call_skew <= threshold:
        smile_shape = "put_skew"
        interpretation = "Put-side IV elevated — normal equity skew, demand for downside protection."
    elif call_skew > threshold and put_skew <= threshold:
        smile_shape = "call_skew"
        interpretation = "Call-side IV elevated — unusual, may indicate short squeeze or event risk."
    else:
        smile_shape = "flat"
        interpretation = "Minimal IV variation across strikes — low skew environment."

    skew_ratio = round(put_skew / call_skew, 4) if call_skew != 0 else float("inf") if put_skew > 0 else 0.0

    per_strike = [
        {"strike": strikes[i], "iv": round(ivs[i], 6), "moneyness": round(strikes[i] / spot, 4)}
        for i in range(len(strikes))
    ]

    return {
        "atm_iv": round(atm_iv, 6),
        "atm_strike": strikes[atm_idx],
        "put_skew": round(put_skew, 6),
        "call_skew": round(call_skew, 6),
        "skew_ratio": skew_ratio,
        "smile_shape": smile_shape,
        "interpretation": interpretation,
        "strikes": per_strike,
    }


@mcp.tool()
def iv_term_structure(
    expiries_days: list[int],
    ivs: list[float],
) -> dict:
    """Analyze IV term structure across expiries.

    Normal = upward sloping (far expiry > near). Inverted = fear/event.

    Args:
        expiries_days: Days to expiry for each data point.
        ivs: ATM IV for each expiry.

    Returns:
        Term structure shape and interpretation.
    """
    if len(expiries_days) != len(ivs) or len(expiries_days) == 0:
        return {"error": "expiries_days and ivs must be non-empty lists of equal length"}

    # Sort by DTE
    paired = sorted(zip(expiries_days, ivs), key=lambda x: x[0])
    sorted_dte = [p[0] for p in paired]
    sorted_ivs = [p[1] for p in paired]

    # Determine structure
    if len(sorted_ivs) >= 2:
        short_iv = sorted_ivs[0]
        long_iv = sorted_ivs[-1]
        if long_iv > short_iv * 1.02:
            structure = "contango"
            interpretation = "Normal term structure — longer-dated IV higher. Market calm, no near-term event fear."
        elif short_iv > long_iv * 1.02:
            structure = "backwardation"
            interpretation = "Inverted term structure — near-term IV elevated. Possible event risk or fear spike."
        else:
            structure = "flat"
            interpretation = "Flat term structure — similar IV across expiries. Neutral outlook."
    else:
        structure = "insufficient_data"
        interpretation = "Need at least 2 expiries to determine structure."

    per_expiry = [
        {"dte": sorted_dte[i], "iv": round(sorted_ivs[i], 6)}
        for i in range(len(sorted_dte))
    ]

    return {
        "structure": structure,
        "interpretation": interpretation,
        "short_term_iv": round(sorted_ivs[0], 6) if sorted_ivs else None,
        "long_term_iv": round(sorted_ivs[-1], 6) if sorted_ivs else None,
        "expiries": per_expiry,
    }


@mcp.tool()
def iv_surface(
    strikes: list[float],
    expiries_days: list[int],
    ivs_matrix: list[list[float]],
    spot: float,
) -> dict:
    """Build IV surface grid (strike x expiry).

    3D view of implied volatility across strikes and expiries.

    Args:
        strikes: Strike prices.
        expiries_days: Days to expiry values.
        ivs_matrix: 2D matrix of IVs [expiry_idx][strike_idx].
        spot: Current spot.

    Returns:
        IV surface grid with analysis.
    """
    if len(ivs_matrix) != len(expiries_days):
        return {"error": "ivs_matrix must have one row per expiry"}
    if any(len(row) != len(strikes) for row in ivs_matrix):
        return {"error": "Each row in ivs_matrix must have one value per strike"}

    grid = []
    for exp_idx, dte in enumerate(expiries_days):
        for str_idx, strike in enumerate(strikes):
            iv = ivs_matrix[exp_idx][str_idx]
            moneyness = round(strike / spot, 4)
            grid.append({
                "strike": strike,
                "dte": dte,
                "iv": round(iv, 6),
                "moneyness": moneyness,
            })

    # Summary: min/max IV, ATM term structure
    all_ivs = [pt["iv"] for pt in grid]
    atm_term = []
    for exp_idx, dte in enumerate(expiries_days):
        atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
        atm_term.append({"dte": dte, "atm_iv": round(ivs_matrix[exp_idx][atm_idx], 6)})

    return {
        "surface": grid,
        "spot": spot,
        "num_strikes": len(strikes),
        "num_expiries": len(expiries_days),
        "min_iv": round(min(all_ivs), 6) if all_ivs else None,
        "max_iv": round(max(all_ivs), 6) if all_ivs else None,
        "atm_term_structure": atm_term,
    }


# ═══════════════════════════════════════════════════════════════
# ADVANCED GREEKS (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def probability_itm(
    spot: float,
    strike: float,
    days_to_expiry: int,
    volatility: float,
    option_type: str,
    risk_free_rate: float = 0.065,
) -> dict:
    """Calculate probability of option finishing in-the-money at expiry.

    Args:
        spot: Current spot price.
        strike: Strike price.
        days_to_expiry: Calendar DTE.
        volatility: IV or HV.
        option_type: CE or PE.
        risk_free_rate: Risk-free rate.

    Returns:
        Probability ITM, OTM, and interpretation.
    """
    from diamond_options.pricing.greeks import probability_itm as _prob

    T = days_to_expiry / 365.0
    p = _prob(spot, strike, T, risk_free_rate, volatility, option_type)

    return {
        "probability_itm": round(p * 100, 2),
        "probability_otm": round((1 - p) * 100, 2),
        "option_type": option_type.upper(),
        "spot": spot,
        "strike": strike,
        "days_to_expiry": days_to_expiry,
        "interpretation": (
            "High probability ITM — deep in the money"
            if p > 0.7
            else "Moderate probability — near the money"
            if p > 0.3
            else "Low probability ITM — out of the money"
        ),
    }


@mcp.tool()
def probability_of_profit(
    legs: list[dict],
    spot: float,
    days_to_expiry: int = 7,
    volatility: float = 0.13,
    lot_size: int = 65,
) -> dict:
    """Calculate probability of a multi-leg trade being profitable at expiry.

    Uses Monte Carlo simulation to estimate P(PnL > 0).

    Args:
        legs: List of legs with: strike, option_type, action, premium.
        spot: Current spot.
        days_to_expiry: Calendar DTE.
        volatility: Assumed volatility.
        lot_size: Shares per lot.

    Returns:
        Probability of profit and expected P&L.
    """
    from diamond_options.pricing.payoff import Leg, expected_value

    option_legs = [
        Leg(
            strike=l["strike"],
            option_type=l["option_type"],
            action=l["action"],
            premium=l["premium"],
            lots=l.get("lots", 1),
            lot_size=lot_size,
        )
        for l in legs
    ]

    T = days_to_expiry / 365.0
    ev = expected_value(option_legs, spot, T=T, r=0.065, sigma=volatility)

    return {
        "prob_profit": ev["prob_profit"],
        "expected_pnl": ev["expected_pnl"],
        "var_95": ev["var_95"],
        "interpretation": (
            "High edge — favorable trade"
            if ev["prob_profit"] > 60
            else "Moderate edge — proceed with sizing"
            if ev["prob_profit"] > 45
            else "Low edge — consider alternatives"
        ),
    }


@mcp.tool()
def greeks_comparison(
    spot: float,
    strikes: list[float],
    days_to_expiry: int,
    volatility: float,
    option_type: str,
    risk_free_rate: float = 0.065,
) -> dict:
    """Compare Greeks across multiple strikes for strike selection.

    Shows delta/gamma/theta/vega side-by-side for multiple strikes.

    Args:
        spot: Underlying price.
        strikes: List of strike prices to compare.
        days_to_expiry: Calendar DTE.
        volatility: IV.
        option_type: CE or PE.
        risk_free_rate: Risk-free rate.

    Returns:
        Greeks for each strike in a comparison table.
    """
    from diamond_options.pricing.greeks import calculate_greeks as _calc

    T = days_to_expiry / 365.0
    results = []
    for strike in strikes:
        g = _calc(spot, strike, T, risk_free_rate, volatility, option_type)
        moneyness = round(strike / spot, 4)
        results.append({
            "strike": strike,
            "moneyness": moneyness,
            "delta": g.delta,
            "gamma": g.gamma,
            "theta": g.theta,
            "vega": g.vega,
        })

    return {
        "option_type": option_type.upper(),
        "spot": spot,
        "days_to_expiry": days_to_expiry,
        "volatility": volatility,
        "strikes": results,
    }


# ═══════════════════════════════════════════════════════════════
# ADVANCED PRICING (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def price_spread(
    legs: list[dict],
    spot: float,
    days_to_expiry: int,
    volatility: float,
    risk_free_rate: float = 0.065,
    lot_size: int = 65,
) -> dict:
    """Price a multi-leg spread using Black-Scholes.

    Calculates theoretical price for each leg and net premium.

    Args:
        legs: List with: strike, option_type (CE/PE), action (BUY/SELL).
        spot: Current spot.
        days_to_expiry: Calendar DTE.
        volatility: IV for pricing.
        risk_free_rate: Risk-free rate.
        lot_size: Shares per lot.

    Returns:
        Per-leg prices and net premium.
    """
    from diamond_options.pricing.black_scholes import price_option as _price

    T = days_to_expiry / 365.0
    results = []
    net_premium = 0.0

    for l in legs:
        result = _price(spot, l["strike"], T, risk_free_rate, volatility, l["option_type"])
        sign = -1 if l["action"].upper() == "BUY" else 1
        net_premium += sign * result.price * lot_size

        results.append({
            "strike": l["strike"],
            "option_type": l["option_type"],
            "action": l["action"],
            "price": round(result.price, 2),
            "value_per_lot": round(result.price * lot_size, 2),
        })

    return {
        "spot": spot,
        "days_to_expiry": days_to_expiry,
        "volatility": volatility,
        "legs": results,
        "net_premium": round(net_premium, 2),
        "net_premium_type": "credit" if net_premium > 0 else "debit",
    }


@mcp.tool()
def payoff_curve(
    legs: list[dict],
    spot: float,
    lot_size: int = 65,
    num_points: int = 50,
) -> dict:
    """Generate payoff curve data points for plotting.

    Returns (spot_price, pnl) pairs spanning the relevant range.

    Args:
        legs: List with: strike, option_type, action, premium.
        spot: Current spot.
        lot_size: Shares per lot.
        num_points: Number of data points.

    Returns:
        Payoff curve data, breakevens, max profit/loss.
    """
    from diamond_options.pricing.payoff import Leg, payoff_curve as _curve, analyze_payoff as _analyze

    option_legs = [
        Leg(
            strike=l["strike"],
            option_type=l["option_type"],
            action=l["action"],
            premium=l["premium"],
            lots=l.get("lots", 1),
            lot_size=lot_size,
        )
        for l in legs
    ]

    curve = _curve(option_legs, spot, num_points=num_points)
    analysis = _analyze(option_legs, spot)

    return {
        "curve": [{"spot": round(s, 2), "pnl": round(p, 2)} for s, p in curve],
        "breakevens": analysis.breakevens,
        "max_profit": analysis.max_profit if analysis.max_profit != float("inf") else "Unlimited",
        "max_loss": analysis.max_loss if analysis.max_loss != float("-inf") else "Unlimited",
    }


# ═══════════════════════════════════════════════════════════════
# STRATEGY COMPARISON (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def compare_strategies(
    strategy_slugs: list[str],
    spot: float,
    days_to_expiry: int = 7,
    volatility: float = 0.13,
    lot_size: int = 65,
    strike_step: float = 50.0,
) -> dict:
    """Compare multiple strategies side-by-side for the same underlying.

    Shows max profit, max loss, breakevens, prob profit for each.

    Args:
        strategy_slugs: List of strategy slugs to compare.
        spot: Current spot price.
        days_to_expiry: Calendar DTE.
        volatility: IV for BS pricing.
        lot_size: Shares per lot.
        strike_step: Strike interval.

    Returns:
        Side-by-side comparison of all strategies.
    """
    from diamond_options.strategy.definitions import get_strategy, BUILDERS
    from diamond_options.pricing.payoff import Leg, analyze_payoff as _analyze, expected_value
    from diamond_options.pricing.black_scholes import price_option as _price

    T = days_to_expiry / 365.0
    comparisons = []

    for slug in strategy_slugs:
        spec = get_strategy(slug)
        builder = BUILDERS.get(slug)
        if not spec or not builder:
            comparisons.append({"strategy": slug, "error": "Not found"})
            continue

        raw_legs = builder(spot, strike_step)
        legs = []
        for rl in raw_legs:
            bs = _price(spot, rl["strike"], T, 0.065, volatility, rl["option_type"])
            legs.append(Leg(
                strike=rl["strike"],
                option_type=rl["option_type"],
                action=rl["action"],
                premium=bs.price,
                lots=1,
                lot_size=lot_size,
            ))

        analysis = _analyze(legs, spot)
        ev = expected_value(legs, spot, T=T, r=0.065, sigma=volatility)

        mp = analysis.max_profit
        ml = analysis.max_loss

        comparisons.append({
            "strategy": spec.name,
            "slug": slug,
            "category": spec.category.value,
            "risk_profile": spec.risk_profile.value,
            "num_legs": spec.num_legs,
            "max_profit": round(mp, 2) if mp != float("inf") else "Unlimited",
            "max_loss": round(ml, 2) if ml != float("-inf") else "Unlimited",
            "breakevens": analysis.breakevens,
            "risk_reward": round(analysis.risk_reward, 2) if analysis.risk_reward != float("inf") else "N/A",
            "net_premium": round(analysis.net_premium, 2),
            "prob_profit": ev["prob_profit"],
            "expected_pnl": ev["expected_pnl"],
        })

    return {"spot": spot, "comparisons": comparisons}


@mcp.tool()
def strategies_for_vix_regime(vix: float) -> dict:
    """Get strategies suitable for the current VIX regime.

    Maps VIX level to regime and returns compatible strategies.

    Args:
        vix: Current India VIX value.

    Returns:
        Regime classification and suitable strategies.
    """
    from diamond_options.volatility.vix import classify_regime
    from diamond_options.strategy.definitions import strategies_for_regime

    regime = classify_regime(vix)
    strategies = strategies_for_regime(regime.regime)

    return {
        "vix": vix,
        "regime": regime.regime,
        "strategy_bias": regime.strategy_bias,
        "suitable_strategies": [
            {
                "name": s.name,
                "slug": s.slug,
                "category": s.category.value,
                "risk_profile": s.risk_profile.value,
            }
            for s in strategies
        ],
        "count": len(strategies),
    }


# ═══════════════════════════════════════════════════════════════
# POSITION SIZING (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def kelly_position_size(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    capital: float,
    max_loss_per_lot: float,
    lot_size: int = 65,
    fraction: float = 0.5,
) -> dict:
    """Calculate position size using Kelly criterion.

    Kelly fraction = (p*b - q) / b, where p=win rate, b=win/loss ratio.
    Uses half-Kelly by default for safety.

    Args:
        win_rate: Historical win rate (0-1, e.g., 0.65).
        avg_win: Average winning trade P&L.
        avg_loss: Average losing trade P&L (positive number).
        capital: Available capital.
        max_loss_per_lot: Max loss per lot.
        lot_size: Shares per lot.
        fraction: Kelly fraction (0.5 = half-Kelly).

    Returns:
        Kelly fraction, recommended lots, capital at risk.
    """
    from diamond_options.strategy.sizing import kelly_size
    from dataclasses import asdict

    size = kelly_size(
        capital=capital,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        max_loss_per_lot=max_loss_per_lot,
        lot_size=lot_size,
        fraction=fraction,
    )

    return asdict(size)


@mcp.tool()
def max_lots_affordable(
    capital: float,
    premium_per_share: float,
    lot_size: int = 65,
    max_capital_pct: float = 10.0,
) -> dict:
    """Calculate maximum lots affordable for long option positions.

    For debit strategies where cost = premium x lot_size x lots.

    Args:
        capital: Available capital.
        premium_per_share: Option premium per share.
        lot_size: Shares per lot.
        max_capital_pct: Max % of capital to deploy.

    Returns:
        Maximum lots and capital usage.
    """
    from diamond_options.strategy.sizing import max_lots_by_capital

    lots = max_lots_by_capital(
        capital=capital,
        premium_per_share=premium_per_share,
        lot_size=lot_size,
        max_capital_pct=max_capital_pct,
    )

    cost_per_lot = premium_per_share * lot_size
    total_cost = cost_per_lot * lots

    return {
        "max_lots": lots,
        "cost_per_lot": round(cost_per_lot, 2),
        "total_cost": round(total_cost, 2),
        "capital_used_pct": round(total_cost / capital * 100, 2),
        "capital": capital,
    }


# ═══════════════════════════════════════════════════════════════
# WHAT-IF ANALYSIS (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def what_if_spot_move(
    legs: list[dict],
    spot: float,
    spot_changes_pct: list[float],
    lot_size: int = 65,
) -> dict:
    """What-if analysis: P&L at different spot prices.

    Shows how position performs if spot moves by given percentages.

    Args:
        legs: List with: strike, option_type, action, premium.
        spot: Current spot.
        spot_changes_pct: List of % changes (e.g., [-5, -2, 0, 2, 5]).
        lot_size: Shares per lot.

    Returns:
        P&L at each spot level.
    """
    from diamond_options.pricing.payoff import Leg, position_payoff_at_expiry

    option_legs = [
        Leg(
            strike=l["strike"],
            option_type=l["option_type"],
            action=l["action"],
            premium=l["premium"],
            lots=l.get("lots", 1),
            lot_size=lot_size,
        )
        for l in legs
    ]

    results = []
    for pct in spot_changes_pct:
        new_spot = spot * (1 + pct / 100)
        pnl = position_payoff_at_expiry(option_legs, new_spot)
        results.append({
            "spot_change_pct": pct,
            "new_spot": round(new_spot, 2),
            "pnl": round(pnl, 2),
        })

    return {"current_spot": spot, "scenarios": results}


@mcp.tool()
def what_if_iv_change(
    spot: float,
    strike: float,
    days_to_expiry: int,
    current_iv: float,
    iv_changes: list[float],
    option_type: str,
    risk_free_rate: float = 0.065,
    lot_size: int = 65,
) -> dict:
    """What-if analysis: option price at different IV levels.

    Shows impact of IV crush or expansion on option value.

    Args:
        spot: Underlying price.
        strike: Strike price.
        days_to_expiry: Calendar DTE.
        current_iv: Current IV.
        iv_changes: IV change amounts (e.g., [-0.05, -0.02, 0, 0.02, 0.05]).
        option_type: CE or PE.
        risk_free_rate: Risk-free rate.
        lot_size: Shares per lot.

    Returns:
        Option price at each IV level.
    """
    from diamond_options.pricing.black_scholes import price_option as _price

    T = days_to_expiry / 365.0
    base = _price(spot, strike, T, risk_free_rate, current_iv, option_type)

    results = []
    for dv in iv_changes:
        new_iv = max(0.01, current_iv + dv)
        new_price = _price(spot, strike, T, risk_free_rate, new_iv, option_type)
        results.append({
            "iv_change": dv,
            "new_iv": round(new_iv, 4),
            "new_iv_pct": f"{new_iv * 100:.1f}%",
            "price": round(new_price.price, 2),
            "price_change": round(new_price.price - base.price, 2),
            "pnl_per_lot": round((new_price.price - base.price) * lot_size, 2),
        })

    return {
        "base_price": round(base.price, 2),
        "current_iv": current_iv,
        "option_type": option_type.upper(),
        "scenarios": results,
    }


@mcp.tool()
def what_if_time_decay(
    spot: float,
    strike: float,
    days_to_expiry: int,
    volatility: float,
    option_type: str,
    check_days: list[int] = None,
    risk_free_rate: float = 0.065,
    lot_size: int = 65,
) -> dict:
    """What-if analysis: option value as time passes (theta decay).

    Shows how premium erodes over time. Crucial for timing entries/exits.

    Args:
        spot: Underlying price.
        strike: Strike price.
        days_to_expiry: Current calendar DTE.
        volatility: IV.
        option_type: CE or PE.
        check_days: Days to check (default: evenly spaced).
        risk_free_rate: Risk-free rate.
        lot_size: Shares per lot.

    Returns:
        Option price at each time checkpoint.
    """
    from diamond_options.pricing.black_scholes import price_option as _price

    if check_days is None:
        check_days = [d for d in [days_to_expiry, max(1, days_to_expiry * 3 // 4),
                                   max(1, days_to_expiry // 2), max(1, days_to_expiry // 4), 1]
                      if d > 0]
        check_days = sorted(set(check_days), reverse=True)

    results = []
    base_T = days_to_expiry / 365.0
    base = _price(spot, strike, base_T, risk_free_rate, volatility, option_type)

    for d in check_days:
        T = d / 365.0
        p = _price(spot, strike, T, risk_free_rate, volatility, option_type)
        results.append({
            "days_remaining": d,
            "price": round(p.price, 2),
            "time_value": round(p.time_value, 2),
            "decay_from_now": round(p.price - base.price, 2),
            "decay_per_lot": round((p.price - base.price) * lot_size, 2),
        })

    return {
        "spot": spot,
        "strike": strike,
        "current_price": round(base.price, 2),
        "option_type": option_type.upper(),
        "decay_curve": results,
    }


# ═══════════════════════════════════════════════════════════════
# TRADE EXECUTION HELPERS (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def build_option_symbol(
    symbol: str,
    strike: float,
    option_type: str,
    expiry_date: str = "",
) -> dict:
    """Build NSE option trading symbol.

    Args:
        symbol: Underlying (e.g., NIFTY, RELIANCE).
        strike: Strike price.
        option_type: CE or PE.
        expiry_date: ISO date (default: next weekly expiry).

    Returns:
        Trading symbol and Kite instrument format.
    """
    from diamond_options.utils.formatters import option_symbol
    from diamond_options.data.expiry import next_weekly_expiry
    from datetime import date as dt_date

    if expiry_date:
        exp = dt_date.fromisoformat(expiry_date)
    else:
        exp = next_weekly_expiry()

    sym = option_symbol(symbol, strike, option_type, exp)

    return {
        "symbol": sym,
        "underlying": symbol.upper(),
        "strike": strike,
        "option_type": option_type.upper(),
        "expiry": exp.isoformat(),
    }


@mcp.tool()
def trade_cost_impact(
    strategy_slug: str,
    spot: float,
    strike_step: float = 50.0,
    volatility: float = 0.13,
    days_to_expiry: int = 7,
    lot_size: int = 65,
    lots: int = 1,
    is_index: bool = True,
) -> dict:
    """Calculate total cost impact on a strategy's profitability.

    Shows costs as % of max profit to assess if the trade is worth it.

    Args:
        strategy_slug: Strategy (e.g., iron_condor).
        spot: Spot price.
        strike_step: Strike interval.
        volatility: IV for pricing.
        days_to_expiry: Calendar DTE.
        lot_size: Shares per lot.
        lots: Number of lots.
        is_index: Whether it's an index option.

    Returns:
        Cost breakdown, cost as % of max profit, and net profitability.
    """
    from diamond_options.strategy.definitions import BUILDERS
    from diamond_options.pricing.black_scholes import price_option as _price
    from diamond_options.pricing.payoff import Leg, analyze_payoff as _analyze
    from diamond_options.data.costs import calculate_options_costs

    builder = BUILDERS.get(strategy_slug)
    if not builder:
        return {"error": f"Strategy '{strategy_slug}' not found"}

    T = days_to_expiry / 365.0
    raw_legs = builder(spot, strike_step)
    option_legs = []
    total_cost = 0.0

    for rl in raw_legs:
        bs = _price(spot, rl["strike"], T, 0.065, volatility, rl["option_type"])
        premium_amount = bs.price * lot_size * lots

        # Entry cost
        entry_cost = calculate_options_costs(rl["action"], premium_amount, is_index)
        # Exit cost (reverse action)
        exit_action = "SELL" if rl["action"] == "BUY" else "BUY"
        exit_cost = calculate_options_costs(exit_action, premium_amount, is_index)
        total_cost += entry_cost.total + exit_cost.total

        option_legs.append(Leg(
            strike=rl["strike"],
            option_type=rl["option_type"],
            action=rl["action"],
            premium=bs.price,
            lots=lots,
            lot_size=lot_size,
        ))

    analysis = _analyze(option_legs, spot)
    mp = analysis.max_profit

    return {
        "strategy": strategy_slug,
        "total_round_trip_cost": round(total_cost, 2),
        "max_profit": round(mp, 2) if mp != float("inf") else "Unlimited",
        "cost_as_pct_of_max_profit": round(total_cost / mp * 100, 2) if mp != float("inf") and mp > 0 else "N/A",
        "net_max_profit": round(mp - total_cost, 2) if mp != float("inf") else "Unlimited",
        "num_orders": len(raw_legs) * 2,
        "brokerage_alone": len(raw_legs) * 2 * 20,
    }


# ═══════════════════════════════════════════════════════════════
# VIX TOOLS (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def vix_term_structure(
    near_vix: float,
    far_vix: float,
) -> dict:
    """Analyze VIX term structure (contango vs backwardation).

    Contango (far > near) = normal. Backwardation (near > far) = fear.

    Args:
        near_vix: Near-month VIX.
        far_vix: Far-month VIX.

    Returns:
        Term structure state and trading implications.
    """
    from diamond_options.volatility.vix import vix_term_structure_signal

    result = vix_term_structure_signal(near_vix, far_vix)
    return result


@mcp.tool()
def vix_mean_reversion(vix: float) -> dict:
    """Check if VIX is mean-reverting and get signal.

    VIX > 20 tends to revert down (sell premium).
    VIX < 12 tends to revert up (buy protection).

    Args:
        vix: Current India VIX value.

    Returns:
        Mean reversion signal and action.
    """
    from diamond_options.volatility.vix import vix_mean_reversion_signal

    signal = vix_mean_reversion_signal(vix)
    return signal


# ═══════════════════════════════════════════════════════════════
# EXPIRY & CALENDAR (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def next_monthly_expiry() -> dict:
    """Get next monthly F&O expiry date.

    Monthly expiry is the last Tuesday of the month.
    All F&O stocks expire monthly.

    Returns:
        Next monthly expiry date with days remaining.
    """
    from diamond_options.data.expiry import (
        next_monthly_expiry as _next_monthly,
        days_to_expiry,
        expiry_label,
    )

    exp = _next_monthly()
    days = days_to_expiry(exp)

    return {
        "expiry": exp.isoformat(),
        "label": expiry_label(exp),
        "days_remaining": days,
        "type": "monthly",
    }


@mcp.tool()
def trading_days_to_expiry(expiry_date: str) -> dict:
    """Calculate trading days (not calendar days) to an expiry.

    Trading days exclude weekends and NSE holidays.
    Important for theta decay calculations.

    Args:
        expiry_date: ISO date string (e.g., "2026-03-12").

    Returns:
        Trading days and calendar days comparison.
    """
    from diamond_options.utils.indian_markets import (
        trading_days_to_expiry as _trading_days,
        calendar_days_to_expiry as _cal_days,
    )
    from datetime import date as dt_date

    exp = dt_date.fromisoformat(expiry_date)
    trading = _trading_days(exp)
    calendar = _cal_days(exp)

    return {
        "expiry": expiry_date,
        "trading_days": trading,
        "calendar_days": calendar,
        "ratio": round(trading / calendar, 2) if calendar > 0 else 0,
    }


@mcp.tool()
def is_trading_day(check_date: str = "") -> dict:
    """Check if a date is an NSE trading day.

    Considers weekends and NSE holidays.

    Args:
        check_date: ISO date (default: today).

    Returns:
        Whether it's a trading day and next trading day.
    """
    from diamond_options.utils.indian_markets import (
        is_trading_day as _is_trading,
        next_trading_day,
    )
    from datetime import date as dt_date

    d = dt_date.fromisoformat(check_date) if check_date else dt_date.today()
    is_td = _is_trading(d)
    next_td = next_trading_day(d)

    return {
        "date": d.isoformat(),
        "is_trading_day": is_td,
        "next_trading_day": next_td.isoformat(),
        "day_of_week": d.strftime("%A"),
    }


# ═══════════════════════════════════════════════════════════════
# FORMATTING & DISPLAY (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def format_inr(amount: float) -> dict:
    """Format amount in INR with Indian number system (lakhs/crores).

    Args:
        amount: Amount in INR.

    Returns:
        Formatted strings in different formats.
    """
    from diamond_options.utils.formatters import fmt_inr, fmt_lakhs

    return {
        "amount": amount,
        "formatted": fmt_inr(amount),
        "lakhs_crores": fmt_lakhs(amount),
    }


@mcp.tool()
def futures_costs(
    action: str,
    contract_value: float,
    is_index: bool = False,
) -> dict:
    """Calculate futures transaction costs for Indian markets.

    Args:
        action: BUY or SELL.
        contract_value: Total contract value in INR.
        is_index: Whether it's an index future.

    Returns:
        Itemized cost breakdown.
    """
    from diamond_options.data.costs import calculate_futures_costs
    from dataclasses import asdict

    cost = calculate_futures_costs(action.upper(), contract_value, is_index)
    return asdict(cost)


# ═══════════════════════════════════════════════════════════════
# QUICK ANALYSIS (Phase 5)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def quick_iron_condor(
    spot: float,
    vix: float = 15.0,
    days_to_expiry: int = 7,
    lot_size: int = 65,
    strike_step: float = 50.0,
) -> dict:
    """Quick iron condor setup with auto-selected strikes and full analysis.

    One-click iron condor builder for the most popular strategy.

    Args:
        spot: Current spot price.
        vix: India VIX (affects wing width).
        days_to_expiry: Calendar DTE.
        lot_size: Shares per lot.
        strike_step: Strike interval.

    Returns:
        Complete iron condor with strikes, premiums, max P&L, and prob profit.
    """
    from diamond_options.pricing.black_scholes import price_option as _price
    from diamond_options.pricing.payoff import Leg, analyze_payoff as _analyze, expected_value
    from diamond_options.strategy.sizing import vix_adjusted_multiplier

    T = days_to_expiry / 365.0
    sigma = vix / 100.0 if vix > 1 else 0.15

    # Compute ATM and strikes
    atm = round(spot / strike_step) * strike_step
    # Widen strikes if VIX > 20
    width_multiplier = 3 if vix <= 20 else 4
    put_sell = atm - 2 * strike_step
    put_buy = atm - width_multiplier * strike_step
    call_sell = atm + 2 * strike_step
    call_buy = atm + width_multiplier * strike_step

    # Price each leg with Black-Scholes
    pb_bs = _price(spot, put_buy, T, 0.065, sigma, "PE")
    ps_bs = _price(spot, put_sell, T, 0.065, sigma, "PE")
    cs_bs = _price(spot, call_sell, T, 0.065, sigma, "CE")
    cb_bs = _price(spot, call_buy, T, 0.065, sigma, "CE")

    legs = [
        Leg(put_buy, "PE", "BUY", pb_bs.price, 1, lot_size),
        Leg(put_sell, "PE", "SELL", ps_bs.price, 1, lot_size),
        Leg(call_sell, "CE", "SELL", cs_bs.price, 1, lot_size),
        Leg(call_buy, "CE", "BUY", cb_bs.price, 1, lot_size),
    ]

    analysis = _analyze(legs, spot)
    ev = expected_value(legs, spot, T=T, r=0.065, sigma=sigma)

    return {
        "strategy": "Iron Condor",
        "legs": [{"strike": l.strike, "type": l.option_type, "action": l.action,
                  "premium": round(l.premium, 2)} for l in legs],
        "max_profit": round(analysis.max_profit, 2) if analysis.max_profit != float("inf") else "Unlimited",
        "max_loss": round(analysis.max_loss, 2) if analysis.max_loss != float("-inf") else "Unlimited",
        "breakevens": analysis.breakevens,
        "net_premium": round(analysis.net_premium, 2),
        "prob_profit": ev["prob_profit"],
        "vix_size_multiplier": vix_adjusted_multiplier(vix),
    }


@mcp.tool()
def quick_straddle(
    spot: float,
    days_to_expiry: int = 7,
    lot_size: int = 65,
    strike_step: float = 50.0,
    direction: str = "short",
) -> dict:
    """Quick straddle setup (long or short) with ATM strikes.

    Args:
        spot: Current spot.
        days_to_expiry: Calendar DTE.
        lot_size: Shares per lot.
        strike_step: Strike interval.
        direction: "short" (sell premium) or "long" (buy volatility).

    Returns:
        Straddle with premiums and analysis.
    """
    from diamond_options.pricing.black_scholes import price_option as _price
    from diamond_options.pricing.payoff import Leg, analyze_payoff as _analyze, expected_value

    if direction not in ("short", "long"):
        return {"error": f"Unknown direction: {direction}. Use 'short' or 'long'."}

    T = days_to_expiry / 365.0
    atm = round(spot / strike_step) * strike_step
    action = "SELL" if direction == "short" else "BUY"

    # Price ATM call and put
    call_bs = _price(spot, atm, T, 0.065, 0.13, "CE")
    put_bs = _price(spot, atm, T, 0.065, 0.13, "PE")

    legs = [
        Leg(atm, "CE", action, call_bs.price, 1, lot_size),
        Leg(atm, "PE", action, put_bs.price, 1, lot_size),
    ]

    analysis = _analyze(legs, spot)
    ev = expected_value(legs, spot, T=T, r=0.065, sigma=0.13)

    return {
        "strategy": f"{direction.title()} Straddle",
        "legs": [{"strike": l.strike, "type": l.option_type, "action": l.action,
                  "premium": round(l.premium, 2)} for l in legs],
        "max_profit": round(analysis.max_profit, 2) if analysis.max_profit != float("inf") else "Unlimited",
        "max_loss": round(analysis.max_loss, 2) if analysis.max_loss != float("-inf") else "Unlimited",
        "breakevens": analysis.breakevens,
        "net_premium": round(analysis.net_premium, 2),
        "prob_profit": ev["prob_profit"],
    }


@mcp.tool()
def option_chain_strikes(
    spot: float,
    strike_step: float = 50.0,
    num_strikes: int = 10,
) -> dict:
    """Generate strike price ladder around spot.

    Quick helper to see available strikes without fetching full chain.

    Args:
        spot: Current spot price.
        strike_step: Strike interval.
        num_strikes: OTM strikes per side.

    Returns:
        ATM strike and full strike ladder.
    """
    from diamond_options.data.options_chain import generate_strikes

    strikes = generate_strikes(spot, strike_step, num_strikes)
    atm = round(spot / strike_step) * strike_step

    return {
        "spot": spot,
        "atm_strike": atm,
        "strike_step": strike_step,
        "strikes": strikes,
        "count": len(strikes),
    }


@mcp.tool()
def sector_fno_stocks(sector: str) -> dict:
    """Get all F&O stocks in a specific sector.

    Args:
        sector: Sector name (e.g., "Technology", "Financial Services", "Energy").

    Returns:
        Stocks in sector with lot sizes.
    """
    from diamond_options.data.universe import get_fno_by_sector

    stocks = get_fno_by_sector(sector)
    return {
        "sector": sector,
        "count": len(stocks),
        "stocks": [
            {"symbol": s.symbol, "lot_size": s.lot_size}
            for s in stocks
        ],
    }


# ═══════════════════════════════════════════════════════════════
# CROSS-ENGINE INTEGRATION (Phase 6)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def stock_holdings_for_options(
    strategy: str = "gods_plan",
    db_path: str = "",
) -> dict:
    """Read equity holdings from diamond_stock_engine for options overlay.

    Shows which holdings are F&O-eligible and can be used for
    covered calls, protective puts, or collars.

    Args:
        strategy: Stock engine strategy name (default: gods_plan).
        db_path: Explicit path to stock engine .db file (optional).

    Returns:
        Portfolio with F&O-eligible holdings.
    """
    from diamond_options.integration.stock_bridge import get_stock_holdings
    from pathlib import Path

    portfolio = get_stock_holdings(
        strategy=strategy,
        db_path=Path(db_path) if db_path else None,
    )

    return {
        "strategy": portfolio.strategy,
        "total_value": portfolio.total_value,
        "cash": portfolio.cash,
        "nav": portfolio.nav,
        "num_stocks": portfolio.num_stocks,
        "fno_eligible_count": len(portfolio.fno_eligible),
        "fno_eligible_value": portfolio.fno_eligible_value,
        "fno_eligible_pct": portfolio.fno_eligible_pct,
        "holdings": [
            {
                "ticker": h.ticker,
                "fno_symbol": h.fno_symbol,
                "shares": h.shares,
                "avg_price": h.avg_price,
                "current_price": h.current_price,
                "market_value": h.market_value,
                "unrealized_pnl": h.unrealized_pnl,
                "weight_pct": h.weight_pct,
                "fno_eligible": h in portfolio.fno_eligible,
            }
            for h in portfolio.holdings
        ],
    }


@mcp.tool()
def covered_call_suggestions(
    ticker: str,
    shares: int,
    current_price: float,
    avg_price: float = 0.0,
    days_to_expiry: int = 30,
    volatility: float = 0.25,
    num_suggestions: int = 3,
) -> dict:
    """Suggest covered call strikes for a stock you own.

    Requires owning at least 1 lot worth of shares.

    Args:
        ticker: NSE symbol (e.g., RELIANCE, TCS).
        shares: Number of shares held.
        current_price: Current market price.
        avg_price: Your average buy price (for P&L context).
        days_to_expiry: Target DTE for the call.
        volatility: Estimated IV for the stock.
        num_suggestions: Number of strike suggestions.

    Returns:
        Covered call setups with premium, yield, and protection.
    """
    from diamond_options.integration.stock_bridge import StockHolding
    from diamond_options.integration.overlay import suggest_covered_calls

    if avg_price <= 0:
        avg_price = current_price

    holding = StockHolding(
        ticker=f"{ticker.upper()}.NS",
        fno_symbol=ticker.upper(),
        shares=shares,
        avg_price=avg_price,
        current_price=current_price,
        market_value=shares * current_price,
        unrealized_pnl=(current_price - avg_price) * shares,
        unrealized_pnl_pct=((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0,
        weight_pct=100,
    )

    setups = suggest_covered_calls(
        holding, days_to_expiry=days_to_expiry,
        volatility=volatility, num_suggestions=num_suggestions,
    )

    if not setups:
        from diamond_options.data.universe import get_lot_size
        lot = get_lot_size(ticker.upper())
        return {
            "error": f"Need at least {lot} shares of {ticker.upper()} for covered calls (you have {shares})",
        }

    return {
        "ticker": ticker.upper(),
        "shares": shares,
        "current_price": current_price,
        "suggestions": [
            {
                "strike": s.strike,
                "premium": s.premium,
                "total_premium": s.total_premium,
                "lots_coverable": s.lots_coverable,
                "annualized_yield_pct": s.annualized_yield_pct,
                "downside_protection_pct": s.downside_protection_pct,
                "upside_cap": s.upside_cap,
                "breakeven": s.breakeven,
                "moneyness": s.moneyness,
                "delta": s.delta,
                "notes": s.notes,
            }
            for s in setups
        ],
    }


@mcp.tool()
def protective_put_suggestions(
    ticker: str,
    shares: int,
    current_price: float,
    days_to_expiry: int = 30,
    volatility: float = 0.25,
    num_suggestions: int = 3,
) -> dict:
    """Suggest protective put strikes to hedge a stock holding.

    Args:
        ticker: NSE symbol.
        shares: Shares held.
        current_price: Current price.
        days_to_expiry: Target DTE.
        volatility: Estimated IV.
        num_suggestions: Number of suggestions.

    Returns:
        Protective put setups with cost and protection levels.
    """
    from diamond_options.integration.stock_bridge import StockHolding
    from diamond_options.integration.overlay import suggest_protective_puts

    holding = StockHolding(
        ticker=f"{ticker.upper()}.NS",
        fno_symbol=ticker.upper(),
        shares=shares,
        avg_price=current_price,
        current_price=current_price,
        market_value=shares * current_price,
        unrealized_pnl=0,
        unrealized_pnl_pct=0,
        weight_pct=100,
    )

    setups = suggest_protective_puts(
        holding, days_to_expiry=days_to_expiry,
        volatility=volatility, num_suggestions=num_suggestions,
    )

    if not setups:
        return {"error": f"{ticker.upper()} is not F&O eligible or insufficient shares"}

    return {
        "ticker": ticker.upper(),
        "shares": shares,
        "current_price": current_price,
        "suggestions": [
            {
                "strike": s.strike,
                "premium": s.premium,
                "total_cost": s.total_cost,
                "cost_as_pct_of_holding": s.cost_as_pct_of_holding,
                "annualized_cost_pct": s.annualized_cost_pct,
                "max_loss_per_share": s.max_loss_per_share,
                "max_loss_total": s.max_loss_total,
                "protection_level_pct": s.protection_level_pct,
                "delta": s.delta,
                "notes": s.notes,
            }
            for s in setups
        ],
    }


@mcp.tool()
def collar_suggestion(
    ticker: str,
    shares: int,
    current_price: float,
    days_to_expiry: int = 30,
    volatility: float = 0.25,
    call_otm_pct: float = 5.0,
    put_otm_pct: float = 5.0,
) -> dict:
    """Suggest a collar (sell call + buy put) for a stock holding.

    A collar caps upside and floors downside, often near zero-cost.

    Args:
        ticker: NSE symbol.
        shares: Shares held.
        current_price: Current price.
        days_to_expiry: Target DTE.
        volatility: Estimated IV.
        call_otm_pct: Call strike % above spot (e.g., 5.0 for 5%).
        put_otm_pct: Put strike % below spot (e.g., 5.0 for 5%).

    Returns:
        Collar setup with net cost, max gain/loss.
    """
    from diamond_options.integration.stock_bridge import StockHolding
    from diamond_options.integration.overlay import suggest_collar

    holding = StockHolding(
        ticker=f"{ticker.upper()}.NS",
        fno_symbol=ticker.upper(),
        shares=shares,
        avg_price=current_price,
        current_price=current_price,
        market_value=shares * current_price,
        unrealized_pnl=0,
        unrealized_pnl_pct=0,
        weight_pct=100,
    )

    collar = suggest_collar(
        holding, days_to_expiry=days_to_expiry,
        volatility=volatility,
        call_otm_pct=call_otm_pct / 100,
        put_otm_pct=put_otm_pct / 100,
    )

    if not collar:
        return {"error": f"{ticker.upper()} not F&O eligible or insufficient shares for 1 lot"}

    return {
        "ticker": ticker.upper(),
        "shares": shares,
        "current_price": current_price,
        "collar": {
            "call_strike": collar.call_strike,
            "call_premium": collar.call_premium,
            "put_strike": collar.put_strike,
            "put_premium": collar.put_premium,
            "net_premium": collar.net_premium,
            "net_cost": collar.net_cost,
            "max_gain_per_share": collar.max_gain_per_share,
            "max_loss_per_share": collar.max_loss_per_share,
            "upside_cap_pct": collar.upside_cap_pct,
            "downside_floor_pct": collar.downside_floor_pct,
            "lots": collar.lots,
            "notes": collar.notes,
        },
    }


@mcp.tool()
def portfolio_hedge_analysis(
    portfolio_value: float,
    nifty_spot: float = 22500.0,
    portfolio_beta: float = 1.0,
    days_to_expiry: int = 30,
    volatility: float = 0.13,
    hedge_ratio: float = 1.0,
) -> dict:
    """Analyze how to hedge an equity portfolio using NIFTY options.

    Suggests protective puts, bear put spreads, and collars on NIFTY
    to hedge systematic risk of the entire equity portfolio.

    Args:
        portfolio_value: Total equity portfolio value in INR.
        nifty_spot: Current NIFTY spot.
        portfolio_beta: Portfolio beta to NIFTY (default 1.0).
        days_to_expiry: Hedge duration in days.
        volatility: NIFTY IV estimate.
        hedge_ratio: 1.0 = full hedge, 0.5 = half hedge.

    Returns:
        Hedge options with costs, protection levels, and comparison.
    """
    from diamond_options.integration.stock_bridge import StockPortfolio
    from diamond_options.integration.hedge import analyze_portfolio_hedge

    # Build a minimal portfolio for the analysis
    portfolio = StockPortfolio(
        strategy="custom",
        holdings=[],
        total_value=portfolio_value,
        cash=0,
        nav=portfolio_value,
        num_stocks=0,
        fno_eligible=[],
        fno_eligible_value=portfolio_value,
        fno_eligible_pct=100,
    )

    result = analyze_portfolio_hedge(
        portfolio,
        nifty_spot=nifty_spot,
        portfolio_beta=portfolio_beta,
        days_to_expiry=days_to_expiry,
        volatility=volatility,
        hedge_ratio=hedge_ratio,
    )

    return {
        "portfolio_value": result.portfolio_value,
        "beta": result.beta,
        "beta_adjusted_exposure": result.beta_adjusted_exposure,
        "nifty_lots_for_hedge": result.lots_to_hedge,
        "nifty_lots_partial": result.lots_partial_hedge,
        "hedge_notional": result.hedge_notional,
        "summary": result.summary,
        "options": [
            {
                "name": h.name,
                "strategy": h.strategy,
                "strike": h.strike,
                "strike_2": h.strike_2,
                "total_cost": h.total_cost,
                "cost_as_pct": h.cost_as_pct,
                "annualized_cost_pct": h.annualized_cost_pct,
                "protection_level": h.protection_level,
                "max_loss_hedged": h.max_loss_hedged,
                "lots": h.lots,
                "notes": h.notes,
            }
            for h in result.hedging_options
        ],
    }


@mcp.tool()
def covered_call_income_report(
    strategy: str = "gods_plan",
    db_path: str = "",
    days_to_expiry: int = 30,
    volatility: float = 0.25,
) -> dict:
    """Generate covered call income report for all F&O-eligible stock holdings.

    Shows potential monthly income from selling covered calls on each
    holding in the stock engine portfolio.

    Args:
        strategy: Stock engine strategy name.
        db_path: Explicit path to stock engine .db (optional).
        days_to_expiry: Target DTE for calls.
        volatility: Assumed IV for stock options.

    Returns:
        Per-stock income potential and portfolio-level yield.
    """
    from diamond_options.integration.stock_bridge import get_stock_holdings
    from diamond_options.integration.hedge import covered_call_income_report as _report
    from pathlib import Path

    portfolio = get_stock_holdings(
        strategy=strategy,
        db_path=Path(db_path) if db_path else None,
    )

    if portfolio.num_stocks == 0:
        return {"error": f"No holdings found for strategy '{strategy}'"}

    return _report(portfolio, days_to_expiry=days_to_expiry, volatility=volatility)


# ═══════════════════════════════════════════════════════════════
# LIVE OI ANALYSIS (Kite Bridge)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def build_live_chain(
    symbol: str = "NIFTY",
    spot: float = 0,
    expiry: str = "",
    kite_quotes: dict = {},
) -> dict:
    """Build an options chain from live Kite quote data.

    Pass the raw quotes dict from Kite's get_quotes MCP tool to build
    a full OptionsChain with OI, volume, and LTP data.

    Args:
        symbol: Underlying symbol (e.g., "NIFTY", "BANKNIFTY").
        spot: Current spot price.
        expiry: Expiry date as YYYY-MM-DD string.
        kite_quotes: Raw dict from Kite get_quotes (key: "NFO:SYMBOL...", value: quote dict).

    Returns:
        Chain summary with calls, puts, PCR, max pain.
    """
    from datetime import date as _date
    from diamond_options.data.kite_bridge import build_chain_from_kite_quotes

    if not kite_quotes:
        return {"error": "No kite_quotes provided. Pass raw Kite get_quotes response."}
    if not spot:
        return {"error": "spot price required"}

    try:
        exp = _date.fromisoformat(expiry) if expiry else None
    except ValueError:
        return {"error": f"Invalid expiry format: {expiry}. Use YYYY-MM-DD."}

    if exp is None:
        return {"error": "expiry required (YYYY-MM-DD)"}

    chain = build_chain_from_kite_quotes(symbol, spot, exp, kite_quotes)

    calls_data = [
        {"strike": q.strike, "ltp": q.ltp, "oi": q.open_interest, "volume": q.volume, "change": q.change}
        for q in chain.calls
    ]
    puts_data = [
        {"strike": q.strike, "ltp": q.ltp, "oi": q.open_interest, "volume": q.volume, "change": q.change}
        for q in chain.puts
    ]

    return {
        "symbol": chain.symbol,
        "spot": chain.spot_price,
        "expiry": str(chain.expiry),
        "num_calls": len(chain.calls),
        "num_puts": len(chain.puts),
        "pcr_oi": round(chain.pcr_oi() or 0, 3),
        "max_pain": chain.max_pain(),
        "total_call_oi": sum(q.open_interest for q in chain.calls),
        "total_put_oi": sum(q.open_interest for q in chain.puts),
        "calls": calls_data,
        "puts": puts_data,
    }


@mcp.tool()
def live_oi_analysis(
    symbol: str = "NIFTY",
    spot: float = 0,
    expiry: str = "",
    kite_quotes: dict = {},
    top_n: int = 10,
) -> dict:
    """Comprehensive OI analysis from live Kite data.

    Identifies support/resistance levels, call walls, put bases,
    max pain, PCR, and key OI levels — all from live market data.

    Args:
        symbol: Underlying symbol.
        spot: Current spot price.
        expiry: Expiry date (YYYY-MM-DD).
        kite_quotes: Raw Kite quotes dict.
        top_n: Number of top OI levels to return.

    Returns:
        Full OI analysis with walls, support, resistance, PCR.
    """
    from datetime import date as _date
    from diamond_options.data.kite_bridge import build_chain_from_kite_quotes, analyze_oi

    if not kite_quotes or not spot:
        return {"error": "kite_quotes and spot are required"}

    try:
        exp = _date.fromisoformat(expiry)
    except (ValueError, TypeError):
        return {"error": f"Invalid expiry: {expiry}. Use YYYY-MM-DD."}

    chain = build_chain_from_kite_quotes(symbol, spot, exp, kite_quotes)
    analysis = analyze_oi(chain, top_n=top_n)

    return {
        "symbol": symbol,
        "spot": spot,
        "expiry": expiry,
        "max_pain": analysis.max_pain,
        "pcr_oi": analysis.pcr_oi,
        "total_call_oi": analysis.total_call_oi,
        "total_put_oi": analysis.total_put_oi,
        "call_wall": {"strike": analysis.call_wall, "oi": analysis.call_wall_oi},
        "put_base": {"strike": analysis.put_base, "oi": analysis.put_base_oi},
        "support_levels": analysis.support_levels,
        "resistance_levels": analysis.resistance_levels,
        "key_levels": [
            {
                "strike": lv.strike,
                "call_oi": lv.call_oi,
                "put_oi": lv.put_oi,
                "pcr": lv.pcr,
                "net_oi": lv.net_oi,
            }
            for lv in analysis.key_levels
        ],
    }


@mcp.tool()
def oi_walls(
    symbol: str = "NIFTY",
    spot: float = 0,
    expiry: str = "",
    kite_quotes: dict = {},
    threshold: float = 2.0,
) -> dict:
    """Detect OI walls (unusually high OI acting as support/resistance).

    An OI wall is a strike where open interest is significantly above
    the average, acting as a magnet or barrier for price movement.

    Args:
        symbol: Underlying symbol.
        spot: Current spot price.
        expiry: Expiry date (YYYY-MM-DD).
        kite_quotes: Raw Kite quotes dict.
        threshold: Multiplier above average to qualify as wall (default 2.0).

    Returns:
        Call walls (resistance), put walls (support), and interpretation.
    """
    from datetime import date as _date
    from diamond_options.data.kite_bridge import build_chain_from_kite_quotes, detect_oi_walls

    if not kite_quotes or not spot:
        return {"error": "kite_quotes and spot are required"}

    try:
        exp = _date.fromisoformat(expiry)
    except (ValueError, TypeError):
        return {"error": f"Invalid expiry: {expiry}. Use YYYY-MM-DD."}

    chain = build_chain_from_kite_quotes(symbol, spot, exp, kite_quotes)
    walls = detect_oi_walls(chain, spot, threshold_multiplier=threshold)

    return {
        "symbol": symbol,
        "spot": spot,
        "expiry": expiry,
        "call_walls": walls["call_walls"],
        "put_walls": walls["put_walls"],
        "nearest_call_wall": walls.get("nearest_call_wall"),
        "nearest_put_wall": walls.get("nearest_put_wall"),
        "interpretation": walls["interpretation"],
    }


@mcp.tool()
def parse_kite_symbol_tool(tradingsymbol: str) -> dict:
    """Parse a Kite tradingsymbol into its components.

    Useful for debugging and understanding Kite instrument keys.

    Args:
        tradingsymbol: Kite symbol (e.g., "NIFTY2631024450CE").

    Returns:
        Parsed components: symbol, expiry, strike, option_type.
    """
    from diamond_options.data.kite_bridge import parse_kite_symbol

    result = parse_kite_symbol(tradingsymbol)
    if result is None:
        return {"error": f"Could not parse symbol: {tradingsymbol}"}

    # Convert date to string for JSON serialization
    parsed = dict(result)
    if "expiry" in parsed:
        parsed["expiry"] = str(parsed["expiry"])
    return parsed


# ═══════════════════════════════════════════════════════════════
# POSITION SYNC (Kite → Engine)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def sync_kite_positions(kite_positions: list[dict] = []) -> dict:
    """Sync live positions from Kite broker into engine format.

    Pass the raw list from Kite's get_positions MCP tool.
    Returns parsed positions with P&L, lot counts, and spread detection.

    Args:
        kite_positions: Raw list from Kite get_positions tool.

    Returns:
        Portfolio summary with positions, P&L, spreads.
    """
    from diamond_options.data.position_sync import sync_positions, detect_spreads

    if not kite_positions:
        return {"error": "No positions provided. Pass raw Kite get_positions response.",
                "positions": [], "total_pnl": 0}

    portfolio = sync_positions(kite_positions)

    positions_data = []
    for p in portfolio.positions:
        positions_data.append({
            "symbol": p.symbol,
            "tradingsymbol": p.tradingsymbol,
            "strike": p.strike,
            "option_type": p.option_type,
            "expiry": str(p.expiry) if p.expiry else None,
            "quantity": p.quantity,
            "lots": p.lots,
            "avg_price": p.avg_price,
            "ltp": p.ltp,
            "pnl": round(p.pnl, 2),
            "m2m": round(p.m2m, 2),
            "side": "LONG" if p.is_long else "SHORT",
            "product": p.product,
        })

    spreads = detect_spreads(portfolio.positions)
    spread_summary = {
        group: [p.tradingsymbol for p in positions]
        for group, positions in spreads.items()
        if len(positions) > 1
    }

    return {
        "num_positions": len(portfolio.positions),
        "num_long": portfolio.num_long,
        "num_short": portfolio.num_short,
        "total_pnl": round(portfolio.total_pnl, 2),
        "total_m2m": round(portfolio.total_m2m, 2),
        "net_quantity_by_symbol": portfolio.net_quantity_by_symbol,
        "positions": positions_data,
        "spreads_detected": spread_summary,
        "num_futures": len(portfolio.futures_positions),
    }


@mcp.tool()
def compare_kite_vs_ledger(kite_positions: list[dict] = []) -> dict:
    """Compare Kite broker positions with local ledger.

    Identifies mismatches: positions in Kite but not ledger (untracked),
    positions in ledger but not Kite (stale), and quantity differences.

    Args:
        kite_positions: Raw list from Kite get_positions tool.

    Returns:
        Reconciliation report with matched, untracked, stale positions.
    """
    from diamond_options.data.position_sync import sync_positions, compare_positions
    from diamond_options.data.ledger import OptionsLedger

    if not kite_positions:
        return {"error": "No kite_positions provided"}

    portfolio = sync_positions(kite_positions)

    try:
        ledger = OptionsLedger()
        ledger_positions = ledger.get_positions()
    except Exception:
        ledger_positions = []

    result = compare_positions(portfolio.positions, ledger_positions)
    return result


# ═══════════════════════════════════════════════════════════════
# LIVE IV & GREEKS (from market prices)
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def live_greeks(
    spot: float = 0,
    expiry: str = "",
    kite_quotes: dict = {},
) -> dict:
    """Compute real IV and Greeks from live market prices.

    Solves implied volatility from Kite LTP using Newton-Raphson,
    then computes all Greeks (delta, gamma, theta, vega, rho).

    Args:
        spot: Current spot price.
        expiry: Expiry date (YYYY-MM-DD).
        kite_quotes: Raw Kite quotes dict.

    Returns:
        Per-strike IV and Greeks for all options in the chain.
    """
    from datetime import date as _date
    from diamond_options.pricing.live_greeks import compute_chain_greeks, chain_greeks_summary

    if not kite_quotes or not spot:
        return {"error": "spot and kite_quotes are required"}

    try:
        exp = _date.fromisoformat(expiry)
    except (ValueError, TypeError):
        return {"error": f"Invalid expiry: {expiry}. Use YYYY-MM-DD."}

    greeks_list = compute_chain_greeks(spot, exp, kite_quotes)

    if not greeks_list:
        return {"error": "Could not compute IV for any options. Check quotes."}

    summary = chain_greeks_summary(greeks_list, spot)

    options_data = []
    for g in greeks_list:
        options_data.append({
            "strike": g.strike,
            "type": g.option_type,
            "ltp": g.ltp,
            "iv": round(g.iv * 100, 2) if g.iv else None,
            "delta": round(g.delta, 4) if g.delta is not None else None,
            "gamma": round(g.gamma, 6) if g.gamma is not None else None,
            "theta": round(g.theta, 2) if g.theta is not None else None,
            "vega": round(g.vega, 2) if g.vega is not None else None,
            "oi": g.oi,
            "moneyness": g.moneyness,
            "intrinsic": round(g.intrinsic_value, 2),
            "time_value": round(g.time_value, 2),
        })

    return {
        "spot": spot,
        "expiry": expiry,
        "num_options": len(greeks_list),
        "summary": summary,
        "options": options_data,
    }


@mcp.tool()
def compute_option_greeks(
    spot: float = 0,
    strike: float = 0,
    expiry: str = "",
    option_type: str = "CE",
    market_price: float = 0,
) -> dict:
    """Compute IV and Greeks for a single option from its market price.

    Uses Newton-Raphson to solve IV from the market price, then
    computes all Greeks from that IV.

    Args:
        spot: Current spot price.
        strike: Option strike price.
        expiry: Expiry date (YYYY-MM-DD).
        option_type: CE or PE.
        market_price: Current market LTP of the option.

    Returns:
        IV and all Greeks for the option.
    """
    from datetime import date as _date
    from diamond_options.pricing.live_greeks import compute_greeks_for_quote

    if not all([spot, strike, market_price]):
        return {"error": "spot, strike, and market_price are required"}

    try:
        exp = _date.fromisoformat(expiry)
    except (ValueError, TypeError):
        return {"error": f"Invalid expiry: {expiry}. Use YYYY-MM-DD."}

    result = compute_greeks_for_quote(
        spot=spot, strike=strike, expiry=exp,
        option_type=option_type.upper(), ltp=market_price,
    )

    if result is None:
        return {"error": "Could not solve IV for this option. Price may be too low or inconsistent."}

    return {
        "strike": result.strike,
        "type": result.option_type,
        "ltp": result.ltp,
        "iv": round(result.iv * 100, 2) if result.iv else None,
        "iv_decimal": result.iv,
        "delta": round(result.delta, 4) if result.delta is not None else None,
        "gamma": round(result.gamma, 6) if result.gamma is not None else None,
        "theta": round(result.theta, 2) if result.theta is not None else None,
        "vega": round(result.vega, 2) if result.vega is not None else None,
        "rho": round(result.rho, 4) if result.rho is not None else None,
        "moneyness": result.moneyness,
        "intrinsic_value": round(result.intrinsic_value, 2),
        "time_value": round(result.time_value, 2),
    }


# ═══════════════════════════════════════════════════════════════
# EVENT CALENDAR
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
def upcoming_market_events(
    days_ahead: int = 14,
    event_type: str = "",
) -> dict:
    """Get upcoming market events that affect options pricing.

    Covers RBI policy, earnings seasons, Union Budget, FOMC,
    economic data releases, and NSE holidays.

    Args:
        days_ahead: Number of days to look ahead (default 14).
        event_type: Filter by type: rbi_policy, earnings, budget, expiry, holiday, economic_data, global.

    Returns:
        List of upcoming events with impact levels.
    """
    from diamond_options.data.events import get_upcoming_events

    event_types = [event_type] if event_type else None
    events = get_upcoming_events(days_ahead=days_ahead, event_types=event_types)

    return {
        "days_ahead": days_ahead,
        "count": len(events),
        "events": [
            {
                "date": str(e.date),
                "type": e.event_type,
                "title": e.title,
                "description": e.description,
                "impact": e.impact,
                "affected_symbols": e.affected_symbols,
            }
            for e in events
        ],
    }


@mcp.tool()
def event_context(days_ahead: int = 7) -> dict:
    """Get event-aware trading context for today.

    Returns whether today is a high-impact day, upcoming events,
    earnings season status, and IV impact notes.

    Args:
        days_ahead: How many days to look ahead (default 7).

    Returns:
        Trading context with event awareness.
    """
    from diamond_options.data.events import event_aware_context

    return event_aware_context(days_ahead=days_ahead)


@mcp.tool()
def events_for_symbol(symbol: str, days_ahead: int = 30) -> dict:
    """Get events affecting a specific symbol.

    Includes symbol-specific events plus broad market events
    (NIFTY events affect all F&O stocks).

    Args:
        symbol: F&O symbol (e.g., NIFTY, RELIANCE).
        days_ahead: Days to look ahead (default 30).

    Returns:
        Events affecting this symbol.
    """
    from diamond_options.data.events import get_events_for_symbol

    events = get_events_for_symbol(symbol.upper(), days_ahead=days_ahead)

    return {
        "symbol": symbol.upper(),
        "days_ahead": days_ahead,
        "count": len(events),
        "events": [
            {
                "date": str(e.date),
                "type": e.event_type,
                "title": e.title,
                "impact": e.impact,
            }
            for e in events
        ],
    }


@mcp.tool()
def earnings_calendar(symbol: str = "") -> dict:
    """Get earnings season calendar.

    Shows quarterly earnings windows. Useful for planning
    volatility trades around results season.

    Args:
        symbol: Optional symbol to filter (default: all).

    Returns:
        Earnings season dates and affected symbols.
    """
    from diamond_options.data.events import get_earnings_calendar

    events = get_earnings_calendar(symbol.upper() if symbol else "")

    return {
        "symbol": symbol.upper() if symbol else "ALL",
        "count": len(events),
        "earnings_windows": [
            {
                "date": str(e.date),
                "title": e.title,
                "description": e.description,
                "affected_symbols": e.affected_symbols,
            }
            for e in events
        ],
    }


if __name__ == "__main__":
    mcp.run()
