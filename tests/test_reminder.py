"""Tests for pure helper functions in src/reminder.py."""
import hashlib
import hmac
import time
from unittest.mock import patch

import pytest

from src.models import SiteBooking
from src.reminder import (
    _build_email,
    _cancel_url,
    _make_cancel_token,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SECRET = "test-secret-abc123"

BOOKING = SiteBooking(
    site_id="11300768",
    venue="koseze",
    venue_name="TKCC - Koseze",
    date="2026-04-14",
    time="19:00 - 20:00",
    court="BALON HC1",
)

BOOKING_2 = SiteBooking(
    site_id="11300900",
    venue="koseze",
    venue_name="TKCC - Koseze",
    date="2026-04-21",
    time="13:00 - 14:00",
    court="BALON HC2",
)


# ---------------------------------------------------------------------------
# _make_cancel_token
# ---------------------------------------------------------------------------

class TestMakeCancelToken:
    def test_returns_hex_string_and_future_expiry(self):
        tok, exp = _make_cancel_token("11300768", SECRET)
        assert isinstance(tok, str)
        assert len(tok) == 64  # SHA-256 hex digest
        assert exp > int(time.time())

    def test_expiry_is_roughly_48_hours(self):
        tok, exp = _make_cancel_token("11300768", SECRET)
        delta = exp - int(time.time())
        assert 47 * 3600 < delta <= 48 * 3600 + 5  # 5s tolerance

    def test_token_is_correct_hmac(self):
        tok, exp = _make_cancel_token("11300768", SECRET)
        payload = f"11300768:{exp}"
        expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        assert tok == expected

    def test_different_site_ids_produce_different_tokens(self):
        tok1, _ = _make_cancel_token("111", SECRET)
        tok2, _ = _make_cancel_token("222", SECRET)
        assert tok1 != tok2


# ---------------------------------------------------------------------------
# _cancel_url
# ---------------------------------------------------------------------------

class TestCancelUrl:
    def test_url_contains_site_id_token_exp_user(self):
        url = _cancel_url(BOOKING, SECRET, "https://ZuricZ.github.io/sportifiq-public", "ZZ")
        assert "id=11300768" in url
        assert "t=" in url
        assert "exp=" in url
        assert "user=ZZ" in url

    def test_url_base_has_trailing_slash_stripped(self):
        url1 = _cancel_url(BOOKING, SECRET, "https://ZuricZ.github.io/sportifiq-public/", "ZZ")
        url2 = _cancel_url(BOOKING, SECRET, "https://ZuricZ.github.io/sportifiq-public", "ZZ")
        assert url1.split("?")[0] == url2.split("?")[0]

    def test_token_verifies_correctly(self):
        url = _cancel_url(BOOKING, SECRET, "https://example.github.io/sportifiq-public", "ZZ")
        qs = dict(p.split("=") for p in url.split("?")[1].split("&"))
        site_id = qs["id"]
        tok = qs["t"]
        exp = int(qs["exp"])
        payload = f"{site_id}:{exp}"
        expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        assert hmac.compare_digest(tok, expected)


# ---------------------------------------------------------------------------
# _build_email
# ---------------------------------------------------------------------------

class TestBuildEmail:
    def test_subject_contains_booking_count(self):
        cancel_links = {BOOKING.site_id: "https://example.github.io/sportifiq/?id=11300768&t=abc&exp=999&user=ZZ&venue=koseze"}
        subject, _ = _build_email([BOOKING], cancel_links)
        assert "1" in subject

    def test_body_contains_cancel_link(self):
        url = "https://example.github.io/sportifiq/?id=11300768&t=abc&exp=999&user=ZZ&venue=koseze"
        cancel_links = {BOOKING.site_id: url}
        _, html = _build_email([BOOKING], cancel_links)
        assert url in html

    def test_body_contains_booking_details(self):
        cancel_links = {BOOKING.site_id: "https://example.github.io/sportifiq/?id=11300768&t=abc&exp=999&user=ZZ&venue=koseze"}
        _, html = _build_email([BOOKING], cancel_links)
        assert "2026-04-14" in html
        assert "19:00 - 20:00" in html
        assert "BALON HC1" in html
        assert "TKCC - Koseze" in html

    def test_body_contains_all_upcoming_bookings(self):
        cancel_links = {
            BOOKING.site_id: "https://example.github.io/sportifiq/?id=11300768&t=abc&exp=999&user=ZZ&venue=koseze",
            BOOKING_2.site_id: "https://example.github.io/sportifiq/?id=11300769&t=abc&exp=999&user=ZZ&venue=koseze",
        }
        _, html = _build_email([BOOKING, BOOKING_2], cancel_links)
        assert "2026-04-14" in html
        assert "2026-04-21" in html
