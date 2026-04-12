import random
import time

from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class SportifiqPage:
    """Page Object for the Sportifiq booking website.

    All CSS/XPath selectors live here as class constants.
    When the website changes, only this file needs updating.
    No business logic — only DOM interactions.
    """

    # --- Selectors ---
    _LOGIN_BUTTON_ID = "loginButton"
    _SIGNIN_BUTTON_ID = "signInButton"
    _USERNAME_INPUT_ID = "user_session_email"
    _PASSWORD_INPUT_ID = "user_session_password"

    _SELECTABLE_XPATH = '//*[@id="selectable"]'
    # Sportifiq uses two different attribute names for session titles depending on booking state;
    # the compound XPath matches either in a single DOM query.
    _SESSION_BUTTON_XPATH = '//*[@title="{time} {court}" or @original-title="{time} {court}"]'
    _CONFIRM_BOOKING_XPATH = '//*[@id="confirmBookingBottomSend"]'
    _ACCEPT_BOOKING_XPATH = '//*[@id="bookingDetailsModalBottomSend"]'
    _CLOSE_NOTICE_XPATH = '//*[@id="flashNoticeCentered"]/div[3]/button'
    _DAY_LINK_XPATH = '//a[text()="{day}"]'

    _WAIT_TIMEOUT = 10
    _MIN_SLEEP = 1.0
    _MAX_SLEEP = 3.0

    def __init__(self, driver: WebDriver) -> None:
        self._driver = driver
        self._wait = WebDriverWait(driver, self._WAIT_TIMEOUT)

    # --- Public interface ---

    def login(self, url: str, email: str, password: str) -> None:
        self._driver.get(url)
        # Wait for the login button to be clickable rather than using a fixed sleep
        self._wait.until(EC.element_to_be_clickable((By.ID, self._LOGIN_BUTTON_ID))).click()
        self._random_sleep()
        self._fill_by_id(self._USERNAME_INPUT_ID, email)
        self._fill_by_id(self._PASSWORD_INPUT_ID, password)
        self._click_by_id(self._SIGNIN_BUTTON_ID)

    def select_day(self, day: str) -> None:
        xpath = self._DAY_LINK_XPATH.format(day=day)
        self._wait.until(EC.element_to_be_clickable((By.XPATH, xpath))).click()

    def book_slot(self, session_time: str, court: str) -> bool:
        """Attempt to book a single time slot.

        Args:
            session_time: Formatted as "HH:MM-HH:MM".
            court: Exact court name as displayed on the website.

        Returns:
            True if the booking was confirmed, False if the slot was unavailable.
        """
        try:
            selectable = self._wait.until(EC.presence_of_element_located((By.XPATH, self._SELECTABLE_XPATH)))
            ActionChains(self._driver).move_to_element(selectable).perform()
            self._random_sleep()

            xpath = self._SESSION_BUTTON_XPATH.format(time=session_time, court=court)
            try:
                session_button = self._wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            except TimeoutException:
                return False

            session_button.click()
            self._random_sleep()

            self._confirm_booking()
            self._random_sleep()
            self._dismiss_notice()
            return True

        except (NoSuchElementException, TimeoutException):
            return False

    # --- Private helpers ---

    def _confirm_booking(self) -> None:
        try:
            self._driver.find_element(By.XPATH, self._CONFIRM_BOOKING_XPATH).click()
        except ElementNotInteractableException:
            try:
                self._driver.find_element(By.XPATH, self._ACCEPT_BOOKING_XPATH).click()
            except ElementNotInteractableException:
                raise NoSuchElementException("Neither confirm nor accept booking button was interactable")

    def _dismiss_notice(self) -> None:
        try:
            self._wait.until(EC.element_to_be_clickable((By.XPATH, self._CLOSE_NOTICE_XPATH))).click()
        except TimeoutException:
            pass  # notice is optional

    def _click_by_id(self, element_id: str) -> None:
        self._driver.find_element(By.ID, element_id).click()
        self._random_sleep()

    def _fill_by_id(self, element_id: str, text: str) -> None:
        self._driver.find_element(By.ID, element_id).send_keys(text)

    def _random_sleep(self) -> None:
        time.sleep(random.uniform(self._MIN_SLEEP, self._MAX_SLEEP))
