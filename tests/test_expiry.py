"""Tests for F&O expiry calendar."""

from datetime import date

from diamond_options.data.expiry import (
    monthly_expiry,
    weekly_expiries,
    next_weekly_expiry,
    next_monthly_expiry,
    upcoming_expiries,
    expiry_label,
    is_expiry_day,
    days_to_expiry,
    classify_expiry,
)


def test_monthly_expiry_basic():
    """Last Tuesday of March 2026 is March 31, adjusted for holiday to March 27."""
    exp = monthly_expiry(2026, 3)
    assert exp.weekday() < 5  # Must be a trading day
    assert exp.month == 3
    assert exp.year == 2026


def test_monthly_expiry_is_trading_day():
    """Monthly expiry should always be a trading day."""
    for month in range(1, 13):
        exp = monthly_expiry(2026, month)
        assert exp.weekday() < 5, f"Expiry {exp} is a weekend"


def test_weekly_expiries_all_trading_days():
    """All weekly expiries should be trading days."""
    for month in range(1, 13):
        for exp in weekly_expiries(2026, month):
            assert exp.weekday() < 5, f"Weekly expiry {exp} is a weekend"
            assert exp.month == month or exp.month == month - 1  # Holiday shift possible


def test_weekly_expiries_count():
    """Each month should have 4-5 weekly expiries."""
    for month in range(1, 13):
        expiries = weekly_expiries(2026, month)
        assert 4 <= len(expiries) <= 5, f"Month {month} has {len(expiries)} expiries"


def test_next_weekly_expiry():
    """Next weekly expiry should be on or after the given date."""
    from_date = date(2026, 3, 2)  # Monday
    exp = next_weekly_expiry(from_date)
    assert exp >= from_date
    assert (exp - from_date).days <= 7


def test_next_weekly_expiry_on_tuesday():
    """If today is Tuesday and a trading day, it's an expiry."""
    tuesday = date(2026, 3, 3)  # A Tuesday
    exp = next_weekly_expiry(tuesday)
    assert exp == tuesday


def test_next_monthly_expiry():
    """Next monthly expiry should be in current or next month."""
    from_date = date(2026, 3, 1)
    exp = next_monthly_expiry(from_date)
    assert exp >= from_date
    assert exp.month in (3, 4)


def test_next_monthly_expiry_after_current():
    """If this month's expiry passed, get next month."""
    from_date = date(2026, 3, 28)
    exp = next_monthly_expiry(from_date)
    assert exp >= from_date


def test_upcoming_expiries_count():
    """Should return requested number of expiries."""
    expiries = upcoming_expiries(date(2026, 3, 1), count=8)
    assert len(expiries) == 8


def test_upcoming_expiries_sorted():
    """Expiries should be in chronological order."""
    expiries = upcoming_expiries(date(2026, 3, 1), count=8)
    for i in range(len(expiries) - 1):
        assert expiries[i] <= expiries[i + 1]


def test_upcoming_monthly_only():
    """Monthly-only should return fewer, more spaced out dates."""
    weekly = upcoming_expiries(date(2026, 3, 1), count=4, weekly=True)
    monthly = upcoming_expiries(date(2026, 3, 1), count=4, weekly=False)
    # Monthly expiries should be more spread out
    if len(monthly) >= 2:
        monthly_gap = (monthly[1] - monthly[0]).days
        assert monthly_gap >= 20  # At least 3 weeks apart


def test_expiry_label():
    """Label format should be like '12MAR'."""
    label = expiry_label(date(2026, 3, 12))
    assert label == "12MAR"


def test_days_to_expiry():
    assert days_to_expiry(date(2026, 3, 12), date(2026, 3, 7)) == 5
    assert days_to_expiry(date(2026, 3, 7), date(2026, 3, 7)) == 0
    assert days_to_expiry(date(2026, 3, 5), date(2026, 3, 7)) == 0  # Past


def test_classify_expiry():
    base = date(2026, 3, 7)
    assert classify_expiry(date(2026, 3, 12), base) == "current_week"
    assert classify_expiry(date(2026, 3, 19), base) == "next_week"
    assert classify_expiry(date(2026, 3, 26), base) == "current_month"
    assert classify_expiry(date(2026, 5, 1), base) == "far_month"
