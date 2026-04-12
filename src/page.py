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
        """
        self._selected_day = day
        target = day.upper()
        elements = self._driver.find_elements(By.CSS_SELECTOR, "div[data-date]")
        for el in elements:
            date_attr = el.get_attribute("data-date") or ""
            first_line = (el.text.split("\n")[0] or "").upper()
            if date_attr == day or first_line == target:
                if el.get_attribute("data-action"):
                    el.click()
                    self._random_sleep()
                return
        raise ValueError(f"Day '{day}' not found in timetable")

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

    # --- Private helpers ---

    def _ensure_correct_day(self) -> None:
        """After a redirect, make sure we're on the location page / correct day."""
        if "members/location" not in self._driver.current_url:
            self._driver.get(self._venue_url)
            self._wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-date]"))
            )
        if self._selected_day:
            self.select_day(self._selected_day)

    @staticmethod
    def _fmt(t: datetime) -> str:
        """Format time without a leading zero on the hour, matching site display."""
        return f"{t.hour}:{t.strftime('%M')}"

    def _fill_by_id(self, element_id: str, text: str) -> None:
        self._driver.find_element(By.ID, element_id).send_keys(text)

    def _random_sleep(self) -> None:
        time.sleep(random.uniform(self._MIN_SLEEP, self._MAX_SLEEP))
