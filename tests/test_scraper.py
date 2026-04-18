"""Tests for pure parsing functions in src/libs/scraper.py."""
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from src.libs.scraper import fmt_time, parse_slo_date, parse_booking_data


FIXED_TODAY = date(2026, 4, 12)


@pytest.fixture(autouse=True)
def freeze_today(monkeypatch):
    mock_date = MagicMock(wraps=date)
    mock_date.today.return_value = FIXED_TODAY
    monkeypatch.setattr("src.libs.scraper.date", mock_date)


# ---------------------------------------------------------------------------
# fmt_time
# ---------------------------------------------------------------------------

class TestFmtTime:
    def test_midnight(self):
        assert fmt_time(datetime(2000, 1, 1, 0, 0)) == "0:00"

    def test_single_digit_hour(self):
        assert fmt_time(datetime(2000, 1, 1, 9, 30)) == "9:30"

    def test_double_digit_hour(self):
        assert fmt_time(datetime(2000, 1, 1, 19, 0)) == "19:00"

    def test_noon(self):
        assert fmt_time(datetime(2000, 1, 1, 12, 0)) == "12:00"


# ---------------------------------------------------------------------------
# parse_slo_date
# ---------------------------------------------------------------------------

class TestParseSloDate:
    def test_future_date_same_year(self):
        assert parse_slo_date("17. apr") == "2026-04-17"

    def test_future_date_with_trailing_comma(self):
        assert parse_slo_date("17. apr,") == "2026-04-17"

    def test_past_date_rolls_over_to_next_year(self):
        assert parse_slo_date("5. jan") == "2027-01-05"

    def test_today_same_day_is_not_past(self):
        assert parse_slo_date("12. apr") == "2026-04-12"

    def test_all_months(self):
        expected = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
            "jul": 7, "avg": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
        }
        for abbr, num in expected.items():
            result = parse_slo_date(f"15. {abbr}")
            assert result is not None
            assert int(result.split("-")[1]) == num

    def test_unknown_month_returns_none(self):
        assert parse_slo_date("15. xyz") is None

    def test_bad_day_returns_none(self):
        assert parse_slo_date("abc. apr") is None

    def test_empty_string_returns_none(self):
        assert parse_slo_date("") is None

    def test_only_one_part_returns_none(self):
        assert parse_slo_date("17.") is None

    def test_december_future_this_year(self):
        assert parse_slo_date("25. dec") == "2026-12-25"


# ---------------------------------------------------------------------------
# parse_booking_data
# ---------------------------------------------------------------------------

class TestParseBookingData:
    def test_happy_path(self):
        result = parse_booking_data(
            href="https://tk-cc-koseze.sportifiq.com/members/bookings/11300768",
            venue_name="TKCC - Koseze",
            court="BALON HC1",
            time_str="19:00 - 20:00",
            raw_date="17. apr",
        )
        assert result is not None
        assert result.site_id == "11300768"
        assert result.venue == "koseze"
        assert result.venue_name == "TKCC - Koseze"
        assert result.date == "2026-04-17"
        assert result.time == "19:00 - 20:00"
        assert result.court == "BALON HC1"

    def test_missing_booking_id_returns_none(self):
        result = parse_booking_data(
            href="https://tk-cc-koseze.sportifiq.com/members/bookings/",
            venue_name="TKCC - Koseze",
            court="BALON HC1",
            time_str="19:00 - 20:00",
            raw_date="17. apr",
        )
        assert result is None

    def test_invalid_date_returns_none(self):
        result = parse_booking_data(
            href="https://tk-cc-koseze.sportifiq.com/members/bookings/123",
            venue_name="TKCC - Koseze",
            court="BALON HC1",
            time_str="19:00 - 20:00",
            raw_date="bad date",
        )
        assert result is None
