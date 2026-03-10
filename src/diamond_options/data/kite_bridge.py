"""Kite MCP bridge — fetch live market data from Kite via MCP tools.

Provides functions to convert Kite instrument/quote data into Diamond engine
data structures (OptionsChain, OptionQuote). Designed for dual-mode operation:
use Kite when available, fall back to yfinance/synthetic.

This module does NOT import the Kite MCP SDK directly. Instead, it provides
parsers that accept raw Kite API response dicts (as returned by MCP tools)
and convert them into engine-native objects.

Usage in MCP server:
    1. Call Kite MCP tools (get_quotes, search_instruments) to get raw data
    2. Pass raw dicts to functions here to build OptionsChain objects
    3. Use the OptionsChain for OI analysis, max pain, PCR, etc.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

from diamond_options.data.futures_chain import FuturesChain, FuturesQuote
from diamond_options.data.options_chain import OptionQuote, OptionsChain

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OILevel:
    """Open interest at a specific strike — used for support/resistance analysis."""
    strike: float
    call_oi: int
    put_oi: int
    pcr: float          # put OI / call OI at this strike
    net_oi: int          # put_oi - call_oi (positive = put-heavy = support)


@dataclass(frozen=True)
class OIAnalysis:
    """Comprehensive OI-based market structure analysis."""
    max_pain: float
    pcr_oi: float                  # Overall put-call ratio by OI
    total_call_oi: int
    total_put_oi: int
    call_wall: float               # Strike with highest call OI (resistance)
    put_base: float                # Strike with highest put OI (support)
    call_wall_oi: int
    put_base_oi: int
    key_levels: list[OILevel]      # Top OI levels sorted by total OI
    support_levels: list[float]    # Strikes with high put OI (support)
    resistance_levels: list[float] # Strikes with high call OI (resistance)


def parse_kite_symbol(tradingsymbol: str) -> dict | None:
    """Parse a Kite tradingsymbol into components.

    Examples:
        NIFTY2631024450CE → {symbol: NIFTY, expiry: 2026-03-10, strike: 24450, type: CE}
        NIFTY26MAR24450CE → {symbol: NIFTY, expiry: 2026-03-??, strike: 24450, type: CE}
    """
    # Weekly format: NIFTY2631024450CE (SYMBOL + YYMMDD + STRIKE + TYPE)
    m = re.match(
        r'^([A-Z]+)(\d{2})(\d)(\d{2})(\d+)(CE|PE)$',
        tradingsymbol,
    )
    if m:
        symbol = m.group(1)
        year = 2000 + int(m.group(2))
        month = int(m.group(3))
        day = int(m.group(4))
        strike = float(m.group(5))
        option_type = m.group(6)
        try:
            expiry = date(year, month, day)
        except ValueError:
            return None
        return {
            "symbol": symbol,
            "expiry": expiry,
            "strike": strike,
            "option_type": option_type,
        }

    # Monthly format: NIFTY26MAR24450CE
    m = re.match(
        r'^([A-Z]+)(\d{2})([A-Z]{3})(\d+)(CE|PE)$',
        tradingsymbol,
    )
    if m:
        symbol = m.group(1)
        year = 2000 + int(m.group(2))
        month_str = m.group(3)
        strike = float(m.group(4))
        option_type = m.group(5)
        months = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
        }
        month = months.get(month_str, 1)
        return {
            "symbol": symbol,
            "year": year,
            "month": month,
            "strike": strike,
            "option_type": option_type,
        }

    return None


def kite_quote_to_option_quote(
    kite_key: str,
    kite_quote: dict,
    expiry: date,
) -> OptionQuote | None:
    """Convert a single Kite quote dict to an OptionQuote.

    Args:
        kite_key: Kite instrument key (e.g., "NFO:NIFTY2631024450CE")
        kite_quote: Kite quote response dict with last_price, oi, ohlc, etc.
        expiry: Expiry date for this contract.

    Returns:
        OptionQuote or None if parsing fails.
    """
    tradingsymbol = kite_key.split(":")[-1] if ":" in kite_key else kite_key
    parsed = parse_kite_symbol(tradingsymbol)
    if not parsed:
        return None

    ohlc = kite_quote.get("ohlc", {})
    prev_close = ohlc.get("close", 0)
    last_price = kite_quote.get("last_price", 0)
    change = last_price - prev_close if prev_close > 0 else 0
    change_pct = (change / prev_close * 100) if prev_close > 0 else 0

    return OptionQuote(
        strike=parsed["strike"],
        option_type=parsed["option_type"],
        expiry=expiry,
        ltp=last_price,
        open_interest=kite_quote.get("oi", 0),
        volume=kite_quote.get("volume", 0),
        change=round(change, 2),
        change_pct=round(change_pct, 2),
    )


def build_chain_from_kite_quotes(
    symbol: str,
    spot: float,
    expiry: date,
    kite_quotes: dict[str, dict],
) -> OptionsChain:
    """Build an OptionsChain from a batch of Kite quote responses.

    Args:
        symbol: Underlying symbol (e.g., "NIFTY").
        spot: Current spot price.
        expiry: Expiry date.
        kite_quotes: Dict of {kite_key: kite_quote_dict} from get_quotes.

    Returns:
        Complete OptionsChain with live OI, LTP, volume data.
    """
    calls = []
    puts = []

    for kite_key, quote_data in kite_quotes.items():
        oq = kite_quote_to_option_quote(kite_key, quote_data, expiry)
        if oq is None:
            continue
        if oq.option_type == "CE":
            calls.append(oq)
        else:
            puts.append(oq)

    calls.sort(key=lambda q: q.strike)
    puts.sort(key=lambda q: q.strike)

    ts = kite_quotes.get(next(iter(kite_quotes), ""), {}).get("timestamp", "")

    return OptionsChain(
        symbol=symbol,
        expiry=expiry,
        spot_price=spot,
        timestamp=ts,
        calls=calls,
        puts=puts,
    )


def analyze_oi(chain: OptionsChain, top_n: int = 10) -> OIAnalysis:
    """Perform comprehensive OI analysis on a chain.

    Identifies support/resistance levels, max pain, PCR, and OI walls.

    Args:
        chain: OptionsChain with live OI data.
        top_n: Number of top OI levels to include.

    Returns:
        OIAnalysis with support/resistance levels and key metrics.
    """
    # Build per-strike OI map
    call_oi_map: dict[float, int] = {}
    put_oi_map: dict[float, int] = {}

    for q in chain.calls:
        call_oi_map[q.strike] = q.open_interest
    for q in chain.puts:
        put_oi_map[q.strike] = q.open_interest

    all_strikes = sorted(set(call_oi_map.keys()) | set(put_oi_map.keys()))

    # Build OI levels
    oi_levels: list[OILevel] = []
    for strike in all_strikes:
        c_oi = call_oi_map.get(strike, 0)
        p_oi = put_oi_map.get(strike, 0)
        pcr = p_oi / c_oi if c_oi > 0 else float("inf") if p_oi > 0 else 0.0
        oi_levels.append(OILevel(
            strike=strike,
            call_oi=c_oi,
            put_oi=p_oi,
            pcr=round(pcr, 2) if pcr != float("inf") else 999.9,
            net_oi=p_oi - c_oi,
        ))

    # Totals
    total_call_oi = sum(l.call_oi for l in oi_levels)
    total_put_oi = sum(l.put_oi for l in oi_levels)
    pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0.0

    # Call wall (highest call OI = resistance)
    call_wall_level = max(oi_levels, key=lambda l: l.call_oi) if oi_levels else None
    put_base_level = max(oi_levels, key=lambda l: l.put_oi) if oi_levels else None

    # Support levels: strikes with high put OI (above median)
    if oi_levels:
        put_ois = sorted([l.put_oi for l in oi_levels], reverse=True)
        call_ois = sorted([l.call_oi for l in oi_levels], reverse=True)
        put_threshold = put_ois[min(4, len(put_ois) - 1)] if put_ois else 0
        call_threshold = call_ois[min(4, len(call_ois) - 1)] if call_ois else 0
    else:
        put_threshold = call_threshold = 0

    support_levels = sorted(
        [l.strike for l in oi_levels if l.put_oi >= put_threshold and l.put_oi > 0],
    )
    resistance_levels = sorted(
        [l.strike for l in oi_levels if l.call_oi >= call_threshold and l.call_oi > 0],
    )

    # Top OI levels by total OI
    key_levels = sorted(oi_levels, key=lambda l: l.call_oi + l.put_oi, reverse=True)[:top_n]

    # Max pain from chain
    max_pain = chain.max_pain() or chain.spot_price

    return OIAnalysis(
        max_pain=max_pain,
        pcr_oi=round(pcr_oi, 3),
        total_call_oi=total_call_oi,
        total_put_oi=total_put_oi,
        call_wall=call_wall_level.strike if call_wall_level else 0,
        put_base=put_base_level.strike if put_base_level else 0,
        call_wall_oi=call_wall_level.call_oi if call_wall_level else 0,
        put_base_oi=put_base_level.put_oi if put_base_level else 0,
        key_levels=key_levels,
        support_levels=support_levels,
        resistance_levels=resistance_levels,
    )


def detect_oi_walls(
    chain: OptionsChain,
    spot: float,
    threshold_multiplier: float = 2.0,
) -> dict:
    """Detect OI walls (unusually high OI at specific strikes).

    An OI wall is a strike with OI significantly above the average,
    acting as a magnet/barrier for price movement.

    Args:
        chain: OptionsChain with live OI data.
        spot: Current spot price.
        threshold_multiplier: How many times above average to qualify as a wall.

    Returns:
        Dict with call_walls, put_walls, and their implications.
    """
    call_ois = [(q.strike, q.open_interest) for q in chain.calls if q.open_interest > 0]
    put_ois = [(q.strike, q.open_interest) for q in chain.puts if q.open_interest > 0]

    if not call_ois or not put_ois:
        return {"call_walls": [], "put_walls": [], "interpretation": "Insufficient OI data"}

    avg_call_oi = sum(oi for _, oi in call_ois) / len(call_ois)
    avg_put_oi = sum(oi for _, oi in put_ois) / len(put_ois)

    call_walls = [
        {"strike": strike, "oi": oi, "ratio_vs_avg": round(oi / avg_call_oi, 1)}
        for strike, oi in call_ois
        if oi >= avg_call_oi * threshold_multiplier and strike > spot
    ]
    put_walls = [
        {"strike": strike, "oi": oi, "ratio_vs_avg": round(oi / avg_put_oi, 1)}
        for strike, oi in put_ois
        if oi >= avg_put_oi * threshold_multiplier and strike < spot
    ]

    call_walls.sort(key=lambda w: w["oi"], reverse=True)
    put_walls.sort(key=lambda w: w["oi"], reverse=True)

    # Interpretation
    nearest_call_wall = call_walls[0]["strike"] if call_walls else None
    nearest_put_wall = put_walls[0]["strike"] if put_walls else None

    parts = []
    if nearest_call_wall:
        dist = nearest_call_wall - spot
        parts.append(f"Call wall at {nearest_call_wall:.0f} ({dist:.0f} pts above spot) — resistance")
    if nearest_put_wall:
        dist = spot - nearest_put_wall
        parts.append(f"Put wall at {nearest_put_wall:.0f} ({dist:.0f} pts below spot) — support")
    if nearest_call_wall and nearest_put_wall:
        range_width = nearest_call_wall - nearest_put_wall
        parts.append(f"OI-implied range: {nearest_put_wall:.0f} - {nearest_call_wall:.0f} ({range_width:.0f} pts)")

    return {
        "call_walls": call_walls[:5],
        "put_walls": put_walls[:5],
        "nearest_call_wall": nearest_call_wall,
        "nearest_put_wall": nearest_put_wall,
        "interpretation": ". ".join(parts) if parts else "No significant OI walls detected",
    }


def get_lot_size_from_kite(instrument_data: dict) -> int:
    """Extract lot size from a Kite instrument response."""
    return instrument_data.get("lot_size", 0)


def get_expiry_from_kite(instrument_data: dict) -> date | None:
    """Extract expiry date from a Kite instrument response."""
    exp_str = instrument_data.get("expiry_date", "")
    if exp_str:
        try:
            return date.fromisoformat(exp_str)
        except ValueError:
            pass
    return None


# --- Futures symbol parsing and chain building ---


def parse_futures_symbol(tradingsymbol: str) -> dict | None:
    """Parse a Kite futures tradingsymbol into components.

    Examples:
        NIFTY26MARFUT → {symbol: NIFTY, year: 2026, month: 3, instrument: FUT}
        NIFTY26MAR26FUT → same format (some brokers use YYMMMDD)
        RELIANCE26MARFUT → {symbol: RELIANCE, year: 2026, month: 3, instrument: FUT}
        NIFTY2632624500CE → returns None (this is an option, not a futures)

    Args:
        tradingsymbol: Raw Kite tradingsymbol.

    Returns:
        Dict with symbol, year, month, instrument fields, or None if not futures.
    """
    # Exclude options (end in CE/PE)
    if tradingsymbol.endswith("CE") or tradingsymbol.endswith("PE"):
        return None

    # Standard format: SYMBOL + YY + MMM + FUT
    # e.g., NIFTY26MARFUT, RELIANCE26APRFUT
    m = re.match(
        r"^([A-Z&]+)(\d{2})([A-Z]{3})FUT$",
        tradingsymbol,
    )
    if m:
        symbol = m.group(1)
        year = 2000 + int(m.group(2))
        month_str = m.group(3)
        months = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
        }
        month = months.get(month_str)
        if month is None:
            return None
        return {
            "symbol": symbol,
            "year": year,
            "month": month,
            "instrument": "FUT",
        }

    return None


def kite_quote_to_futures_quote(
    kite_key: str,
    kite_quote: dict,
    expiry: date,
    spot_price: float,
    lot_size: int = 0,
) -> FuturesQuote | None:
    """Convert a Kite quote dict to a FuturesQuote.

    Args:
        kite_key: Kite instrument key (e.g., "NFO:NIFTY26MARFUT").
        kite_quote: Kite quote response dict.
        expiry: Expiry date for this contract.
        spot_price: Current spot price of the underlying.
        lot_size: Lot size (0 to auto-lookup).

    Returns:
        FuturesQuote or None if parsing fails.
    """
    tradingsymbol = kite_key.split(":")[-1] if ":" in kite_key else kite_key
    parsed = parse_futures_symbol(tradingsymbol)
    if not parsed:
        return None

    ohlc = kite_quote.get("ohlc", {})
    prev_close = ohlc.get("close", 0)
    last_price = kite_quote.get("last_price", 0)
    change = last_price - prev_close if prev_close > 0 else 0
    change_pct = (change / prev_close * 100) if prev_close > 0 else 0

    return FuturesQuote(
        symbol=parsed["symbol"],
        expiry=expiry,
        last_price=last_price,
        spot_price=spot_price,
        lot_size=lot_size,
        open_interest=kite_quote.get("oi", 0),
        oi_change=kite_quote.get("oi_day_change", 0),
        volume=kite_quote.get("volume", 0),
        bid=kite_quote.get("depth", {}).get("buy", [{}])[0].get("price", 0)
        if kite_quote.get("depth")
        else 0,
        ask=kite_quote.get("depth", {}).get("sell", [{}])[0].get("price", 0)
        if kite_quote.get("depth")
        else 0,
        open=ohlc.get("open", 0),
        high=ohlc.get("high", 0),
        low=ohlc.get("low", 0),
        prev_close=prev_close,
        change=round(change, 2),
        change_pct=round(change_pct, 2),
    )


def build_futures_chain_from_kite(
    symbol: str,
    spot: float,
    kite_quotes: dict[str, dict],
    expiry_map: dict[str, date],
    lot_size: int = 0,
) -> FuturesChain | None:
    """Build a FuturesChain from Kite quote responses.

    Args:
        symbol: Underlying symbol (e.g., "NIFTY").
        spot: Current spot price.
        kite_quotes: Dict of {kite_key: kite_quote_dict} from get_quotes.
        expiry_map: Dict of {kite_key: expiry_date} mapping each key to its expiry.
        lot_size: Lot size for all contracts.

    Returns:
        FuturesChain with near/next/far month, or None if no valid quotes.
    """
    quotes: list[FuturesQuote] = []

    for kite_key, quote_data in kite_quotes.items():
        expiry = expiry_map.get(kite_key)
        if expiry is None:
            continue
        fq = kite_quote_to_futures_quote(kite_key, quote_data, expiry, spot, lot_size)
        if fq is not None:
            quotes.append(fq)

    if not quotes:
        return None

    # Sort by expiry
    quotes.sort(key=lambda q: q.expiry)

    near = quotes[0]
    next_m = quotes[1] if len(quotes) > 1 else None
    far = quotes[2] if len(quotes) > 2 else None

    ts = ""
    for _, qd in kite_quotes.items():
        ts = qd.get("timestamp", "")
        if ts:
            break

    return FuturesChain(
        symbol=symbol,
        spot=spot,
        near_month=near,
        next_month=next_m,
        far_month=far,
        timestamp=ts,
    )
