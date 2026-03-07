"""NSE F&O expiry calendar.

Weekly expiry moved from Thursday to Tuesday for all indices effective 2024.
Handles weekly (Tuesday) and monthly expiry logic for indices and stocks.
Accounts for holidays — if Tuesday is a holiday, expiry moves to previous trading day.
"""

from __future__ import annotations

from datetime import date, timedelta

from diamond_options.utils.indian_markets import is_trading_day, NSE_HOLIDAYS_2026


def _last_tuesday(year: int, month: int) -> date:
    """Find the last Tuesday of a given month."""
    # Start from the last day of the month
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    # Walk backward to find Tuesday (weekday 1)
    offset = (last_day.weekday() - 1) % 7
    return last_day - timedelta(days=offset)


def _adjust_for_holiday(d: date) -> date:
    """If expiry day is a holiday, move to previous trading day."""
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def monthly_expiry(year: int, month: int) -> date:
    """Return the monthly F&O expiry date (last Tuesday, adjusted for holidays).

    Stock options and futures always expire on monthly expiry.
    """
    tuesday = _last_tuesday(year, month)
    return _adjust_for_holiday(tuesday)


def weekly_expiries(year: int, month: int) -> list[date]:
    """Return all weekly expiry dates (Tuesdays) in a month.

    Weekly expiries are available for NIFTY, BANKNIFTY, FINNIFTY.
    Each Tuesday is an expiry; if it's a holiday, previous trading day.
    """
    # Find the first Tuesday of the month
    first_day = date(year, month, 1)
    offset = (1 - first_day.weekday()) % 7  # Days until Tuesday
    first_tuesday = first_day + timedelta(days=offset)

    tuesdays = []
    current = first_tuesday
    while current.month == month:
        tuesdays.append(_adjust_for_holiday(current))
        current += timedelta(days=7)

    return tuesdays


def next_weekly_expiry(from_date: date | None = None) -> date:
    """Return the next weekly expiry date on or after from_date."""
    if from_date is None:
        from_date = date.today()

    # Find the next Tuesday
    days_until_tuesday = (1 - from_date.weekday()) % 7
    if days_until_tuesday == 0 and is_trading_day(from_date):
        # Today is Tuesday and a trading day — this is expiry day
        return from_date

    next_tuesday = from_date + timedelta(days=days_until_tuesday or 7)
    return _adjust_for_holiday(next_tuesday)


def next_monthly_expiry(from_date: date | None = None) -> date:
    """Return the next monthly expiry date on or after from_date."""
    if from_date is None:
        from_date = date.today()

    year, month = from_date.year, from_date.month
    expiry = monthly_expiry(year, month)

    if from_date > expiry:
        # This month's expiry has passed, go to next month
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        expiry = monthly_expiry(year, month)

    return expiry


def upcoming_expiries(
    from_date: date | None = None,
    count: int = 8,
    weekly: bool = True,
) -> list[date]:
    """Return next `count` expiry dates.

    Args:
        from_date: Starting date (default: today).
        count: Number of expiries to return.
        weekly: If True, include weekly expiries. If False, monthly only.

    Returns:
        Sorted list of upcoming expiry dates.
    """
    if from_date is None:
        from_date = date.today()

    expiries: list[date] = []
    current = from_date

    if weekly:
        while len(expiries) < count:
            exp = next_weekly_expiry(current)
            if exp not in expiries:
                expiries.append(exp)
            # Always advance past the raw next Tuesday to avoid loops
            # when holiday adjustment pulls expiry before current
            days_to_tue = (1 - current.weekday()) % 7
            raw_tuesday = current + timedelta(days=days_to_tue or 7)
            current = max(exp, raw_tuesday) + timedelta(days=1)
    else:
        year, month = current.year, current.month
        while len(expiries) < count:
            exp = monthly_expiry(year, month)
            if exp >= from_date:
                expiries.append(exp)
            month += 1
            if month > 12:
                month = 1
                year += 1

    return sorted(expiries)[:count]


def expiry_label(expiry: date) -> str:
    """Format expiry as human-readable label: '27MAR', '03APR', etc."""
    return expiry.strftime("%d%b").upper()


def is_expiry_day(d: date | None = None) -> bool:
    """Check if a date is an expiry day (weekly Tuesday or adjusted)."""
    if d is None:
        d = date.today()
    # Check if this date appears in weekly expiries for its month
    return d in weekly_expiries(d.year, d.month)


def days_to_expiry(expiry: date, from_date: date | None = None) -> int:
    """Calendar days to expiry."""
    if from_date is None:
        from_date = date.today()
    return max(0, (expiry - from_date).days)


def classify_expiry(expiry: date, from_date: date | None = None) -> str:
    """Classify expiry distance: 'current_week', 'next_week', 'current_month', 'far_month'."""
    dte = days_to_expiry(expiry, from_date)
    if dte <= 7:
        return "current_week"
    elif dte <= 14:
        return "next_week"
    elif dte <= 35:
        return "current_month"
    else:
        return "far_month"
