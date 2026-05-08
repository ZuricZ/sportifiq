from contextlib import contextmanager
from typing import Iterator

from .config_loader import get_password, load_venue_config
from .driver import create_driver
from .page import SportifiqPage


@contextmanager
def sportifiq_session(venue: str | None, email: str, headless: bool = True) -> Iterator[SportifiqPage]:
    """Log in to Sportifiq and yield an authenticated SportifiqPage.

    Args:
        venue: Venue key (e.g. "koseze"). Pass None when no venue page is
            needed (e.g. remind flow — navigates to profile directly).
        email: Sportifiq login email.
        headless: Whether to run Chrome in headless mode.

    Usage:
        with sportifiq_session("koseze", "user@example.com") as page:
            page.select_day("2026-04-19")
            ...
        with sportifiq_session(None, "user@example.com") as page:
            bookings = page.get_upcoming_bookings()
    """
    url = load_venue_config(venue).url if venue else None
    password = get_password()
    with create_driver(headless=headless) as driver:
        page = SportifiqPage(driver)
        page.login(url, email, password)
        yield page
