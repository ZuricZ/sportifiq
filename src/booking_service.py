import logging
from datetime import datetime, timedelta

from .models import BookingRequest, BookingResult
from .page import SportifiqPage

logger = logging.getLogger(__name__)

_TIME_FORMAT = "%H:%M"
_HALF_HOUR = timedelta(minutes=30)


class BookingService:
    """Orchestrates the booking workflow using a SportifiqPage.

    Knows *what* to book and *when* to fall back; delegates all
    Selenium interaction to SportifiqPage.
    """

    def __init__(self, page: SportifiqPage) -> None:
        self._page = page

    def run(self, request: BookingRequest) -> list[BookingResult]:
        """Execute the full booking workflow.

        Books `request.num_sessions` consecutive hourly slots on the
        primary court starting at `request.time`. Any slot that fails
        is retried on `request.backup_court` if one is configured.

        Raises:
            RuntimeError: If a slot cannot be booked on either court.
        """
        start = datetime.strptime(request.time, _TIME_FORMAT)
        results: list[BookingResult] = []

        for i in range(request.num_sessions):
            slot_start = start + timedelta(hours=i)
            result = self._book_session(slot_start, request.court)
            results.append(result)
            logger.info("Session %d/%d [%s]: %s", i + 1, request.num_sessions, request.court, result.message)

        if request.backup_court:
            results = self._retry_failed_on_backup(results, start, request.backup_court)

        return results

    # --- Private ---

    def _book_session(self, start: datetime, court: str) -> BookingResult:
        """Try a full-hour slot; fall back to two half-hour slots."""
        result = self._book_hourly(start, court)
        if not result.success:
            result = self._book_as_two_half_hours(start, court)
        return result

    def _book_hourly(self, start: datetime, court: str) -> BookingResult:
        end = start + timedelta(hours=1)
        session_time = f"{start.strftime(_TIME_FORMAT)}-{end.strftime(_TIME_FORMAT)}"
        success = self._page.book_slot(session_time, court)
        return BookingResult(
            success=success,
            court=court,
            time=session_time,
            message="Booked" if success else "Slot unavailable",
        )

    def _book_as_two_half_hours(self, start: datetime, court: str) -> BookingResult:
        mid = start + _HALF_HOUR
        end = start + timedelta(hours=1)

        first_time = f"{start.strftime(_TIME_FORMAT)}-{mid.strftime(_TIME_FORMAT)}"
        second_time = f"{mid.strftime(_TIME_FORMAT)}-{end.strftime(_TIME_FORMAT)}"
        full_time = f"{start.strftime(_TIME_FORMAT)}-{end.strftime(_TIME_FORMAT)}"

        if not self._page.book_slot(first_time, court):
            return BookingResult(success=False, court=court, time=first_time, message="First half-hour unavailable")

        if not self._page.book_slot(second_time, court):
            # First slot was booked but second failed — manual cleanup may be needed.
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
        self, results: list[BookingResult], start: datetime, backup_court: str
    ) -> list[BookingResult]:
        for i, result in enumerate(results):
            if result.success:
                continue
            slot_start = start + timedelta(hours=i)
            logger.info("Retrying %s on backup court %s", slot_start.strftime("%H:%M"), backup_court)
            backup_result = self._book_session(slot_start, backup_court)
            if not backup_result.success:
                raise RuntimeError(
                    f"Could not book either primary or backup court at {slot_start.strftime(_TIME_FORMAT)}. "
                    f"Primary: {result.court}, Backup: {backup_court}"
                )
            results[i] = backup_result
        return results
