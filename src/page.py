import random
import time
from datetime import datetime, timedelta

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


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

    def book_slot(self, session_time: str, court: str) -> tuple[bool, str]:
        """Attempt to book a single time slot.

        Args:
            session_time: "HH:MM-HH:MM" (30-min or 60-min window, e.g. "13:30-14:30").
            court: Exact court name as shown on the website (e.g. "BALON HC1").

        Returns:
            (success, site_id) — site_id is the Sportifiq numeric booking ID extracted
            from the post-confirmation redirect URL; empty string on failure.
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
                return False, ""

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
                    return False, ""
                sel.select_by_index(1)
            # else: leave default 0:30h selected

            self._random_sleep()
            self._wait.until(
                EC.element_to_be_clickable((By.XPATH, self._CONFIRM_BUTTON_XPATH))
            ).click()
            self._random_sleep()

            # Wait until redirected away from the booking form
            self._wait.until(lambda d: "bookings/new" not in d.current_url)

            # Capture the site booking ID from the redirect URL before navigating away.
            # The URL is typically "{base}/members/bookings/{numeric_id}".
            site_id = self._extract_booking_id(self._driver.current_url)

            # For multi-session runs: ensure the location page is showing the
            # correct day so the next slot search succeeds.
            self._ensure_correct_day()
            return True, site_id

        except (NoSuchElementException, TimeoutException):
            return False, ""

    def cancel_booking(self, booking_id: str) -> bool:
        """Navigate to the booking detail page and click the cancel button.

        Args:
            booking_id: Numeric or string ID as it appears in the booking URL
                        (e.g. from /members/bookings/12345).

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

    # --- Private helpers ---

    @staticmethod
    def _extract_booking_id(url: str) -> str:
        """Pull the numeric booking ID from a URL like .../members/bookings/12345."""
        import re
        m = re.search(r"/members/bookings/(\d+)", url)
        return m.group(1) if m else ""

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
