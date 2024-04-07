from datetime import datetime, timedelta
import random
import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .utils import CaseInsensitiveDict


CHROMEDRIVER_PATH = "./chromedriver.exe"
WINDOW_SIZE = "1920,1080"
USER_AGENT = 'Mozilla/5.0 (Windows NT 4.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2049.0 Safari/537.36'

LOGIN_BUTTON = 'loginButton'
SIGNIN_BUTTON = 'signInButton'
USERNAME_INPUT = 'user_session_email'
PASSWORD_INPUT = 'user_session_password'

URL_TIVOLI = "https://tivoli.sportifiq.com/sl"
URL_SVOBODA = "https://svoboda.sportifiq.com/sl"
URL_KOSEZE = "https://tk-cc-koseze.sportifiq.com/sl"


# CONFIG
def configure_driver(headless_mode=False):
    chrome_options = Options()
    if headless_mode:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=%s" % WINDOW_SIZE)
    chrome_options.add_argument(f'--user-agent={USER_AGENT}')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--disable-extensions")
    driver = webdriver.Chrome(executable_path=CHROMEDRIVER_PATH, options=chrome_options)
    return driver


## SELENIUM HELPER FUNCTIONS
def sleep_random_time():
    time.sleep(random.randint(1, 3))


def navigate_to_website(driver, venue_url):
    driver.get(venue_url)
    time.sleep(5)


def click_button_by_id(driver, button_id):
    button = driver.find_element_by_id(button_id)
    button.click()
    sleep_random_time()


def fill_form_by_id(driver, element_id, text):
    input_box = driver.find_element_by_id(element_id)
    input_box.send_keys(text)


def wait_for_element(wait, locator, by):
    try:
        return wait.until(EC.presence_of_element_located((by, locator)))
    except TimeoutException as ex:
        print(f"Exception: {str(ex)} waiting for presence of element located by {by}: {locator}")
        raise ex


def click_on_element_by_locator(driver, locator, by):
    try:
        element = driver.find_element(by, locator)
        element.click()
    except ElementNotInteractableException as ex:
        print(f"Exception: {str(ex)} while trying to click on element located: {locator}")
        raise ex


## SESSION BOOKING FUNCTIONS
def book_single_session(driver, start_hour, end_hour, court):
    session_time = f'{start_hour.strftime("%H:%M")}-{end_hour.strftime("%H:%M")}'

    selectable_xpath = '//*[@id="selectable"]'
    session_xpath_template = '//*[@title="{0} {1}"]'
    original_session_xpath_template = '//*[@original-title="{0} {1}"]'
    confirm_reservation_button_xpath = '//*[@id="confirmBookingBottomSend"]'
    accept_button_xpath = '//*[@id="bookingDetailsModalBottomSend"]'
    close_button_xpath = '//*[@id="flashNoticeCentered"]/div[3]/button'

    try:
        wait = WebDriverWait(driver, 5)
        selectable_button = wait_for_element(wait, selectable_xpath, By.XPATH)
        # selectable_button.click()
        actions = ActionChains(driver)
        actions.move_to_element(selectable_button)
        actions.perform()
        sleep_random_time()

        try:
            session_button_xpath = session_xpath_template.format(session_time, court)
            session_button = wait_for_element(wait, session_button_xpath, By.XPATH)
        except TimeoutException:
            session_button_xpath = original_session_xpath_template.format(session_time, court)
            session_button = wait_for_element(wait, session_button_xpath, By.XPATH)

        session_button.click()
        sleep_random_time()

        try:
            click_on_element_by_locator(driver, confirm_reservation_button_xpath, By.XPATH)
        except ElementNotInteractableException:
            try:
                click_on_element_by_locator(driver, accept_button_xpath, By.XPATH)
            except:
                raise NoSuchElementException

        sleep_random_time()
        try:
            close_button = wait.until(EC.element_to_be_clickable((By.XPATH, close_button_xpath)))
            close_button.click()
        except TimeoutException:
            pass
        return True
    except (NoSuchElementException, TimeoutException):
        return False


def book_half_hour_sessions(driver, start_hour, court):
    first_session_start = start_hour
    first_session_end = start_hour + timedelta(minutes=30)

    second_session_start = start_hour + timedelta(minutes=30)
    second_session_end = start_hour + timedelta(hours=1)

    if book_single_session(driver, first_session_start, first_session_end, court):
        # If the first booking is successful, attempt to book the second session
        if book_single_session(driver, second_session_start, second_session_end, court):
            return True
        else:
            # TODO: undo_single_booking. Problem when first half an hour is available and the second half is not
            pass
    else:
        return False


def book_sessions(driver, start_hour, num_sessions, court):
    if isinstance(start_hour, str):
        start_hour = datetime.strptime(start_hour, '%H:%M')
    success_list = []

    for _ in range(num_sessions):
        # add some random short wait time between actions
        sleep_random_time()
        success = book_single_session(driver, start_hour, start_hour + timedelta(hours=1), court)
        if not success:
            sleep_random_time()
            success = book_half_hour_sessions(driver, start_hour, court)

        success_list.append(success)
        start_hour += timedelta(hours=1)

    return success_list


## MAIN HELPER FUNCTIONS
def get_venue_to_url_map():
    venue_to_url = CaseInsensitiveDict()
    venue_to_url.update({
        'Tivoli': URL_TIVOLI,
        'Svoboda': URL_SVOBODA,
        'Koseze': URL_KOSEZE
    })
    return venue_to_url


def login_to_website(driver, venue_url, user_email, password):
    navigate_to_website(driver, venue_url)
    click_button_by_id(driver, LOGIN_BUTTON)
    fill_form_by_id(driver, USERNAME_INPUT, user_email)
    fill_form_by_id(driver, PASSWORD_INPUT, password)
    click_button_by_id(driver, SIGNIN_BUTTON)


def choose_day(driver, day):
    day_button = driver.find_element_by_xpath(f'//a[text()="{day}"]')
    day_button.click()


def rebook_failed_sessions_on_backup_court(driver, args, booking_results, start_hour):
    for index, booking_successful in enumerate(booking_results):
        if not booking_successful and args.backup_court_name is not None:
            new_start_time = start_hour + timedelta(hours=index)
            if not book_sessions(driver, new_start_time, num_sessions=1, court=args.backup_court_name):
                raise Exception(
                    f"Could not book sessions for either {args.court_name} or {args.backup_court_name} "
                    f"at {new_start_time.strftime('%H:%M')}."
                )


def manage_primary_and_backup_bookings(driver, args):
    start_hour = datetime.strptime(args.hour, '%H:%M')
    booking_results = book_sessions(driver, start_hour, num_sessions=args.num_sessions, court=args.court_name)
    if not all(booking_results):
        rebook_failed_sessions_on_backup_court(driver, args, booking_results, start_hour)

