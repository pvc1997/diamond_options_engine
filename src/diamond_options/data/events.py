"""Indian market event calendar for options-aware trading.

Tracks RBI policy, earnings seasons, budget, economic data releases,
global events, and NSE holidays that affect options pricing and IV.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from diamond_options.utils.indian_markets import NSE_HOLIDAYS_2026

# Valid event types and impact levels
EVENT_TYPES = {
    "rbi_policy", "earnings", "budget", "expiry", "holiday",
    "economic_data", "global", "other",
}
IMPACT_LEVELS = {"high", "medium", "low"}


@dataclass(frozen=True)
class MarketEvent:
    """A single market event that may affect options pricing."""

    date: date
    event_type: str
    title: str
    description: str
    impact: str
    affected_symbols: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"Invalid event_type: {self.event_type}")
        if self.impact not in IMPACT_LEVELS:
            raise ValueError(f"Invalid impact: {self.impact}")


# ---------------------------------------------------------------------------
# Known events database for 2026
# ---------------------------------------------------------------------------

_ALL_INDICES = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
_ALL_SYMBOLS = ["ALL"]  # Sentinel meaning all F&O stocks

def _build_events_2026() -> list[MarketEvent]:
    """Build the comprehensive 2026 event calendar."""
    events: list[MarketEvent] = []

    # --- RBI Monetary Policy (bi-monthly, 3-day meetings) ---
    rbi_meetings = [
        (date(2026, 2, 4), date(2026, 2, 6)),
        (date(2026, 4, 6), date(2026, 4, 8)),
        (date(2026, 6, 1), date(2026, 6, 3)),
        (date(2026, 8, 3), date(2026, 8, 5)),
        (date(2026, 10, 5), date(2026, 10, 7)),
        (date(2026, 12, 7), date(2026, 12, 9)),
    ]
    for start, end in rbi_meetings:
        current = start
        while current <= end:
            label = "Day 1" if current == start else ("Day 2" if current == start + timedelta(days=1) else "Decision Day")
            events.append(MarketEvent(
                date=current,
                event_type="rbi_policy",
                title=f"RBI Policy {current.strftime('%b %Y')} — {label}",
                description=f"RBI Monetary Policy Committee meeting {label.lower()}. Rate decision on final day.",
                impact="high",
                affected_symbols=list(_ALL_INDICES),
            ))
            current += timedelta(days=1)

    # --- Union Budget ---
    events.append(MarketEvent(
        date=date(2026, 2, 1),
        event_type="budget",
        title="Union Budget 2026-27",
        description="Annual Union Budget presentation. High volatility expected across all sectors.",
        impact="high",
        affected_symbols=list(_ALL_SYMBOLS),
    ))

    # --- Earnings seasons (window start and end as individual events) ---
    earnings_windows = [
        ("Q3 FY26", date(2026, 1, 15), date(2026, 2, 15)),
        ("Q4 FY26", date(2026, 4, 15), date(2026, 5, 31)),
        ("Q1 FY27", date(2026, 7, 15), date(2026, 8, 31)),
        ("Q2 FY27", date(2026, 10, 15), date(2026, 11, 30)),
    ]
    for label, start, end in earnings_windows:
        events.append(MarketEvent(
            date=start,
            event_type="earnings",
            title=f"{label} Earnings Season Begins",
            description=f"{label} corporate results season starts. Stock-specific IV likely elevated.",
            impact="medium",
            affected_symbols=list(_ALL_SYMBOLS),
        ))
        events.append(MarketEvent(
            date=end,
            event_type="earnings",
            title=f"{label} Earnings Season Ends",
            description=f"{label} corporate results season winds down.",
            impact="low",
            affected_symbols=list(_ALL_SYMBOLS),
        ))

    # --- Key economic data releases ---
    # GDP: last week of Feb, May, Aug, Nov (use last Friday)
    gdp_dates = [date(2026, 2, 27), date(2026, 5, 29), date(2026, 8, 28), date(2026, 11, 27)]
    for d in gdp_dates:
        events.append(MarketEvent(
            date=d,
            event_type="economic_data",
            title=f"India GDP Data Release ({d.strftime('%b %Y')})",
            description="Quarterly GDP growth figures. May move index options.",
            impact="medium",
            affected_symbols=list(_ALL_INDICES),
        ))

    # CPI/Inflation: 2nd week (12th) of every month
    for month in range(1, 13):
        d = date(2026, month, 12)
        events.append(MarketEvent(
            date=d,
            event_type="economic_data",
            title=f"CPI Inflation Data ({d.strftime('%b %Y')})",
            description="Monthly CPI inflation release. Influences RBI rate expectations.",
            impact="medium",
            affected_symbols=list(_ALL_INDICES),
        ))

    # IIP: 2nd week (12th) of every month
    for month in range(1, 13):
        d = date(2026, month, 12)
        # Same date as CPI — combine description
        # Actually add as separate event to keep types clean
        events.append(MarketEvent(
            date=d,
            event_type="economic_data",
            title=f"IIP Industrial Production ({d.strftime('%b %Y')})",
            description="Monthly industrial production index release.",
            impact="low",
            affected_symbols=list(_ALL_INDICES),
        ))

    # --- Global events ---
    # US Fed FOMC meetings (2-day, decision on day 2)
    fomc_meetings = [
        (date(2026, 1, 28), date(2026, 1, 29)),
        (date(2026, 3, 18), date(2026, 3, 19)),
        (date(2026, 5, 6), date(2026, 5, 7)),
        (date(2026, 6, 17), date(2026, 6, 18)),
        (date(2026, 7, 29), date(2026, 7, 30)),
        (date(2026, 9, 16), date(2026, 9, 17)),
        (date(2026, 11, 4), date(2026, 11, 5)),
        (date(2026, 12, 16), date(2026, 12, 17)),
    ]
    for start, end in fomc_meetings:
        events.append(MarketEvent(
            date=start,
            event_type="global",
            title=f"US Fed FOMC Meeting Day 1 ({start.strftime('%b %Y')})",
            description="Federal Reserve FOMC meeting begins. Markets may be cautious.",
            impact="medium",
            affected_symbols=list(_ALL_INDICES),
        ))
        events.append(MarketEvent(
            date=end,
            event_type="global",
            title=f"US Fed FOMC Decision ({end.strftime('%b %Y')})",
            description="FOMC rate decision and statement. Can cause significant overnight gap.",
            impact="high",
            affected_symbols=list(_ALL_INDICES),
        ))

    # US Jobs data: First Friday of every month
    for month in range(1, 13):
        first_day = date(2026, month, 1)
        # Find first Friday (weekday 4)
        offset = (4 - first_day.weekday()) % 7
        first_friday = first_day + timedelta(days=offset)
        events.append(MarketEvent(
            date=first_friday,
            event_type="global",
            title=f"US Non-Farm Payrolls ({first_friday.strftime('%b %Y')})",
            description="US monthly jobs report. Can influence global risk sentiment.",
            impact="medium",
            affected_symbols=list(_ALL_INDICES),
        ))

    # --- NSE Holidays ---
    holiday_names = {
        date(2026, 1, 26): "Republic Day",
        date(2026, 2, 17): "Mahashivratri",
        date(2026, 3, 10): "Holi",
        date(2026, 3, 30): "Id-ul-Fitr",
        date(2026, 3, 31): "Id-ul-Fitr",
        date(2026, 4, 2): "Ram Navami",
        date(2026, 4, 3): "Good Friday",
        date(2026, 4, 14): "Dr. Ambedkar Jayanti",
        date(2026, 5, 1): "Maharashtra Day",
        date(2026, 5, 25): "Buddha Purnima",
        date(2026, 6, 6): "Eid-ul-Adha",
        date(2026, 7, 6): "Muharram",
        date(2026, 8, 15): "Independence Day",
        date(2026, 8, 18): "Janmashtami",
        date(2026, 9, 4): "Milad-un-Nabi",
        date(2026, 10, 2): "Mahatma Gandhi Jayanti",
        date(2026, 10, 20): "Dussehra",
        date(2026, 11, 9): "Diwali (Laxmi Puja)",
        date(2026, 11, 10): "Diwali (Balipratipada)",
        date(2026, 11, 30): "Guru Nanak Jayanti",
        date(2026, 12, 25): "Christmas",
    }
    for d in sorted(NSE_HOLIDAYS_2026):
        name = holiday_names.get(d, "NSE Holiday")
        events.append(MarketEvent(
            date=d,
            event_type="holiday",
            title=f"NSE Holiday — {name}",
            description=f"Market closed for {name}. No trading.",
            impact="low",
            affected_symbols=list(_ALL_SYMBOLS),
        ))

    return sorted(events, key=lambda e: e.date)


# Singleton — built once
_EVENTS_2026: list[MarketEvent] = _build_events_2026()

# Earnings season windows for quick lookup
_EARNINGS_WINDOWS: list[tuple[str, date, date]] = [
    ("Q3 FY26", date(2026, 1, 15), date(2026, 2, 15)),
    ("Q4 FY26", date(2026, 4, 15), date(2026, 5, 31)),
    ("Q1 FY27", date(2026, 7, 15), date(2026, 8, 31)),
    ("Q2 FY27", date(2026, 10, 15), date(2026, 11, 30)),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_upcoming_events(
    from_date: Optional[date] = None,
    days_ahead: int = 14,
    event_types: Optional[list[str]] = None,
) -> list[MarketEvent]:
    """Return events in the next N days, optionally filtered by type.

    Args:
        from_date: Starting date (default: today).
        days_ahead: Number of days to look ahead.
        event_types: Filter to specific event types (e.g., ["rbi_policy", "earnings"]).

    Returns:
        List of MarketEvent sorted by date.
    """
    if from_date is None:
        from_date = date.today()
    end_date = from_date + timedelta(days=days_ahead)

    results = [
        e for e in _EVENTS_2026
        if from_date <= e.date <= end_date
    ]
    if event_types:
        results = [e for e in results if e.event_type in event_types]

    return sorted(results, key=lambda e: e.date)


def get_events_for_date(d: date) -> list[MarketEvent]:
    """Return all events on a specific date."""
    return [e for e in _EVENTS_2026 if e.date == d]


def get_events_for_symbol(
    symbol: str,
    from_date: Optional[date] = None,
    days_ahead: int = 30,
) -> list[MarketEvent]:
    """Return events affecting a specific symbol.

    NIFTY/index events are included for all F&O stocks since index moves
    affect the entire market.

    Args:
        symbol: NSE symbol (e.g., "RELIANCE", "NIFTY").
        from_date: Starting date (default: today).
        days_ahead: Number of days to look ahead.

    Returns:
        List of MarketEvent sorted by date.
    """
    if from_date is None:
        from_date = date.today()
    end_date = from_date + timedelta(days=days_ahead)
    symbol_upper = symbol.upper()

    results = []
    for e in _EVENTS_2026:
        if not (from_date <= e.date <= end_date):
            continue
        # Match if: symbol is directly listed, or event affects ALL, or
        # NIFTY events apply to all F&O stocks
        if (
            symbol_upper in e.affected_symbols
            or "ALL" in e.affected_symbols
            or "NIFTY" in e.affected_symbols
        ):
            results.append(e)

    return sorted(results, key=lambda e: e.date)


def is_high_impact_day(d: Optional[date] = None) -> bool:
    """Check if any high-impact event falls on the given date.

    Args:
        d: Date to check (default: today).

    Returns:
        True if at least one high-impact event is on this date.
    """
    if d is None:
        d = date.today()
    return any(e.impact == "high" and e.date == d for e in _EVENTS_2026)


def _is_earnings_season(d: date) -> bool:
    """Check if a date falls within any earnings season window."""
    return any(start <= d <= end for _, start, end in _EARNINGS_WINDOWS)


def event_aware_context(
    from_date: Optional[date] = None,
    days_ahead: int = 7,
) -> dict:
    """Return a trading context dict summarising the event landscape.

    Args:
        from_date: Starting date (default: today).
        days_ahead: Number of days to look ahead.

    Returns:
        Dict with keys: upcoming_events, is_event_day, high_impact_events,
        earnings_season, pre_event_warning, iv_impact_note.
    """
    if from_date is None:
        from_date = date.today()

    upcoming = get_upcoming_events(from_date=from_date, days_ahead=days_ahead)
    today_events = get_events_for_date(from_date)
    high_today = [e for e in today_events if e.impact == "high"]
    earnings = _is_earnings_season(from_date)

    # Pre-event warning: high-impact event in next 2 days (excluding today)
    pre_warning = ""
    tomorrow = from_date + timedelta(days=1)
    day_after = from_date + timedelta(days=2)
    near_high = [
        e for e in _EVENTS_2026
        if tomorrow <= e.date <= day_after and e.impact == "high"
    ]
    if near_high:
        titles = ", ".join(e.title for e in near_high[:3])
        pre_warning = f"High-impact event approaching: {titles}"

    # IV impact note
    iv_reasons: list[str] = []
    if high_today:
        iv_reasons.append(f"high-impact event today ({high_today[0].title})")
    if near_high:
        iv_reasons.append("high-impact event in next 2 days")
    if earnings:
        iv_reasons.append("ongoing earnings season")

    if iv_reasons:
        iv_note = "IV likely elevated due to " + "; ".join(iv_reasons)
    else:
        iv_note = "Normal IV environment"

    return {
        "upcoming_events": upcoming,
        "is_event_day": len(today_events) > 0,
        "high_impact_events": high_today,
        "earnings_season": earnings,
        "pre_event_warning": pre_warning,
        "iv_impact_note": iv_note,
    }


def get_earnings_calendar(symbol: str = "") -> list[MarketEvent]:
    """Return earnings season events.

    Args:
        symbol: If given, return only events for that symbol's earnings.
            If empty, return all earnings season window events.

    Returns:
        List of MarketEvent for earnings seasons.
    """
    earnings_events = [e for e in _EVENTS_2026 if e.event_type == "earnings"]

    if symbol:
        symbol_upper = symbol.upper()
        # Return earnings events that affect this symbol (ALL matches everything)
        return [
            e for e in earnings_events
            if symbol_upper in e.affected_symbols or "ALL" in e.affected_symbols
        ]

    return earnings_events
