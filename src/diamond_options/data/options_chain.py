"""Options chain data fetching and representation.

Provides a unified interface for options chain data from multiple sources:
1. Kite MCP (live data during market hours)
2. Synthetic chain construction from spot + IV (for analysis/backtesting)

Each chain entry contains: strike, type (CE/PE), LTP, bid, ask, OI, volume, IV, Greeks.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

from diamond_options.config import get_config
from diamond_options.data.expiry import expiry_label

logger = logging.getLogger(__name__)


@dataclass
class OptionQuote:
    """A single option contract quote."""
    strike: float
    option_type: str         # "CE" or "PE"
    expiry: date
    ltp: float               # Last traded price
    bid: float = 0.0
    ask: float = 0.0
    open_interest: int = 0
    volume: int = 0
    iv: float = 0.0          # Implied volatility (decimal, e.g., 0.25 = 25%)
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    change: float = 0.0      # Price change from previous close
    change_pct: float = 0.0  # % change

    @property
    def bid_ask_spread(self) -> float:
        """Bid-ask spread in absolute terms."""
        if self.bid > 0 and self.ask > 0:
            return self.ask - self.bid
        return 0.0

    @property
    def bid_ask_spread_pct(self) -> float:
        """Bid-ask spread as % of mid price."""
        mid = (self.bid + self.ask) / 2
        if mid > 0:
            return self.bid_ask_spread / mid
        return 0.0

    @property
    def is_liquid(self) -> bool:
        """Check if the contract has reasonable liquidity."""
        return self.open_interest >= 100 and self.volume >= 10

    @property
    def mid_price(self) -> float:
        """Mid price between bid and ask. Falls back to LTP."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.ltp

    def to_dict(self) -> dict:
        d = asdict(self)
        d["expiry"] = self.expiry.isoformat()
        return d


