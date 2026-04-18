import logging
from datetime import datetime, timedelta

from .exceptions import SlotUnavailableError
from .models import BookingRequest, BookingResult
from .page import SportifiqPage

logger = logging.getLogger(__name__)

_TIME_FORMAT = "%H:%M"
_HALF_HOUR = timedelta(minutes=30)


def book(page: SportifiqPage, request: BookingRequest) -> list[BookingResult]:
    """Execute the full booking workflow for all requested sessions."""
    start = datetime.strptime(request.time, _TIME_FORMAT)
    results: list[BookingResult] = []

    for i in range(request.num_sessions):
        slot_start = start + timedelta(hours=i)
        result = _book_session(page, slot_start, request.court)
        results.append(result)
        logger.info("Session %d/%d [%s]: %s", i + 1, request.num_sessions, request.court, result.message)

    if request.backup_court:
        results = _retry_failed_on_backup(page, results, start, request.backup_court)

    return results


def _book_session(page: SportifiqPage, start: datetime, court: str) -> BookingResult:
    result = _book_hourly(page, start, court)
    if not result.success:
        result = _book_as_two_half_hours(page, start, court)
    return result


def _book_hourly(page: SportifiqPage, start: datetime, court: str) -> BookingResult:
    end = start + timedelta(hours=1)
    session_time = f"{start.strftime(_TIME_FORMAT)}-{end.strftime(_TIME_FORMAT)}"
    try:
        page.book_slot(session_time, court)
        return BookingResult(success=True, court=court, time=session_time, message="Booked")
    except SlotUnavailableError:
        return BookingResult(success=False, court=court, time=session_time, message="Slot unavailable")


def _book_as_two_half_hours(page: SportifiqPage, start: datetime, court: str) -> BookingResult:
    mid = start + _HALF_HOUR
    end = start + timedelta(hours=1)
    first_time = f"{start.strftime(_TIME_FORMAT)}-{mid.strftime(_TIME_FORMAT)}"
    second_time = f"{mid.strftime(_TIME_FORMAT)}-{end.strftime(_TIME_FORMAT)}"
    full_time = f"{start.strftime(_TIME_FORMAT)}-{end.strftime(_TIME_FORMAT)}"

    try:
        page.book_slot(first_time, court)
    except SlotUnavailableError:
        return BookingResult(success=False, court=court, time=first_time, message="First half-hour unavailable")

    try:
        page.book_slot(second_time, court)
    except SlotUnavailableError:
        logger.warning(
            "Partial booking: %s booked %s but %s failed — manual cancellation may be needed.",
            court, first_time, second_time,
        )
        return BookingResult(
            success=False, court=court, time=second_time,
            message="Second half-hour unavailable (first half-hour was booked)",
        )

    return BookingResult(success=True, court=court, time=full_time, message="Booked as two half-hours")


def _retry_failed_on_backup(
    page: SportifiqPage,
    results: list[BookingResult],
    start: datetime,
    backup_court: str,
) -> list[BookingResult]:
    for i, result in enumerate(results):
        if result.success:
            continue
        slot_start = start + timedelta(hours=i)
        logger.info("Retrying %s on backup court %s", slot_start.strftime(_TIME_FORMAT), backup_court)
        backup_result = _book_session(page, slot_start, backup_court)
        if not backup_result.success:
            raise RuntimeError(
                f"Could not book either primary or backup court at {slot_start.strftime(_TIME_FORMAT)}. "
                f"Primary: {result.court}, Backup: {backup_court}"
            )
        results[i] = backup_result
    return results
