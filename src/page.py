import random
import re
import time
from datetime import date, datetime, timedelta
from typing import Optional

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from .models import SiteBooking


class SportifiqPage:
    """Page Object for the Sportifiq booking website.

    All CSS/XPath selectors live here as class constants.
    When the website changes, only this file needs updating.
    No business logic — only DOM interactions.
    """

    # --- Selectors ---
    _LOGIN_URL = "https://sportifiq.com/user_sessions/new"
    _EMAIL_INPUT_ID = "user_session_email"
    _PASSWORD_INPUT_ID = "user_session_password"

    # Available slot: <a href=".../members/bookings/new?..."><div title="H:MM - H:MM+30 Court"></div></a>
    _SLOT_LINK_XPATH = '//a[.//div[@title="{title}"]]'
    _DURATION_SELECT_ID = "duration-select"
    _CONFIRM_BUTTON_XPATH = '//button[contains(., "Potrdi rezervacijo")]'

    # "Izbriši" = Delete (the actual label on the booking detail page)
    _CANCEL_BUTTON_XPATH = (
        '//a[normalize-space(.)="Izbriši"] | '
        '//button[normalize-space(.)="Izbriši"] | '
        '//a[contains(., "Prekliči rezervacijo")] | '
        '//button[contains(., "Prekliči rezervacijo")]'
    )

    # Booking card on the profile page and venue /members/bookings page
    _BOOKING_CARD_XPATH = '//li[contains(@class,"col-span-1")]'

    # Slovenian month abbreviations → month number
    _SLO_MONTHS = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
        "jul": 7, "avg": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
    }

    _WAIT_TIMEOUT = 15
    _MIN_SLEEP = 1.0
    _MAX_SLEEP = 3.0

    def __init__(self, driver: WebDriver) -> None:
        self._driver = driver
        self._wait = WebDriverWait(driver, self._WAIT_TIMEOUT)
        self._venue_url: str = ""
        self._selected_day: str = ""

    # --- Public interface ---

    def login(self, url: str, email: str, password: str) -> None:
        """Log in on sportifiq.com then navigate to the venue members page."""
        self._venue_url = url
        self._driver.get(self._LOGIN_URL)
        self._wait.until(EC.presence_of_element_located((By.ID, self._EMAIL_INPUT_ID)))
        self._fill_by_id(self._EMAIL_INPUT_ID, email)
        self._fill_by_id(self._PASSWORD_INPUT_ID, password)
        # Submit via the form containing the email field (avoids ambiguity with
        # the register / forgot-password forms that share the same page).
        self._driver.find_element(By.ID, self._EMAIL_INPUT_ID).submit()
        self._wait.until(lambda d: "user_sessions" not in d.current_url)
        self._random_sleep()
        self._driver.get(url)
        self._wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-date]")))

    def select_day(self, day: str) -> None:
        """Click the day tab on the timetable.

        Accepts either an ISO date ("2026-04-17") or a Slovenian abbreviation
        that matches the website text ("Čet", "ČET", "Pet", …).  The match is
        case-insensitive.  If the requested day is already active (today /
        "DANES") the click is skipped because no data-action is present.

        Uses JS execution to avoid StaleElementReferenceException caused by
        the Stimulus timetable controller re-rendering divs after page load.
        """
        self._selected_day = day
        target = day.upper()

        result = self._driver.execute_script(
            """
            const day = arguments[0];
            const target = arguments[1];
            const divs = document.querySelectorAll('div[data-date]');
            for (const div of divs) {
                const dateAttr = div.getAttribute('data-date') || '';
                const firstLine = (div.innerText.split('\\n')[0] || '').toUpperCase();
                if (dateAttr === day || firstLine === target) {
                    if (div.getAttribute('data-action')) {
                        div.click();
                        return 'clicked';
                    }
                    return 'already_selected';
                }
            }
            return 'not_found';
            """,
            day,
            target,
        )

        if result == "not_found":
            # Day not in the visible strip — try the date input for ISO dates
            if len(day) == 10 and day[4] == "-":
                self._set_date_input(day)
            else:
                raise ValueError(f"Day '{day}' not found in timetable")
        if result == "clicked":
            self._random_sleep()

    def book_slot(self, session_time: str, court: str) -> bool:
        """Attempt to book a single time slot.

        Args:
            session_time: "HH:MM-HH:MM" (30-min or 60-min window, e.g. "13:30-14:30").
            court: Exact court name as shown on the website (e.g. "BALON HC1").

        Returns:
            True if the booking was confirmed, False if the slot was unavailable.
        """
        try:
            start_str, end_str = session_time.split("-")
            start = datetime.strptime(start_str, "%H:%M")
            end = datetime.strptime(end_str, "%H:%M")
            duration_mins = int((end - start).total_seconds() / 60)

            # The website shows slots in 30-min increments; the link title is
            # "H:MM - H:MM+30 CourtName" regardless of the booking duration.
            slot_end = start + timedelta(minutes=30)
            title = f"{self._fmt(start)} - {self._fmt(slot_end)} {court}"
            xpath = self._SLOT_LINK_XPATH.format(title=title)

            try:
                link = self._wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            except TimeoutException:
                return False

            link.click()
            self._random_sleep()

            # Wait for the booking confirmation page
            self._wait.until(lambda d: "bookings/new" in d.current_url)

            # Choose duration: 0:30h (index 0, default) or 1:00h (index 1)
            sel = Select(
                self._wait.until(
                    EC.presence_of_element_located((By.ID, self._DURATION_SELECT_ID))
                )
            )
            if duration_mins >= 60:
                if len(sel.options) < 2:
                    # 1-hour option not available; go back and report failure
                    self._driver.back()
                    self._wait.until(lambda d: "bookings/new" not in d.current_url)
                    return False
                sel.select_by_index(1)
            # else: leave default 0:30h selected

            self._random_sleep()
            self._wait.until(
                EC.element_to_be_clickable((By.XPATH, self._CONFIRM_BUTTON_XPATH))
            ).click()
            self._random_sleep()

            # Wait until redirected away from the booking form
            self._wait.until(lambda d: "bookings/new" not in d.current_url)

            # For multi-session runs: ensure the location page is showing the
            # correct day so the next slot search succeeds.
            self._ensure_correct_day()
            return True

        except (NoSuchElementException, TimeoutException):
            return False

    def cancel_booking(self, booking_id: str) -> bool:
        """Navigate to the booking detail page and click the cancel button.

        Args:
            booking_id: Numeric ID from the Sportifiq booking URL
                        (e.g. "12345" from /members/bookings/12345).

        Returns:
            True if cancellation was confirmed, False if the booking was not
            found or was already cancelled.
        """
        # Derive base URL: strip "/members/location" (and any trailing slash)
        base_url = self._venue_url.split("/members/")[0]
        booking_url = f"{base_url}/members/bookings/{booking_id}"

        self._driver.get(booking_url)
        self._random_sleep()

        try:
            cancel_btn = self._wait.until(
                EC.element_to_be_clickable((By.XPATH, self._CANCEL_BUTTON_XPATH))
            )
        except TimeoutException:
            return False

        cancel_btn.click()
        self._random_sleep()

        # Handle JS confirm() dialog if the site uses one
        try:
            alert = self._driver.switch_to.alert
            alert.accept()
            self._random_sleep()
        except Exception:
            pass  # No dialog — that's fine

        # Wait until redirected away from the booking page
        try:
            self._wait.until(lambda d: f"bookings/{booking_id}" not in d.current_url)
        except TimeoutException:
            # Some sites stay on the page but show a success message; treat as success
            pass

        return True

    def get_upcoming_bookings(self) -> list[SiteBooking]:
        """Scrape all upcoming reservations from the user's profile page.

        Navigates to sportifiq.com/user_pages/users/{username} and parses every
        booking card.  The profile page shows bookings across all venues, making
        this the single source of truth for the reminder workflow.

        Returns:
            List of SiteBooking objects for confirmed future reservations,
            sorted by date then time.  Returns [] if the user has none.
        """
        # Extract username from the logged-in navbar profile link
        username = self._driver.execute_script("""
            const links = document.querySelectorAll('a[href*="/user_pages/users/"]');
            for (const l of links) {
                const m = l.href.match(/\\/user_pages\\/users\\/([^/?#]+)/);
                if (m) return m[1];
            }
            return null;
        """)
        if not username:
            raise RuntimeError("Could not determine logged-in username from navbar.")

        profile_url = f"https://sportifiq.com/user_pages/users/{username}"
        self._driver.get(profile_url)
        # Wait for either the booking grid or the "no reservations" message
        self._wait.until(lambda d: d.find_elements(By.XPATH, self._BOOKING_CARD_XPATH)
                         or "rezervacij" in d.find_element(By.TAG_NAME, "body").text)
        self._random_sleep()

        cards = self._driver.find_elements(By.XPATH, self._BOOKING_CARD_XPATH)
        bookings: list[SiteBooking] = []
        today = date.today().isoformat()

        for card in cards:
            try:
                booking = self._parse_booking_card(card)
                if booking and booking.date >= today:
                    bookings.append(booking)
            except Exception:
                continue  # Skip malformed cards

        bookings.sort(key=lambda b: (b.date, b.time))
        return bookings

    # --- Private helpers ---

    def _parse_booking_card(self, card) -> Optional[SiteBooking]:
        """Parse a single booking <li> card element into a SiteBooking."""
        # Booking detail link → site_id and venue base URL
        booking_link = card.find_element(By.XPATH, './/a[contains(@href,"/members/bookings/")]')
        href = booking_link.get_attribute("href") or ""
        m = re.search(r"/members/bookings/(\d+)", href)
        if not m:
            return None
        site_id = m.group(1)

        # Venue key from subdomain: "tk-cc-koseze.sportifiq.com" → "koseze"
        subdomain_m = re.match(r"https?://([^.]+)\.sportifiq\.com", href)
        venue_subdomain = subdomain_m.group(1) if subdomain_m else ""
        # Use the last segment of the subdomain as the venue key
        venue_key = venue_subdomain.split("-")[-1] if venue_subdomain else venue_subdomain

        # Venue display name
        venue_name = card.find_element(By.XPATH, './/h3//a').text.strip()

        # Inner list items: first = court (with sport icon img), second = date + time
        inner_items = card.find_elements(By.XPATH, './/ul[contains(@class,"text-left")]//li')
        if len(inner_items) < 2:
            return None

        court = inner_items[0].text.strip()
        date_li = inner_items[1]
        time_str = date_li.find_element(By.XPATH, './/span[contains(@class,"whitespace-nowrap")]').text.strip()

        # Date text is the li text minus the time span text: e.g. "17. apr,\xa019:00 - 20:00" → "17. apr,"
        raw_date = date_li.text.replace(time_str, "").strip().rstrip(",").strip()
        iso_date = self._parse_slo_date(raw_date)
        if not iso_date:
            return None

        return SiteBooking(
            site_id=site_id,
            venue=venue_key,
            venue_name=venue_name,
            date=iso_date,
            time=time_str,
            court=court,
        )

    def _parse_slo_date(self, raw: str) -> Optional[str]:
        """Convert "17. apr" (or "17. apr,") to "YYYY-MM-DD".

        If the resulting date is before today, assumes next year.
        """
        # Normalise: strip trailing punctuation, collapse whitespace
        raw = re.sub(r"[,.\s]+$", "", raw.strip())
        parts = raw.split()
        if len(parts) < 2:
            return None
        try:
            day = int(parts[0].rstrip("."))
        except ValueError:
            return None
        month_key = parts[1].lower()[:3]
        month = self._SLO_MONTHS.get(month_key)
        if not month:
            return None
        today = date.today()
        year = today.year
        candidate = date(year, month, day)
        if candidate < today:
            candidate = date(year + 1, month, day)
        return candidate.isoformat()

    def _ensure_correct_day(self) -> None:
        """After a redirect, make sure we're on the location page / correct day."""
        if "members/location" not in self._driver.current_url:
            self._driver.get(self._venue_url)
            self._wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-date]"))
            )
        if self._selected_day:
            self.select_day(self._selected_day)

    def _set_date_input(self, iso_date: str) -> None:
        """Set the date picker input and wait for the timetable to reload."""
        self._driver.execute_script(
            """
            const inp = document.querySelector('input[type="date"]');
            if (!inp) return;
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            nativeInputValueSetter.call(inp, arguments[0]);
            inp.dispatchEvent(new Event('input', {bubbles: true}));
            inp.dispatchEvent(new Event('change', {bubbles: true}));
            """,
            iso_date,
        )
        self._random_sleep()

    @staticmethod
    def _fmt(t: datetime) -> str:
        """Format time without a leading zero on the hour, matching site display."""
        return f"{t.hour}:{t.strftime('%M')}"

    def _fill_by_id(self, element_id: str, text: str) -> None:
        self._driver.find_element(By.ID, element_id).send_keys(text)

    def _random_sleep(self) -> None:
        time.sleep(random.uniform(self._MIN_SLEEP, self._MAX_SLEEP))
