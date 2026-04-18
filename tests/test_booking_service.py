"""Tests for book() fallback logic. SportifiqPage is mocked — no browser needed."""
from unittest.mock import MagicMock, call

import pytest

from src.libs.booking_service import book
from src.libs.exceptions import SlotUnavailableError
from src.libs.models import BookingRequest, VenueConfig


VENUE_CONFIG = VenueConfig(
    name="Koseze",
    url="https://tk-cc-koseze.sportifiq.com/members/location",
    courts=["BALON HC1", "BALON HC2"],
    backup_courts=["BALON HC2"],
)


def _make_request(num_sessions=1, court="BALON HC1", backup_court=None):
    return BookingRequest(
        venue_config=VENUE_CONFIG,
        day="2026-04-19",
        time="13:00",
        num_sessions=num_sessions,
        court=court,
        user_email="user@example.com",
        backup_court=backup_court,
    )


def _make_page(results):
    """results: list of True (success) or False (SlotUnavailableError)."""
    page = MagicMock()
    page.book_slot.side_effect = [None if r else SlotUnavailableError() for r in results]
    return page


# ---------------------------------------------------------------------------
# Single session — hourly succeeds
# ---------------------------------------------------------------------------

class TestHourlySuccess:
    def test_single_session_booked(self):
        page = _make_page([True])
        results = book(page, _make_request())
        assert len(results) == 1
        assert results[0].success
        assert results[0].court == "BALON HC1"
        assert results[0].time == "13:00-14:00"
        assert results[0].message == "Booked"

    def test_two_sessions_both_booked(self):
        page = _make_page([True, True])
        results = book(page, _make_request(num_sessions=2))
        assert all(r.success for r in results)
        assert results[0].time == "13:00-14:00"
        assert results[1].time == "14:00-15:00"


# ---------------------------------------------------------------------------
# Fallback to two half-hours
# ---------------------------------------------------------------------------

class TestHalfHourFallback:
    def test_hourly_fails_then_two_halves_succeed(self):
        page = _make_page([False, True, True])
        results = book(page, _make_request())
        assert len(results) == 1
        assert results[0].success
        assert results[0].message == "Booked as two half-hours"
        assert results[0].time == "13:00-14:00"

    def test_first_half_fails_session_fails(self):
        page = _make_page([False, False])
        results = book(page, _make_request())
        assert not results[0].success
        assert "First half-hour unavailable" in results[0].message

    def test_second_half_fails_partial_booking_reported(self):
        page = _make_page([False, True, False])
        results = book(page, _make_request())
        assert not results[0].success
        assert "Second half-hour unavailable" in results[0].message


# ---------------------------------------------------------------------------
# Backup court
# ---------------------------------------------------------------------------

class TestBackupCourt:
    def test_primary_fails_backup_succeeds(self):
        page = _make_page([False, False, True])
        results = book(page, _make_request(backup_court="BALON HC2"))
        assert results[0].success
        assert results[0].court == "BALON HC2"

    def test_primary_and_backup_both_fail_raises(self):
        page = _make_page([False, False, False, False])
        with pytest.raises(RuntimeError, match="Could not book either primary or backup"):
            book(page, _make_request(backup_court="BALON HC2"))

    def test_no_backup_configured_failure_is_not_raised(self):
        page = _make_page([False, False])
        results = book(page, _make_request(backup_court=None))
        assert not results[0].success

    def test_two_sessions_second_fails_backup_used(self):
        page = _make_page([True, False, False, True])
        results = book(page, _make_request(num_sessions=2, backup_court="BALON HC2"))
        assert results[0].success and results[0].court == "BALON HC1"
        assert results[1].success and results[1].court == "BALON HC2"


# ---------------------------------------------------------------------------
# Slot time formatting
# ---------------------------------------------------------------------------

class TestSlotTimeFormatting:
    def test_book_slot_called_with_correct_time(self):
        page = _make_page([True])
        book(page, _make_request(num_sessions=1))
        page.book_slot.assert_called_once_with("13:00-14:00", "BALON HC1")

    def test_second_session_time_is_offset_by_one_hour(self):
        page = _make_page([True, True])
        book(page, _make_request(num_sessions=2))
        calls = page.book_slot.call_args_list
        assert calls[0] == call("13:00-14:00", "BALON HC1")
        assert calls[1] == call("14:00-15:00", "BALON HC1")
