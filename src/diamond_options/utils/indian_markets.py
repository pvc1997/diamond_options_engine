"""NSE market hours, holidays, and F&O-specific utilities.

Provides lot sizes, margin rules, and trading calendar.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# NSE trading hours
NSE_OPEN_HOUR, NSE_OPEN_MINUTE = 9, 15
NSE_CLOSE_HOUR, NSE_CLOSE_MINUTE = 15, 30

# NSE holidays for 2026
NSE_HOLIDAYS_2026: set[date] = {
    date(2026, 1, 26),   # Republic Day
    date(2026, 2, 17),   # Mahashivratri
    date(2026, 3, 10),   # Holi
    date(2026, 3, 30),   # Id-ul-Fitr
    date(2026, 3, 31),   # Id-ul-Fitr
    date(2026, 4, 2),    # Ram Navami
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr. Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 5, 25),   # Buddha Purnima
    date(2026, 6, 6),    # Eid-ul-Adha
    date(2026, 7, 6),    # Muharram
    date(2026, 8, 15),   # Independence Day
    date(2026, 8, 18),   # Janmashtami
    date(2026, 9, 4),    # Milad-un-Nabi
    date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    date(2026, 10, 20),  # Dussehra
    date(2026, 11, 9),   # Diwali (Laxmi Puja)
    date(2026, 11, 10),  # Diwali (Balipratipada)
    date(2026, 11, 30),  # Guru Nanak Jayanti
    date(2026, 12, 25),  # Christmas
}


def is_trading_day(d: date) -> bool:
    """Check if a date is an NSE trading day (weekday + not a holiday)."""
    return d.weekday() < 5 and d not in NSE_HOLIDAYS_2026


def is_market_open(now: datetime | None = None) -> bool:
    """Check if NSE is currently open for trading."""
    if now is None:
        now = datetime.now(IST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)

    if not is_trading_day(now.date()):
        return False

    market_open = now.replace(
        hour=NSE_OPEN_HOUR, minute=NSE_OPEN_MINUTE, second=0, microsecond=0
    )
    market_close = now.replace(
        hour=NSE_CLOSE_HOUR, minute=NSE_CLOSE_MINUTE, second=0, microsecond=0
    )
    return market_open <= now <= market_close


def next_trading_day(from_date: date | None = None) -> date:
    """Return the next trading day on or after from_date."""
    if from_date is None:
        from_date = date.today()
    candidate = from_date
    for _ in range(30):
        if is_trading_day(candidate):
            return candidate
        candidate += timedelta(days=1)
    return candidate


def trading_days_between(start: date, end: date) -> int:
    """Count trading days between two dates (exclusive of end)."""
    count = 0
    current = start
    while current < end:
        if is_trading_day(current):
            count += 1
        current += timedelta(days=1)
    return count


def trading_days_to_expiry(expiry: date, from_date: date | None = None) -> int:
    """Count trading days remaining until expiry (inclusive of expiry day)."""
    if from_date is None:
        from_date = date.today()
    if from_date >= expiry:
        return 0
    return trading_days_between(from_date, expiry) + (1 if is_trading_day(expiry) else 0)


def calendar_days_to_expiry(expiry: date, from_date: date | None = None) -> int:
    """Calendar days remaining until expiry."""
    if from_date is None:
        from_date = date.today()
    return max(0, (expiry - from_date).days)


def years_to_expiry(expiry: date, from_date: date | None = None) -> float:
    """Time to expiry in years (calendar days / 365).

    Used for Black-Scholes calculations.
    Returns a small positive number (1/365) if expiry is today to avoid division by zero.
    """
    days = calendar_days_to_expiry(expiry, from_date)
    if days == 0:
        return 1.0 / 365.0  # Avoid zero
    return days / 365.0