@dataclass
class OptionsChain:
    """Complete options chain for a symbol and expiry.

    Contains all available strikes for both calls and puts,
    along with spot price and underlying info.
    """
    symbol: str
    expiry: date
    spot_price: float
    timestamp: str = ""       # When the chain was fetched
    calls: list[OptionQuote] = field(default_factory=list)
    puts: list[OptionQuote] = field(default_factory=list)

    @property
    def strikes(self) -> list[float]:
        """All available strikes, sorted."""
        all_strikes = set()
        for q in self.calls:
            all_strikes.add(q.strike)
        for q in self.puts:
            all_strikes.add(q.strike)
        return sorted(all_strikes)

    @property
    def atm_strike(self) -> float:
        """Find the at-the-money strike closest to spot."""
        if not self.strikes:
            return self.spot_price
        return min(self.strikes, key=lambda s: abs(s - self.spot_price))

    def get_call(self, strike: float) -> OptionQuote | None:
        """Get call option at a specific strike."""
        for q in self.calls:
            if q.strike == strike:
                return q
        return None

    def get_put(self, strike: float) -> OptionQuote | None:
        """Get put option at a specific strike."""
        for q in self.puts:
            if q.strike == strike:
                return q
        return None

    def get_quote(self, strike: float, option_type: str) -> OptionQuote | None:
        """Get option quote by strike and type (CE/PE)."""
        if option_type.upper() == "CE":
            return self.get_call(strike)
        return self.get_put(strike)

    def itm_calls(self) -> list[OptionQuote]:
        """In-the-money calls (strike < spot)."""
        return sorted(
            [q for q in self.calls if q.strike < self.spot_price],
            key=lambda q: q.strike, reverse=True,
        )

    def otm_calls(self) -> list[OptionQuote]:
        """Out-of-the-money calls (strike > spot)."""
        return sorted(
            [q for q in self.calls if q.strike > self.spot_price],
            key=lambda q: q.strike,
        )

    def itm_puts(self) -> list[OptionQuote]:
        """In-the-money puts (strike > spot)."""
        return sorted(
            [q for q in self.puts if q.strike > self.spot_price],
            key=lambda q: q.strike,
        )

    def otm_puts(self) -> list[OptionQuote]:
        """Out-of-the-money puts (strike < spot)."""
        return sorted(
            [q for q in self.puts if q.strike < self.spot_price],
            key=lambda q: q.strike, reverse=True,
        )

    def straddle(self, strike: float | None = None) -> tuple[OptionQuote | None, OptionQuote | None]:
        """Get call + put at a strike (default ATM) for straddle analysis."""
        s = strike or self.atm_strike
        return self.get_call(s), self.get_put(s)

    def pcr_oi(self) -> float | None:
        """Put-Call Ratio by Open Interest."""
        total_call_oi = sum(q.open_interest for q in self.calls)
        total_put_oi = sum(q.open_interest for q in self.puts)
        if total_call_oi == 0:
            return None
        return total_put_oi / total_call_oi

    def pcr_volume(self) -> float | None:
        """Put-Call Ratio by Volume."""
        total_call_vol = sum(q.volume for q in self.calls)
        total_put_vol = sum(q.volume for q in self.puts)
        if total_call_vol == 0:
            return None
        return total_put_vol / total_call_vol

    def max_pain(self) -> float | None:
        """Calculate max pain strike — the strike where option writers lose the least.

        Max pain = strike that minimizes total intrinsic value payout
        weighted by open interest.
        """
        if not self.strikes:
            return None

        min_pain = float("inf")
        pain_strike = self.strikes[0]

        for test_strike in self.strikes:
            total_pain = 0.0
            # Pain from calls: if test_strike > call_strike, call is ITM
            for call in self.calls:
                if test_strike > call.strike:
                    total_pain += (test_strike - call.strike) * call.open_interest
            # Pain from puts: if test_strike < put_strike, put is ITM
            for put in self.puts:
                if test_strike < put.strike:
                    total_pain += (put.strike - test_strike) * put.open_interest

            if total_pain < min_pain:
                min_pain = total_pain
                pain_strike = test_strike

        return pain_strike

    def total_oi(self) -> dict[str, int]:
        """Total open interest summary."""
        return {
            "call_oi": sum(q.open_interest for q in self.calls),
            "put_oi": sum(q.open_interest for q in self.puts),
            "total_oi": sum(q.open_interest for q in self.calls)
                        + sum(q.open_interest for q in self.puts),
        }

    def liquid_strikes(self, min_oi: int = 100) -> list[float]:
        """Strikes with OI above threshold on both call and put side."""
        call_strikes = {q.strike for q in self.calls if q.open_interest >= min_oi}
        put_strikes = {q.strike for q in self.puts if q.open_interest >= min_oi}
        return sorted(call_strikes & put_strikes)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "expiry": self.expiry.isoformat(),
            "spot_price": self.spot_price,
            "timestamp": self.timestamp,
            "calls": [q.to_dict() for q in self.calls],
            "puts": [q.to_dict() for q in self.puts],
        }

    def summary(self) -> dict:
        """Quick summary for display."""
        oi = self.total_oi()
        return {
            "symbol": self.symbol,
            "expiry": expiry_label(self.expiry),
            "spot": self.spot_price,
            "atm_strike": self.atm_strike,
            "num_strikes": len(self.strikes),
            "pcr_oi": self.pcr_oi(),
            "max_pain": self.max_pain(),
            "total_call_oi": oi["call_oi"],
            "total_put_oi": oi["put_oi"],
        }


def _chain_cache_path(symbol: str, expiry: date) -> Path:
    """Cache file path for an options chain."""
    return get_config().cache_dir / "chains" / f"{symbol}_{expiry.isoformat()}.json"


def save_chain_to_cache(chain: OptionsChain) -> None:
    """Save options chain to file cache."""
    path = _chain_cache_path(chain.symbol, chain.expiry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chain.to_dict(), indent=2))


