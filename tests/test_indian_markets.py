"""Tests for Indian market utilities."""

from datetime import date, datetime

from diamond_options.utils.indian_markets import (
    IST,
    is_trading_day,
    is_market_open,
    next_trading_day,
    trading_days_between,
    trading_days_to_expiry,
    calendar_days_to_expiry,
    years_to_expiry,
)


def test_weekend_not_trading_day():
    # March 7, 2026 is a Saturday
    assert is_trading_day(date(2026, 3, 7)) is False   # Saturday
    assert is_trading_day(date(2026, 3, 8)) is False   # Sunday
    assert is_trading_day(date(2026, 3, 9)) is True    # Monday


def test_holiday_not_trading_day():
    assert is_trading_day(date(2026, 1, 26)) is False  # Republic Day
    assert is_trading_day(date(2026, 3, 10)) is False  # Holi
    assert is_trading_day(date(2026, 12, 25)) is False # Christmas


def test_normal_day_is_trading():
    assert is_trading_day(date(2026, 3, 9)) is True    # Monday, not holiday


def test_market_open_during_hours():
    # 10:00 AM on a Monday
    t = datetime(2026, 3, 9, 10, 0, 0, tzinfo=IST)
    assert is_market_open(t) is True


def test_market_closed_before_open():
    t = datetime(2026, 3, 9, 9, 0, 0, tzinfo=IST)
    assert is_market_open(t) is False


def test_market_closed_after_close():
    t = datetime(2026, 3, 9, 16, 0, 0, tzinfo=IST)
    assert is_market_open(t) is False


def test_market_closed_weekend():
    t = datetime(2026, 3, 7, 12, 0, 0, tzinfo=IST)  # Saturday noon
    assert is_market_open(t) is False


def test_next_trading_day_from_weekend():
    assert next_trading_day(date(2026, 3, 7)) == date(2026, 3, 9)  # Monday


def test_next_trading_day_from_weekday():
    assert next_trading_day(date(2026, 3, 9)) == date(2026, 3, 9)  # Already Monday


def test_trading_days_between():
    # March 9-13: Mon(9), Tue(10=Holi holiday), Wed(11), Thu(12) = 3 trading days
    count = trading_days_between(date(2026, 3, 9), date(2026, 3, 13))
    assert count == 3


def test_trading_days_to_expiry():
    dte = trading_days_to_expiry(date(2026, 3, 12), date(2026, 3, 9))
    assert dte >= 3  # Mon, Tue, Wed, Thu (expiry)


def test_calendar_days_to_expiry():
    assert calendar_days_to_expiry(date(2026, 3, 12), date(2026, 3, 7)) == 5
    assert calendar_days_to_expiry(date(2026, 3, 7), date(2026, 3, 7)) == 0


def test_years_to_expiry():
    yte = years_to_expiry(date(2026, 3, 12), date(2026, 3, 7))
    assert abs(yte - 5 / 365) < 0.001

    # Same day should return small positive (not zero)
    yte_zero = years_to_expiry(date(2026, 3, 7), date(2026, 3, 7))
    assert yte_zero > 0
    assert yte_zero == 1 / 365
