import logging
import random
import re
import time
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from .exceptions import SlotUnavailableError
from .models import SiteBooking
from .scraper import fmt_time, parse_booking_data


class SportifiqPage:
    """Page Object for the Sportifiq booking website."""

    _LOGIN_URL = "https://sportifiq.com/user_sessions/new"
    _EMAIL_INPUT_ID = "user_session_email"
    _PASSWORD_INPUT_ID = "user_session_password"
    _SLOT_LINK_XPATH = '//a[.//div[@title="{title}"]]'
    _DURATION_SELECT_ID = "duration-select"
    _CONFIRM_BUTTON_XPATH = (
        '//button[contains(., "Potrdi rezervacijo")] | '
        '//button[contains(., "Rezerviraj in plačaj s kartico")]'
    )
    _CANCEL_BUTTON_XPATH = (
        '//a[normalize-space(.)="Izbriši"] | '
        '//button[normalize-space(.)="Izbriši"] | '
        '//a[contains(., "Prekliči rezervacijo")] | '
        '//button[contains(., "Prekliči rezervacijo")]'
    )
    _BOOKING_CARD_XPATH = '//li[contains(@class,"col-span-1")]'

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
        self._venue_url = url
        self._driver.get(self._LOGIN_URL)
        self._wait.until(EC.presence_of_element_located((By.ID, self._EMAIL_INPUT_ID)))
        self._fill_by_id(self._EMAIL_INPUT_ID, email)
        self._fill_by_id(self._PASSWORD_INPUT_ID, password)
        self._driver.find_element(By.ID, self._EMAIL_INPUT_ID).submit()
        self._wait.until(lambda d: "user_sessions" not in d.current_url)
        self._random_sleep()
        self._driver.get(url)
        self._maybe_accept_terms()
        if url not in self._driver.current_url:
            self._driver.get(url)
        self._wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-date]")))

    def select_day(self, day: str) -> None:
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
            if len(day) == 10 and day[4] == "-":
                self._set_date_input(day)
            else:
                raise ValueError(f"Day '{day}' not found in timetable")
        if result == "clicked":
            self._random_sleep()

    def book_slot(self, session_time: str, court: str) -> None:
        """Attempt to book a single time slot.

        Raises:
            SlotUnavailableError: if no bookable slot is found.
        """
        start_str, end_str = session_time.split("-")
        start = datetime.strptime(start_str, "%H:%M")
        end = datetime.strptime(end_str, "%H:%M")
        duration_mins = int((end - start).total_seconds() / 60)

        link = self._find_slot_link(start, court)
        self._click(link)
        self._wait.until(lambda d: "bookings/new" in d.current_url)
        self._select_duration(duration_mins)
        self._confirm_booking()
        self._ensure_correct_day()

    def cancel_booking(self, booking_id: str) -> bool:
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
        try:
            alert = self._driver.switch_to.alert
            alert.accept()
            self._random_sleep()
        except Exception:
            pass
        try:
            self._wait.until(lambda d: f"bookings/{booking_id}" not in d.current_url)
        except TimeoutException:
            pass
        return True

    def get_upcoming_bookings(self) -> list[SiteBooking]:
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
        self._wait.until(lambda d: d.find_elements(By.XPATH, self._BOOKING_CARD_XPATH)
                         or "rezervacij" in d.find_element(By.TAG_NAME, "body").text)
        self._random_sleep()
        cards = self._driver.find_elements(By.XPATH, self._BOOKING_CARD_XPATH)
        bookings: list[SiteBooking] = []
        today = date.today().isoformat()
        for card in cards:
            try:
                booking = self._extract_card_data(card)
                if booking and booking.date >= today:
                    bookings.append(booking)
            except Exception:
                continue
        bookings.sort(key=lambda b: (b.date, b.time))
        return bookings

    # --- Private helpers ---

    def _find_slot_link(self, start: datetime, court: str):
        """Return a clickable slot link element, or raise SlotUnavailableError."""
        for slot_mins in (30, 60):
            slot_end = start + timedelta(minutes=slot_mins)
            title = f"{fmt_time(start)} - {fmt_time(slot_end)} {court}"
            xpath = self._SLOT_LINK_XPATH.format(title=title)
            try:
                return self._wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            except TimeoutException:
                continue
        raise SlotUnavailableError(f"No slot found for {fmt_time(start)} on {court}")

    def _click(self, element) -> None:
        """Click an element, falling back to JS click on intercept."""
        try:
            element.click()
        except Exception:
            self._driver.execute_script("arguments[0].click();", element)
        self._random_sleep()

    def _select_duration(self, duration_mins: int) -> None:
        """Select 1-hour duration if the dropdown is present and has options."""
        elements = self._driver.find_elements(By.ID, self._DURATION_SELECT_ID)
        if elements and duration_mins >= 60:
            sel = Select(elements[0])
            if len(sel.options) >= 2:
                sel.select_by_index(1)
        self._random_sleep()

    def _confirm_booking(self) -> None:
        """Click the confirm button and wait for redirect away from booking form."""
        self._wait.until(
            EC.element_to_be_clickable((By.XPATH, self._CONFIRM_BUTTON_XPATH))
        ).click()
        self._random_sleep()
        self._wait.until(lambda d: "bookings/new" not in d.current_url)

    def _extract_card_data(self, card) -> Optional[SiteBooking]:
        """Extract raw strings from a Selenium booking card element and parse them."""
        booking_link = card.find_element(By.XPATH, './/a[contains(@href,"/members/bookings/")]')
        href = booking_link.get_attribute("href") or ""
        venue_name = card.find_element(By.XPATH, './/h3//a').text.strip()
        inner_items = card.find_elements(By.XPATH, './/ul[contains(@class,"text-left")]//li')
        if len(inner_items) < 2:
            return None
        court = inner_items[0].text.strip()
        time_span = inner_items[1].find_element(By.XPATH, './/span[contains(@class,"whitespace-nowrap")]')
        time_str = time_span.text.strip()
        raw_date = inner_items[1].text.replace(time_str, "").strip().rstrip(",").strip()
        return parse_booking_data(href, venue_name, court, time_str, raw_date)

    def _ensure_correct_day(self) -> None:
        if "members/location" not in self._driver.current_url:
            self._driver.get(self._venue_url)
            self._wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-date]")))
        if self._selected_day:
            self.select_day(self._selected_day)

    def _set_date_input(self, iso_date: str) -> None:
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

    def _maybe_accept_terms(self) -> None:
        """Handle the Sportifiq terms-acceptance page if redirected there.

        Sportifiq redirects to /user_pages/terms_acceptance when terms have not
        been accepted. Checks only the mandatory terms/privacy checkbox; the
        marketing news checkbox must never be checked.
        """
        _TERMS_URL_FRAGMENT = "terms_acceptance"
        _TERMS_CB_ID = "agreed_to_terms_of_service"
        _NEWS_CB_ID = "agreed_to_marketing"
        _POPUP_TIMEOUT = 5

        try:
            WebDriverWait(self._driver, _POPUP_TIMEOUT).until(
                lambda d: _TERMS_URL_FRAGMENT in d.current_url
            )
        except TimeoutException:
            logger.debug("No terms_acceptance redirect — skipping.")
            return

        logger.info("Terms acceptance page detected — accepting terms only.")

        # Check terms checkbox
        try:
            terms_cb = self._driver.find_element(By.ID, _TERMS_CB_ID)
            if not terms_cb.is_selected():
                logger.info("Checking terms checkbox.")
                terms_cb.click()
        except NoSuchElementException:
            logger.warning("Terms checkbox (#%s) not found.", _TERMS_CB_ID)

        # Ensure marketing checkbox is NOT checked
        try:
            news_cb = self._driver.find_element(By.ID, _NEWS_CB_ID)
            if news_cb.is_selected():
                logger.info("Unchecking marketing checkbox.")
                news_cb.click()
        except NoSuchElementException:
            pass

        # Submit — Nadaljuj is input[type="submit"], not a <button>
        try:
            nadaljuj = self._driver.find_element(
                By.XPATH, '//input[@type="submit" and @value="Nadaljuj"]'
            )
            logger.info("Clicking Nadaljuj submit button.")
            nadaljuj.click()
            self._wait.until(lambda d: _TERMS_URL_FRAGMENT not in d.current_url)
            logger.info("Terms accepted — continuing to venue page.")
        except (NoSuchElementException, TimeoutException) as exc:
            logger.warning("Could not complete terms acceptance: %s", exc)

    def _fill_by_id(self, element_id: str, text: str) -> None:
        self._driver.find_element(By.ID, element_id).send_keys(text)

    def _random_sleep(self) -> None:
        time.sleep(random.uniform(self._MIN_SLEEP, self._MAX_SLEEP))
