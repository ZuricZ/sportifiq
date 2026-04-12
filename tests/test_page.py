"""Tests for pure / mock-friendly methods on SportifiqPage.

No Selenium session is started.  SportifiqPage.__new__ bypasses __init__
so we can test _parse_slo_date and _fmt without a real browser.
"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.page import SportifiqPage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _page() -> SportifiqPage:
    """Return a SportifiqPage instance without calling __init__."""
    page = SportifiqPage.__new__(SportifiqPage)
    return page


# ---------------------------------------------------------------------------
# _fmt
# ---------------------------------------------------------------------------

class TestFmt:
    def test_midnight(self):
        t = datetime(2000, 1, 1, 0, 0)
        assert SportifiqPage._fmt(t) == "0:00"

    def test_single_digit_hour(self):
        t = datetime(2000, 1, 1, 9, 30)
        assert SportifiqPage._fmt(t) == "9:30"

    def test_double_digit_hour(self):
        t = datetime(2000, 1, 1, 19, 0)
        assert SportifiqPage._fmt(t) == "19:00"

    def test_noon(self):
        t = datetime(2000, 1, 1, 12, 0)
        assert SportifiqPage._fmt(t) == "12:00"


# ---------------------------------------------------------------------------
# _parse_slo_date
# ---------------------------------------------------------------------------

FIXED_TODAY = date(2026, 4, 12)  # matches session date


@pytest.fixture(autouse=True)
def freeze_today(monkeypatch):
    """Freeze date.today() to FIXED_TODAY for all tests in this module."""
    mock_date = MagicMock(wraps=date)
    mock_date.today.return_value = FIXED_TODAY
    monkeypatch.setattr("src.page.date", mock_date)


class TestParseSloDate:
    def test_future_date_same_year(self):
        page = _page()
        result = page._parse_slo_date("17. apr")
        assert result == "2026-04-17"

    def test_future_date_with_trailing_comma(self):
        page = _page()
        result = page._parse_slo_date("17. apr,")
        assert result == "2026-04-17"

    def test_past_date_rolls_over_to_next_year(self):
        page = _page()
        # Jan 5 is before Apr 12 — should become 2027-01-05
        result = page._parse_slo_date("5. jan")
        assert result == "2027-01-05"

    def test_today_same_day_is_not_past(self):
        page = _page()
        # Apr 12 == today → not past → current year
        result = page._parse_slo_date("12. apr")
        assert result == "2026-04-12"

    def test_all_months(self):
        page = _page()
        expected_months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
            "jul": 7, "avg": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
        }
        for abbr, num in expected_months.items():
            result = page._parse_slo_date(f"15. {abbr}")
            assert result is not None, f"Failed for month '{abbr}'"
            parsed_month = int(result.split("-")[1])
            assert parsed_month == num, f"Month mismatch for '{abbr}': got {parsed_month}"

    def test_unknown_month_returns_none(self):
        page = _page()
        assert page._parse_slo_date("15. xyz") is None

    def test_bad_day_returns_none(self):
        page = _page()
        assert page._parse_slo_date("abc. apr") is None

    def test_empty_string_returns_none(self):
        page = _page()
        assert page._parse_slo_date("") is None

    def test_only_one_part_returns_none(self):
        page = _page()
        assert page._parse_slo_date("17.") is None

    def test_december_future_this_year(self):
        # Dec 25 is after Apr 12 → 2026
        page = _page()
        result = page._parse_slo_date("25. dec")
        assert result == "2026-12-25"


# ---------------------------------------------------------------------------
# _parse_booking_card  (mocked Selenium element tree)
# ---------------------------------------------------------------------------

def _make_card(
    booking_href: str = "https://tk-cc-koseze.sportifiq.com/members/bookings/11300768",
    venue_name: str = "TKCC - Koseze",
    court_text: str = "BALON HC1",
    date_text: str = "17. apr,\xa019:00 - 20:00",
    time_text: str = "19:00 - 20:00",
):
    """Build a minimal fake Selenium WebElement tree for a booking card."""
    booking_link = MagicMock()
    booking_link.get_attribute.return_value = booking_href

    venue_anchor = MagicMock()
    venue_anchor.text = venue_name

    court_li = MagicMock()
    court_li.text = court_text

    time_span = MagicMock()
    time_span.text = time_text

    date_li = MagicMock()
    date_li.text = date_text
    date_li.find_element.return_value = time_span

    card = MagicMock()

    def fake_find_element(by, xpath):
        if "/members/bookings/" in xpath:
            return booking_link
        if "h3" in xpath:
            return venue_anchor
        return MagicMock()

    def fake_find_elements(by, xpath):
        if "text-left" in xpath:
            return [court_li, date_li]
        return []

    card.find_element.side_effect = fake_find_element
    card.find_elements.side_effect = fake_find_elements
    return card


class TestParseBookingCard:
    def test_happy_path(self):
        page = _page()
        card = _make_card()
        result = page._parse_booking_card(card)
        assert result is not None
        assert result.site_id == "11300768"
        assert result.venue == "koseze"
        assert result.venue_name == "TKCC - Koseze"
        assert result.date == "2026-04-17"
        assert result.time == "19:00 - 20:00"
        assert result.court == "BALON HC1"

    def test_missing_booking_id_returns_none(self):
        page = _page()
        booking_link = MagicMock()
        booking_link.get_attribute.return_value = "https://tk-cc-koseze.sportifiq.com/members/bookings/"

        card = MagicMock()
        card.find_element.return_value = booking_link
        card.find_elements.return_value = []
        result = page._parse_booking_card(card)
        assert result is None

    def test_too_few_inner_items_returns_none(self):
        page = _page()
        booking_link = MagicMock()
        booking_link.get_attribute.return_value = "https://tk-cc-koseze.sportifiq.com/members/bookings/123"

        venue_anchor = MagicMock()
        venue_anchor.text = "TKCC - Koseze"

        card = MagicMock()

        def fake_find_element(by, xpath):
            if "/members/bookings/" in xpath:
                return booking_link
            if "h3" in xpath:
                return venue_anchor
            return MagicMock()

        card.find_element.side_effect = fake_find_element
        card.find_elements.return_value = []  # No inner list items

        result = page._parse_booking_card(card)
        assert result is None
