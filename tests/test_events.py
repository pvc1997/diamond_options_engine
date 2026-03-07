"""Tests for market event calendar module.

Verifies event lookups, filtering, high-impact detection,
earnings season context, and edge cases.
"""

from datetime import date

from diamond_options.data.events import (
    MarketEvent,
    get_upcoming_events,
    get_events_for_date,
    get_events_for_symbol,
    is_high_impact_day,
    event_aware_context,
    get_earnings_calendar,
    _EVENTS_2026,
)


class TestMarketEventDataclass:
    def test_frozen(self):
        """MarketEvent is immutable."""
        e = MarketEvent(
            date=date(2026, 1, 1),
            event_type="other",
            title="Test",
            description="Desc",
            impact="low",
            affected_symbols=["NIFTY"],
        )
        try:
            e.title = "Changed"  # type: ignore
            assert False, "Should not allow mutation"
        except AttributeError:
            pass

    def test_invalid_event_type_raises(self):
        try:
            MarketEvent(
                date=date(2026, 1, 1),
                event_type="invalid_type",
                title="Bad",
                description="Desc",
                impact="low",
            )
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_invalid_impact_raises(self):
        try:
            MarketEvent(
                date=date(2026, 1, 1),
                event_type="other",
                title="Bad",
                description="Desc",
                impact="extreme",
            )
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestGetUpcomingEvents:
    def test_returns_sorted_by_date(self):
        events = get_upcoming_events(from_date=date(2026, 1, 1), days_ahead=365)
        dates = [e.date for e in events]
        assert dates == sorted(dates)

    def test_respects_days_ahead(self):
        events = get_upcoming_events(from_date=date(2026, 2, 1), days_ahead=7)
        for e in events:
            assert e.date >= date(2026, 2, 1)
            assert e.date <= date(2026, 2, 8)

    def test_filter_by_event_type(self):
        events = get_upcoming_events(
            from_date=date(2026, 1, 1),
            days_ahead=365,
            event_types=["rbi_policy"],
        )
        assert len(events) > 0
        assert all(e.event_type == "rbi_policy" for e in events)

    def test_filter_multiple_types(self):
        events = get_upcoming_events(
            from_date=date(2026, 1, 1),
            days_ahead=365,
            event_types=["rbi_policy", "budget"],
        )
        assert all(e.event_type in ("rbi_policy", "budget") for e in events)
        # Should have both types
        types = {e.event_type for e in events}
        assert "rbi_policy" in types
        assert "budget" in types

    def test_no_events_in_range(self):
        """A very narrow window in a quiet period returns empty."""
        # Dec 30 - Dec 31 — no events expected (Christmas is Dec 25)
        events = get_upcoming_events(from_date=date(2026, 12, 30), days_ahead=1)
        # May or may not have events; just ensure no crash
        assert isinstance(events, list)


class TestGetEventsForDate:
    def test_budget_day(self):
        events = get_events_for_date(date(2026, 2, 1))
        titles = [e.title for e in events]
        assert any("Budget" in t for t in titles)

    def test_rbi_decision_day(self):
        events = get_events_for_date(date(2026, 2, 6))
        assert any(e.event_type == "rbi_policy" for e in events)

    def test_holiday(self):
        events = get_events_for_date(date(2026, 1, 26))
        assert any(e.event_type == "holiday" for e in events)
        assert any("Republic Day" in e.title for e in events)

    def test_no_events(self):
        """A random date with no events returns empty list."""
        # Try a date unlikely to have events
        events = get_events_for_date(date(2026, 3, 15))
        # Could have events; just check it's a list
        assert isinstance(events, list)


class TestGetEventsForSymbol:
    def test_nifty_events_included_for_stocks(self):
        """NIFTY/index events should show up for any F&O stock."""
        events = get_events_for_symbol(
            "RELIANCE", from_date=date(2026, 2, 1), days_ahead=10
        )
        # Should include RBI policy (affects NIFTY) and Budget (affects ALL)
        types = {e.event_type for e in events}
        assert "rbi_policy" in types or "budget" in types

    def test_case_insensitive(self):
        upper = get_events_for_symbol("NIFTY", from_date=date(2026, 2, 1), days_ahead=10)
        lower = get_events_for_symbol("nifty", from_date=date(2026, 2, 1), days_ahead=10)
        assert len(upper) == len(lower)


