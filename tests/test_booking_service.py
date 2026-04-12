"""Tests for BookingService fallback logic.

SportifiqPage is mocked — no browser needed.
"""
from unittest.mock import MagicMock, call, patch

import pytest

from src.booking_service import BookingService
from src.models import BookingRequest, VenueConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


def _service(book_slot_side_effect):
    """Return a BookingService whose page.book_slot yields the given values."""
    page = MagicMock()
    page.book_slot.side_effect = book_slot_side_effect
    return BookingService(page), page


# ---------------------------------------------------------------------------
# Single session — hourly succeeds
# ---------------------------------------------------------------------------

class TestHourlySuccess:
    def test_single_session_booked(self):
        svc, page = _service([True])
        results = svc.run(_make_request())
        assert len(results) == 1
        assert results[0].success
        assert results[0].court == "BALON HC1"
        assert results[0].time == "13:00-14:00"
        assert results[0].message == "Booked"

    def test_two_sessions_both_booked(self):
        svc, page = _service([True, True])
        results = svc.run(_make_request(num_sessions=2))
        assert all(r.success for r in results)
        assert results[0].time == "13:00-14:00"
        assert results[1].time == "14:00-15:00"


# ---------------------------------------------------------------------------
# Fallback to two half-hours
# ---------------------------------------------------------------------------

class TestHalfHourFallback:
    def test_hourly_fails_then_two_halves_succeed(self):
        # book_slot calls: hourly fail, first half OK, second half OK
        svc, page = _service([False, True, True])
        results = svc.run(_make_request())
        assert len(results) == 1
        assert results[0].success
        assert results[0].message == "Booked as two half-hours"
        assert results[0].time == "13:00-14:00"  # full slot time reported

    def test_first_half_fails_session_fails(self):
        # hourly fail, first half fail → stop
        svc, page = _service([False, False])
        results = svc.run(_make_request())
        assert not results[0].success
        assert "First half-hour unavailable" in results[0].message

    def test_second_half_fails_partial_booking_reported(self):
        # hourly fail, first half OK, second half fail
        svc, page = _service([False, True, False])
        results = svc.run(_make_request())
        assert not results[0].success
        assert "Second half-hour unavailable" in results[0].message


# ---------------------------------------------------------------------------
# Backup court
# ---------------------------------------------------------------------------

class TestBackupCourt:
    def test_primary_fails_backup_succeeds(self):
        # Primary hourly+halves all fail, backup hourly succeeds
        svc, page = _service([False, False, True])
        results = svc.run(_make_request(backup_court="BALON HC2"))
        assert results[0].success
        assert results[0].court == "BALON HC2"

    def test_primary_and_backup_both_fail_raises(self):
        # Primary fails completely, backup also fails completely
        svc, page = _service([False, False, False, False])
        with pytest.raises(RuntimeError, match="Could not book either primary or backup"):
            svc.run(_make_request(backup_court="BALON HC2"))

    def test_no_backup_configured_failure_is_not_raised(self):
        # Without backup_court, a failed session is returned as-is (no raise)
        svc, page = _service([False, False])
        results = svc.run(_make_request(backup_court=None))
        assert not results[0].success

    def test_two_sessions_second_fails_backup_used(self):
        # Session 1 succeeds (hourly), session 2 fails → backup for session 2 only
        svc, page = _service([True, False, False, True])
        results = svc.run(_make_request(num_sessions=2, backup_court="BALON HC2"))
        assert results[0].success
        assert results[0].court == "BALON HC1"
        assert results[1].success
        assert results[1].court == "BALON HC2"


# ---------------------------------------------------------------------------
# Slot time formatting
# ---------------------------------------------------------------------------

class TestSlotTimeFormatting:
    def test_book_slot_called_with_correct_time(self):
        svc, page = _service([True])
        svc.run(_make_request(num_sessions=1))
        page.book_slot.assert_called_once_with("13:00-14:00", "BALON HC1")

    def test_second_session_time_is_offset_by_one_hour(self):
        svc, page = _service([True, True])
        svc.run(_make_request(num_sessions=2))
        calls = page.book_slot.call_args_list
        assert calls[0] == call("13:00-14:00", "BALON HC1")
        assert calls[1] == call("14:00-15:00", "BALON HC1")