def load_chain_from_cache(symbol: str, expiry: date) -> OptionsChain | None:
    """Load options chain from cache if fresh enough."""
    path = _chain_cache_path(symbol, expiry)
    if not path.exists():
        return None

    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > get_config().cache.chain_ttl:
        return None

    try:
        data = json.loads(path.read_text())
        return _chain_from_dict(data)
    except Exception:
        logger.warning("Failed to load chain cache for %s %s", symbol, expiry)
        return None


def _chain_from_dict(data: dict) -> OptionsChain:
    """Reconstruct OptionsChain from serialized dict."""
    calls = [
        OptionQuote(
            strike=q["strike"],
            option_type=q["option_type"],
            expiry=date.fromisoformat(q["expiry"]),
            ltp=q["ltp"],
            bid=q.get("bid", 0),
            ask=q.get("ask", 0),
            open_interest=q.get("open_interest", 0),
            volume=q.get("volume", 0),
            iv=q.get("iv", 0),
            delta=q.get("delta", 0),
            gamma=q.get("gamma", 0),
            theta=q.get("theta", 0),
            vega=q.get("vega", 0),
            change=q.get("change", 0),
            change_pct=q.get("change_pct", 0),
        )
        for q in data.get("calls", [])
    ]
    puts = [
        OptionQuote(
            strike=q["strike"],
            option_type=q["option_type"],
            expiry=date.fromisoformat(q["expiry"]),
            ltp=q["ltp"],
            bid=q.get("bid", 0),
            ask=q.get("ask", 0),
            open_interest=q.get("open_interest", 0),
            volume=q.get("volume", 0),
            iv=q.get("iv", 0),
            delta=q.get("delta", 0),
            gamma=q.get("gamma", 0),
            theta=q.get("theta", 0),
            vega=q.get("vega", 0),
            change=q.get("change", 0),
            change_pct=q.get("change_pct", 0),
        )
        for q in data.get("puts", [])
    ]

    return OptionsChain(
        symbol=data["symbol"],
        expiry=date.fromisoformat(data["expiry"]),
        spot_price=data["spot_price"],
        timestamp=data.get("timestamp", ""),
        calls=calls,
        puts=puts,
    )


def build_synthetic_chain(
    symbol: str,
    spot: float,
    expiry: date,
    strikes: list[float],
    iv: float = 0.20,
) -> OptionsChain:
    """Build a synthetic options chain for analysis/backtesting.

    Uses uniform IV across strikes. In production, use live chain data.
    Greeks should be computed by the pricing engine after chain creation.

    Args:
        symbol: Underlying symbol.
        spot: Current spot price.
        expiry: Expiry date.
        strikes: List of strike prices to include.
        iv: Implied volatility to assign (uniform).

    Returns:
        OptionsChain with synthetic quotes (LTP = 0, to be priced).
    """
    calls = []
    puts = []

    for strike in sorted(strikes):
        calls.append(OptionQuote(
            strike=strike,
            option_type="CE",
            expiry=expiry,
            ltp=0.0,
            iv=iv,
        ))
        puts.append(OptionQuote(
            strike=strike,
            option_type="PE",
            expiry=expiry,
            ltp=0.0,
            iv=iv,
        ))

    return OptionsChain(
        symbol=symbol,
        expiry=expiry,
        spot_price=spot,
        calls=calls,
        puts=puts,
    )


def generate_strikes(
    spot: float,
    step: float,
    num_otm: int = 10,
) -> list[float]:
    """Generate strike prices around the spot price.

    Args:
        spot: Current spot price.
        step: Strike interval (e.g., 50 for Nifty, 100 for BankNifty).
        num_otm: Number of OTM strikes on each side.

    Returns:
        Sorted list of strike prices centered around ATM.
    """
    atm = round(spot / step) * step
    strikes = []
    for i in range(-num_otm, num_otm + 1):
        strikes.append(atm + i * step)
    return strikes
