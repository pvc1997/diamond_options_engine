"""Futures chain data structures and analysis.

Provides unified futures data representation for Indian F&O markets:
- FuturesQuote: Single futures contract quote
- FuturesChain: Near/next/far month contracts with basis and spread analysis

Designed for dual-mode operation: live data from Kite or synthetic construction.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path

from diamond_options.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class FuturesQuote:
    """A single futures contract quote."""

    symbol: str  # Underlying (e.g., "NIFTY", "RELIANCE")
    expiry: date
    last_price: float  # LTP of futures contract
    spot_price: float  # Underlying spot price
    lot_size: int = 0
    open_interest: int = 0
    oi_change: int = 0  # OI change from previous day
    volume: int = 0
    bid: float = 0.0
    ask: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    change: float = 0.0  # Price change from prev close
    change_pct: float = 0.0

    @property
    def basis(self) -> float:
        """Futures premium/discount over spot (₹)."""
        return self.last_price - self.spot_price

    @property
    def basis_pct(self) -> float:
        """Basis as percentage of spot."""
        if self.spot_price <= 0:
            return 0.0
        return (self.basis / self.spot_price) * 100

    @property
    def contract_value(self) -> float:
        """Notional value of one lot."""
        return self.last_price * self.lot_size

    @property
    def spread(self) -> float:
        """Bid-ask spread."""
        if self.bid > 0 and self.ask > 0:
            return self.ask - self.bid
        return 0.0

    @property
    def spread_pct(self) -> float:
        """Bid-ask spread as % of mid price."""
        if self.bid > 0 and self.ask > 0:
            mid = (self.bid + self.ask) / 2
            if mid > 0:
                return (self.spread / mid) * 100
        return 0.0

    @property
    def is_contango(self) -> bool:
        """Futures trading at premium to spot."""
        return self.basis > 0

    @property
    def is_backwardation(self) -> bool:
        """Futures trading at discount to spot."""
        return self.basis < 0

    def annualized_basis(self, days_to_expiry: int) -> float:
        """Basis annualized as cost-of-carry equivalent (%).

        Args:
            days_to_expiry: Trading days remaining to expiry.

        Returns:
            Annualized basis in percentage.
        """
        if days_to_expiry <= 0 or self.spot_price <= 0:
            return 0.0
        return (self.basis_pct / days_to_expiry) * 365

    def to_dict(self) -> dict:
        d = asdict(self)
        d["expiry"] = self.expiry.isoformat()
        d["basis"] = round(self.basis, 2)
        d["basis_pct"] = round(self.basis_pct, 4)
        d["contract_value"] = round(self.contract_value, 2)
        return d


@dataclass
class FuturesChain:
    """Complete futures chain for a symbol across expiries.

    Contains near-month, next-month, and optionally far-month contracts
    with basis, spread, and rollover analysis.
    """

    symbol: str
    spot: float
    near_month: FuturesQuote  # Current month contract
    next_month: FuturesQuote | None = None  # Next month contract
    far_month: FuturesQuote | None = None  # Far month (indices only)
    timestamp: str = ""

    @property
    def calendar_spread(self) -> float | None:
        """Price difference between next and near month (₹)."""
        if self.next_month is None:
            return None
        return self.next_month.last_price - self.near_month.last_price

    @property
    def calendar_spread_pct(self) -> float | None:
        """Calendar spread as % of near month price."""
        if self.next_month is None or self.near_month.last_price <= 0:
            return None
        spread = self.calendar_spread
        if spread is None:
            return None
        return (spread / self.near_month.last_price) * 100

    @property
    def total_oi(self) -> int:
        """Total OI across all months."""
        total = self.near_month.open_interest
        if self.next_month:
            total += self.next_month.open_interest
        if self.far_month:
            total += self.far_month.open_interest
        return total

    @property
    def oi_concentration(self) -> str:
        """Which month has the most OI."""
        near_oi = self.near_month.open_interest
        next_oi = self.next_month.open_interest if self.next_month else 0
        far_oi = self.far_month.open_interest if self.far_month else 0

        if near_oi >= next_oi and near_oi >= far_oi:
            return "near"
        if next_oi >= near_oi and next_oi >= far_oi:
            return "next"
        return "far"

    @property
    def rollover_pct(self) -> float:
        """Percentage of OI in next month vs total near+next.

        High rollover (>50%) near expiry indicates continuation.
        Low rollover indicates traders closing rather than rolling.
        """
        near_oi = self.near_month.open_interest
        next_oi = self.next_month.open_interest if self.next_month else 0
        total = near_oi + next_oi
        if total == 0:
            return 0.0
        return (next_oi / total) * 100

    @property
    def term_structure(self) -> str:
        """Describe the futures term structure.

        Contango: near < next < far (normal carry)
        Backwardation: near > next > far (inverted)
        Mixed: no clear pattern
        """
        prices = [self.near_month.last_price]
        if self.next_month:
            prices.append(self.next_month.last_price)
        if self.far_month:
            prices.append(self.far_month.last_price)

        if len(prices) < 2:
            return "single_month"

        if all(prices[i] < prices[i + 1] for i in range(len(prices) - 1)):
            return "contango"
        if all(prices[i] > prices[i + 1] for i in range(len(prices) - 1)):
            return "backwardation"
        return "mixed"

    def summary(self) -> dict:
        """Quick summary for display."""
        result = {
            "symbol": self.symbol,
            "spot": self.spot,
            "near_month": {
                "expiry": self.near_month.expiry.isoformat(),
                "price": self.near_month.last_price,
                "basis": round(self.near_month.basis, 2),
                "basis_pct": round(self.near_month.basis_pct, 4),
                "oi": self.near_month.open_interest,
                "volume": self.near_month.volume,
            },
            "total_oi": self.total_oi,
            "oi_concentration": self.oi_concentration,
            "rollover_pct": round(self.rollover_pct, 1),
            "term_structure": self.term_structure,
        }

        if self.next_month:
            result["next_month"] = {
                "expiry": self.next_month.expiry.isoformat(),
                "price": self.next_month.last_price,
                "basis": round(self.next_month.basis, 2),
                "basis_pct": round(self.next_month.basis_pct, 4),
                "oi": self.next_month.open_interest,
                "volume": self.next_month.volume,
            }
            result["calendar_spread"] = round(self.calendar_spread or 0, 2)
            result["calendar_spread_pct"] = round(self.calendar_spread_pct or 0, 4)

        if self.far_month:
            result["far_month"] = {
                "expiry": self.far_month.expiry.isoformat(),
                "price": self.far_month.last_price,
                "basis": round(self.far_month.basis, 2),
                "basis_pct": round(self.far_month.basis_pct, 4),
                "oi": self.far_month.open_interest,
                "volume": self.far_month.volume,
            }

        return result

    def to_dict(self) -> dict:
        d = {
            "symbol": self.symbol,
            "spot": self.spot,
            "near_month": self.near_month.to_dict(),
            "timestamp": self.timestamp,
        }
        if self.next_month:
            d["next_month"] = self.next_month.to_dict()
        if self.far_month:
            d["far_month"] = self.far_month.to_dict()
        return d


def _futures_cache_path(symbol: str) -> Path:
    """Cache file path for a futures chain."""
    return get_config().cache_dir / "futures" / f"{symbol}_chain.json"


def save_futures_chain_to_cache(chain: FuturesChain) -> None:
    """Save futures chain to file cache."""
    path = _futures_cache_path(chain.symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chain.to_dict(), indent=2))


def load_futures_chain_from_cache(symbol: str) -> FuturesChain | None:
    """Load futures chain from cache if fresh enough."""
    path = _futures_cache_path(symbol)
    if not path.exists():
        return None

    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > get_config().cache.chain_ttl:
        return None

    try:
        data = json.loads(path.read_text())
        return _chain_from_dict(data)
    except Exception:
        logger.warning("Failed to load futures chain cache for %s", symbol)
        return None


def _quote_from_dict(d: dict) -> FuturesQuote:
    """Reconstruct FuturesQuote from serialized dict."""
    return FuturesQuote(
        symbol=d["symbol"],
        expiry=date.fromisoformat(d["expiry"]),
        last_price=d["last_price"],
        spot_price=d["spot_price"],
        lot_size=d.get("lot_size", 0),
        open_interest=d.get("open_interest", 0),
        oi_change=d.get("oi_change", 0),
        volume=d.get("volume", 0),
        bid=d.get("bid", 0),
        ask=d.get("ask", 0),
        open=d.get("open", 0),
        high=d.get("high", 0),
        low=d.get("low", 0),
        prev_close=d.get("prev_close", 0),
        change=d.get("change", 0),
        change_pct=d.get("change_pct", 0),
    )


def _chain_from_dict(data: dict) -> FuturesChain:
    """Reconstruct FuturesChain from serialized dict."""
    near = _quote_from_dict(data["near_month"])
    next_m = _quote_from_dict(data["next_month"]) if "next_month" in data else None
    far = _quote_from_dict(data["far_month"]) if "far_month" in data else None

    return FuturesChain(
        symbol=data["symbol"],
        spot=data["spot"],
        near_month=near,
        next_month=next_m,
        far_month=far,
        timestamp=data.get("timestamp", ""),
    )