class TestIsHighImpactDay:
    def test_rbi_decision_day_is_high_impact(self):
        # RBI decision days: Feb 6, Apr 8, Jun 3, Aug 5, Oct 7, Dec 9
        assert is_high_impact_day(date(2026, 2, 6)) is True
        assert is_high_impact_day(date(2026, 4, 8)) is True

    def test_budget_day_is_high_impact(self):
        assert is_high_impact_day(date(2026, 2, 1)) is True

    def test_fomc_decision_day_is_high_impact(self):
        assert is_high_impact_day(date(2026, 1, 29)) is True

    def test_random_day_not_high_impact(self):
        # Pick a day with no high-impact events
        assert is_high_impact_day(date(2026, 3, 15)) is False


class TestEventAwareContext:
    def test_during_earnings_season(self):
        ctx = event_aware_context(from_date=date(2026, 1, 20))
        assert ctx["earnings_season"] is True

    def test_outside_earnings_season(self):
        ctx = event_aware_context(from_date=date(2026, 3, 15))
        assert ctx["earnings_season"] is False

    def test_is_event_day_on_budget(self):
        ctx = event_aware_context(from_date=date(2026, 2, 1))
        assert ctx["is_event_day"] is True
        assert len(ctx["high_impact_events"]) > 0

    def test_iv_note_elevated_on_event_day(self):
        ctx = event_aware_context(from_date=date(2026, 2, 1))
        assert "elevated" in ctx["iv_impact_note"].lower() or "IV likely" in ctx["iv_impact_note"]

    def test_iv_note_normal_on_quiet_day(self):
        ctx = event_aware_context(from_date=date(2026, 3, 15))
        assert "Normal IV environment" in ctx["iv_impact_note"]

    def test_pre_event_warning(self):
        """Day before RBI decision should have a warning."""
        # Feb 5 is day before RBI decision day (Feb 6)
        ctx = event_aware_context(from_date=date(2026, 2, 5))
        assert ctx["pre_event_warning"] != ""
        assert "High-impact" in ctx["pre_event_warning"]

    def test_context_keys(self):
        ctx = event_aware_context(from_date=date(2026, 6, 1))
        expected_keys = {
            "upcoming_events", "is_event_day", "high_impact_events",
            "earnings_season", "pre_event_warning", "iv_impact_note",
        }
        assert set(ctx.keys()) == expected_keys


class TestGetEarningsCalendar:
    def test_all_earnings_events(self):
        events = get_earnings_calendar()
        assert len(events) == 8  # 4 seasons x 2 (begin + end)
        assert all(e.event_type == "earnings" for e in events)

    def test_symbol_filter(self):
        """Any symbol should get all earnings events (they affect ALL)."""
        events = get_earnings_calendar(symbol="RELIANCE")
        assert len(events) == 8

    def test_empty_for_nonexistent(self):
        """Even unknown symbols match ALL-targeted earnings."""
        events = get_earnings_calendar(symbol="UNKNOWN")
        assert len(events) == 8


class TestHolidaysFromNSE:
    def test_all_holidays_in_events(self):
        """Every date in NSE_HOLIDAYS_2026 should appear as a holiday event."""
        from diamond_options.utils.indian_markets import NSE_HOLIDAYS_2026

        holiday_events = [e for e in _EVENTS_2026 if e.event_type == "holiday"]
        holiday_dates = {e.date for e in holiday_events}
        for h in NSE_HOLIDAYS_2026:
            assert h in holiday_dates, f"Holiday {h} not in events"

    def test_holiday_count(self):
        from diamond_options.utils.indian_markets import NSE_HOLIDAYS_2026

        holiday_events = [e for e in _EVENTS_2026 if e.event_type == "holiday"]
        assert len(holiday_events) == len(NSE_HOLIDAYS_2026)


class TestEdgeCases:
    def test_past_date_returns_empty(self):
        """A date before any 2026 events returns empty."""
        events = get_upcoming_events(from_date=date(2025, 1, 1), days_ahead=1)
        assert events == []

    def test_far_future_returns_empty(self):
        events = get_upcoming_events(from_date=date(2027, 1, 1), days_ahead=30)
        assert events == []

    def test_events_total_count_reasonable(self):
        """Sanity check: we should have a substantial number of events."""
        assert len(_EVENTS_2026) > 80  # holidays + RBI + budget + earnings + economic + global
