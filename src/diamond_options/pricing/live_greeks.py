"""Live Greeks computation from market prices.

Computes implied volatility and Greeks from live option prices (e.g., Kite quotes).
Kite quotes provide last_price, oi, volume but NOT IV or Greeks — this module
bridges that gap using our existing BS/IV solvers.

Usage:
    1. Get live quotes from Kite (last_price, oi, volume per strike)
    2. Call compute_chain_greeks() to solve IV and compute all Greeks
    3. Use chain_greeks_summary() for ATM IV, skew, aggregate Greeks
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from diamond_options.data.kite_bridge import parse_kite_symbol
from diamond_options.pricing.black_scholes import call_price, put_price
from diamond_options.pricing.greeks import calculate_greeks
from diamond_options.pricing.implied_volatility import implied_volatility

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptionWithGreeks:
    """An option quote enriched with computed IV and Greeks."""

    strike: float
    option_type: str        # "CE" or "PE"
    expiry: date
    ltp: float              # Last traded price
    oi: int                 # Open interest
    volume: int             # Traded volume

    # Computed fields
    iv: float               # Implied volatility (annualized decimal, e.g. 0.20)
    delta: float
    gamma: float
    theta: float            # Per calendar day
    vega: float             # Per 1% vol move
    rho: float              # Per 1% rate move

    intrinsic_value: float
    time_value: float
    moneyness: str          # "ITM", "ATM", or "OTM"


def compute_iv_from_market(
    ltp: float,
    spot: float,
    strike: float,
    expiry: date,
    option_type: str,
    r: float = 0.065,
) -> float | None:
    """Compute implied volatility from a market price.

    Args:
        ltp: Last traded price (market premium).
        spot: Underlying spot price.
        strike: Option strike price.
        expiry: Expiry date.
        option_type: "CE" or "PE".
        r: Risk-free rate (default 6.5% for India).

    Returns:
        Implied volatility as a decimal (e.g. 0.20 for 20%), or None if
        the IV solver fails (deep OTM with near-zero premium, bad data, etc.).
    """
    if ltp <= 0 or spot <= 0 or strike <= 0:
        return None

    today = date.today()
    days_to_expiry = (expiry - today).days

    if days_to_expiry < 0:
        return None

    # Expiry day: use a small fraction to avoid T=0 issues
    if days_to_expiry == 0:
        T = 0.5 / 365.0  # Half a day
    else:
        T = days_to_expiry / 365.0

    # Check if ltp is below intrinsic (likely bad data)
    is_call = option_type.upper() in ("CE", "CALL", "C")
    if is_call:
        intrinsic = max(spot - strike, 0.0)
    else:
        intrinsic = max(strike - spot, 0.0)

    if ltp < intrinsic * 0.95 and intrinsic > 0:
        # Price significantly below intrinsic — bad data
        return None

    return implied_volatility(ltp, spot, strike, T, r, option_type)


def _classify_moneyness(spot: float, strike: float, option_type: str) -> str:
    """Classify an option as ITM, ATM, or OTM.

    ATM if |spot - strike| / spot < 0.5%.
    """
    if spot <= 0:
        return "OTM"

    pct_diff = abs(spot - strike) / spot

    if pct_diff < 0.005:
        return "ATM"

    is_call = option_type.upper() in ("CE", "CALL", "C")
    if is_call:
        return "ITM" if spot > strike else "OTM"
    else:
        return "ITM" if spot < strike else "OTM"


def compute_greeks_for_quote(
    spot: float,
    strike: float,
    expiry: date,
    option_type: str,
    ltp: float,
    oi: int = 0,
    volume: int = 0,
    r: float = 0.065,
) -> OptionWithGreeks | None:
    """Compute IV and all Greeks for a single option quote.

    Args:
        spot: Underlying spot price.
        strike: Option strike price.
        expiry: Expiry date.
        option_type: "CE" or "PE".
        ltp: Last traded price (market premium).
        oi: Open interest.
        volume: Traded volume.
        r: Risk-free rate.

    Returns:
        OptionWithGreeks with all computed fields, or None if IV solve fails.
    """
    iv = compute_iv_from_market(ltp, spot, strike, expiry, option_type, r)
    if iv is None:
        return None

    today = date.today()
    days_to_expiry = (expiry - today).days
    if days_to_expiry <= 0:
        T = 0.5 / 365.0
    else:
        T = days_to_expiry / 365.0

    # Compute Greeks using solved IV
    greeks = calculate_greeks(spot, strike, T, r, iv, option_type)

    # Intrinsic and time value
    is_call = option_type.upper() in ("CE", "CALL", "C")
    if is_call:
        intrinsic = max(spot - strike, 0.0)
    else:
        intrinsic = max(strike - spot, 0.0)

    time_value = max(ltp - intrinsic, 0.0)
    moneyness = _classify_moneyness(spot, strike, option_type)

    return OptionWithGreeks(
        strike=strike,
        option_type=option_type,
        expiry=expiry,
        ltp=ltp,
        oi=oi,
        volume=volume,
        iv=round(iv, 6),
        delta=greeks.delta,
        gamma=greeks.gamma,
        theta=greeks.theta,
        vega=greeks.vega,
        rho=greeks.rho,
        intrinsic_value=round(intrinsic, 2),
        time_value=round(time_value, 2),
        moneyness=moneyness,
    )


def compute_chain_greeks(
    spot: float,
    expiry: date,
    kite_quotes: dict[str, dict],
    r: float = 0.065,
) -> list[OptionWithGreeks]:
    """Compute IV and Greeks for an entire chain from Kite quotes.

    Args:
        spot: Underlying spot price.
        expiry: Expiry date.
        kite_quotes: Dict of {kite_key: quote_dict} as from Kite get_quotes.
            Each quote_dict should have at least: last_price, oi, volume.
            Keys are like "NFO:NIFTY2631024450CE".
        r: Risk-free rate.

    Returns:
        Sorted list of OptionWithGreeks (calls first, then puts, by strike).
        Quotes where IV solve fails are skipped.
    """
    results: list[OptionWithGreeks] = []

    for kite_key, quote_data in kite_quotes.items():
        tradingsymbol = kite_key.split(":")[-1] if ":" in kite_key else kite_key
        parsed = parse_kite_symbol(tradingsymbol)
        if parsed is None:
            logger.debug("Could not parse symbol: %s", kite_key)
            continue

        # Use the parsed expiry if available, otherwise use the provided expiry
        quote_expiry = parsed.get("expiry", expiry)
        if not isinstance(quote_expiry, date):
            quote_expiry = expiry

        ltp = quote_data.get("last_price", 0)
        oi_val = quote_data.get("oi", 0)
        vol = quote_data.get("volume", 0)

        owg = compute_greeks_for_quote(
            spot=spot,
            strike=parsed["strike"],
            expiry=quote_expiry,
            option_type=parsed["option_type"],
            ltp=ltp,
            oi=oi_val,
            volume=vol,
            r=r,
        )
        if owg is not None:
            results.append(owg)
        else:
            logger.debug(
                "IV solve failed for %s (strike=%.0f, ltp=%.2f)",
                kite_key, parsed["strike"], ltp,
            )

    # Sort: calls first by strike, then puts by strike
    calls = sorted([r for r in results if r.option_type == "CE"], key=lambda x: x.strike)
    puts = sorted([r for r in results if r.option_type == "PE"], key=lambda x: x.strike)

    return calls + puts


def chain_greeks_summary(
    greeks_list: list[OptionWithGreeks],
    spot: float,
) -> dict:
    """Summarize IV and Greeks across a chain.

    Args:
        greeks_list: List of OptionWithGreeks from compute_chain_greeks().
        spot: Current spot price.

    Returns:
        Dict with ATM IV, average IVs, IV skew, aggregate Greeks, etc.
    """
    if not greeks_list:
        return {
            "atm_call_iv": None,
            "atm_put_iv": None,
            "avg_call_iv": None,
            "avg_put_iv": None,
            "iv_skew": None,
            "put_call_iv_ratio": None,
            "total_delta": 0.0,
            "total_gamma": 0.0,
            "total_theta": 0.0,
            "total_vega": 0.0,
            "num_calls": 0,
            "num_puts": 0,
        }

    calls = [g for g in greeks_list if g.option_type == "CE"]
    puts = [g for g in greeks_list if g.option_type == "PE"]

    # ATM: nearest strike to spot
    def nearest_to_spot(options: list[OptionWithGreeks]) -> OptionWithGreeks | None:
        if not options:
            return None
        return min(options, key=lambda o: abs(o.strike - spot))

    atm_call = nearest_to_spot(calls)
    atm_put = nearest_to_spot(puts)

    atm_call_iv = atm_call.iv if atm_call else None
    atm_put_iv = atm_put.iv if atm_put else None

    # Average IVs
    call_ivs = [c.iv for c in calls if c.iv > 0]
    put_ivs = [p.iv for p in puts if p.iv > 0]

    avg_call_iv = sum(call_ivs) / len(call_ivs) if call_ivs else None
    avg_put_iv = sum(put_ivs) / len(put_ivs) if put_ivs else None

    # IV skew: OTM put IV - OTM call IV
    otm_calls = [c for c in calls if c.moneyness == "OTM" and c.iv > 0]
    otm_puts = [p for p in puts if p.moneyness == "OTM" and p.iv > 0]

    if otm_puts and otm_calls:
        avg_otm_put_iv = sum(p.iv for p in otm_puts) / len(otm_puts)
        avg_otm_call_iv = sum(c.iv for c in otm_calls) / len(otm_calls)
        iv_skew = round(avg_otm_put_iv - avg_otm_call_iv, 6)
    else:
        iv_skew = None

    # Put-call IV ratio
    if avg_call_iv and avg_call_iv > 0 and avg_put_iv:
        put_call_iv_ratio = round(avg_put_iv / avg_call_iv, 4)
    else:
        put_call_iv_ratio = None

    # Aggregate Greeks (as if 1 lot of each)
    total_delta = sum(g.delta for g in greeks_list)
    total_gamma = sum(g.gamma for g in greeks_list)
    total_theta = sum(g.theta for g in greeks_list)
    total_vega = sum(g.vega for g in greeks_list)

    return {
        "atm_call_iv": round(atm_call_iv, 6) if atm_call_iv else None,
        "atm_put_iv": round(atm_put_iv, 6) if atm_put_iv else None,
        "avg_call_iv": round(avg_call_iv, 6) if avg_call_iv else None,
        "avg_put_iv": round(avg_put_iv, 6) if avg_put_iv else None,
        "iv_skew": iv_skew,
        "put_call_iv_ratio": put_call_iv_ratio,
        "total_delta": round(total_delta, 4),
        "total_gamma": round(total_gamma, 6),
        "total_theta": round(total_theta, 4),
        "total_vega": round(total_vega, 4),
        "num_calls": len(calls),
        "num_puts": len(puts),
    }
