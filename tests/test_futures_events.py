"""Tests for futures-specific events in the event calendar."""

from datetime import date, timedelta

from diamond_options.data.events import (
    get_futures_events,
    get_upcoming_events,
    get_events_for_date,
    is_rollover_window,
    days_to_futures_expiry,
    _EVENTS_2026,
)


class TestFuturesEventTypes:
    def test_futures_expiry_events_exist(self):
        events = [e for e in _EVENTS_2026 if e.event_type == "futures_expiry"]
        assert len(events) == 12  # One per month

    def test_rollover_window_events_exist(self):
        events = [e for e in _EVENTS_2026 if e.event_type == "rollover_window"]
        assert len(events) == 12

    def test_delivery_margin_events_exist(self):
        events = [e for e in _EVENTS_2026 if e.event_type == "delivery_margin"]
        assert len(events) == 12

    def test_quarterly_rollover_events_exist(self):
        events = [e for e in _EVENTS_2026 if e.event_type == "quarterly_rollover"]
        assert len(events) == 4  # Mar, Jun, Sep, Dec

    def test_futures_expiry_has_correct_impact(self):
        events = [e for e in _EVENTS_2026 if e.event_type == "futures_expiry"]
        quarterly = [e for e in events if e.impact == "high"]
        monthly = [e for e in events if e.impact == "medium"]
        assert len(quarterly) == 4  # Mar, Jun, Sep, Dec
        assert len(monthly) == 8  # Other months

    def test_delivery_margin_is_high_impact(self):
        events = [e for e in _EVENTS_2026 if e.event_type == "delivery_margin"]
        assert all(e.impact == "high" for e in events)

    def test_rollover_before_expiry(self):
        expiry_events = {
            e.date: e for e in _EVENTS_2026 if e.event_type == "futures_expiry"
        }
        rollover_events = [
            e for e in _EVENTS_2026 if e.event_type == "rollover_window"
        ]
        for r in rollover_events:
            # Find the matching expiry (rollover date + 7 days)
            expected_expiry = r.date + timedelta(days=7)
            assert expected_expiry in expiry_events

    def test_delivery_before_expiry(self):
        expiry_events = {
            e.date: e for e in _EVENTS_2026 if e.event_type == "futures_expiry"
        }
        delivery_events = [
            e for e in _EVENTS_2026 if e.event_type == "delivery_margin"
        ]
        for d in delivery_events:
            expected_expiry = d.date + timedelta(days=4)
            assert expected_expiry in expiry_events


class TestFuturesEventContent:
    def test_futures_expiry_title(self):
        jan_expiry = [
            e for e in _EVENTS_2026
            if e.event_type == "futures_expiry" and e.date.month == 1
        ]
        assert len(jan_expiry) == 1
        assert "January" in jan_expiry[0].title
        assert "Futures Expiry" in jan_expiry[0].title

    def test_delivery_margin_description(self):
        events = [e for e in _EVENTS_2026 if e.event_type == "delivery_margin"]
        for e in events:
            assert "40-50%" in e.description
            assert "stock futures" in e.description.lower()

    def test_quarterly_rollover_description(self):
        events = [e for e in _EVENTS_2026 if e.event_type == "quarterly_rollover"]
        for e in events:
            assert "heavy volume" in e.description.lower() or "Heavy volume" in e.description

    def test_affected_symbols(self):
        futures_events = [e for e in _EVENTS_2026 if e.event_type == "futures_expiry"]
        assert all("ALL_FUTURES" in e.affected_symbols for e in futures_events)

        delivery_events = [e for e in _EVENTS_2026 if e.event_type == "delivery_margin"]
        assert all("ALL_STOCK_FUTURES" in e.affected_symbols for e in delivery_events)


class TestGetFuturesEvents:
    def test_get_futures_events_filters_correctly(self):
        # Pick a date range that includes a known expiry month
        events = get_futures_events(from_date=date(2026, 3, 1), days_ahead=31)
        types = {e.event_type for e in events}
        # Should only contain futures event types
        futures_types = {"futures_expiry", "rollover_window", "delivery_margin", "quarterly_rollover"}
        assert types.issubset(futures_types)
        assert len(events) > 0

    def test_get_futures_events_march_quarterly(self):
        events = get_futures_events(from_date=date(2026, 3, 1), days_ahead=31)
        types = {e.event_type for e in events}
        assert "quarterly_rollover" in types  # March is quarterly

    def test_get_futures_events_february_no_quarterly(self):
        events = get_futures_events(from_date=date(2026, 2, 1), days_ahead=28)
        types = {e.event_type for e in events}
        assert "quarterly_rollover" not in types  # February is not quarterly

    def test_existing_events_not_broken(self):
        # Ensure existing event types still work
        rbi = get_upcoming_events(
            from_date=date(2026, 2, 1), days_ahead=10,
            event_types=["rbi_policy"],
        )
        assert len(rbi) > 0  # Feb 4-6 RBI meeting


class TestIsRolloverWindow:
    def test_rollover_window_detected(self):
        # Find a rollover event date
        rollover_events = [
            e for e in _EVENTS_2026 if e.event_type == "rollover_window"
        ]
        if rollover_events:
            rd = rollover_events[0].date
            assert is_rollover_window(rd) is True
            assert is_rollover_window(rd + timedelta(days=3)) is True

    def test_not_rollover_window(self):
        # Jan 1 should not be in any rollover window
        assert is_rollover_window(date(2026, 1, 1)) is False


class TestDaysToFuturesExpiry:
    def test_days_calculated(self):
        # On Jan 1, next expiry is Jan's monthly expiry
        days = days_to_futures_expiry(date(2026, 1, 1))
        assert days > 0
        assert days <= 31

    def test_on_expiry_day(self):
        expiry_events = [
            e for e in _EVENTS_2026 if e.event_type == "futures_expiry"
        ]
        if expiry_events:
            days = days_to_futures_expiry(expiry_events[0].date)
            assert days == 0

    def test_fallback_when_past_all(self):
        days = days_to_futures_expiry(date(2027, 12, 31))
        assert days == 30  # Default fallback
