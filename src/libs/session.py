from contextlib import contextmanager
from typing import Iterator

from .config_loader import get_password, load_venue_config
from .driver import create_driver
from .page import SportifiqPage


@contextmanager
def sportifiq_session(venue: str, email: str, headless: bool = True) -> Iterator[SportifiqPage]:
    """Log in to Sportifiq and yield an authenticated SportifiqPage.

    Usage:
        with sportifiq_session("koseze", "user@example.com") as page:
            page.select_day("2026-04-19")
            ...
    """
    venue_config = load_venue_config(venue)
    password = get_password()
    with create_driver(headless=headless) as driver:
        page = SportifiqPage(driver)
        page.login(venue_config.url, email, password)
        yield page
