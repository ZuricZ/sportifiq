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
    """
    Configure and return a WebDriver instance with specified options.

    :param headless_mode: Determines if the browser should run in headless mode. Defaults to False.
    :type headless_mode: bool
    :return: WebDriver instance configured with specified options.
    :rtype: selenium.webdriver.WebDriver
    """
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
    """
    Sleeps for a random amount of time between 1 and 3 seconds.

    :return: None
    """
    time.sleep(random.randint(1, 3))


def navigate_to_website(driver, venue_url):
    """
    :param driver: WebDriver object used to control the web browser
    :param venue_url: URL of the website to navigate to
    :return: None

    This method navigates the web browser to the specified website URL. It waits for 5 seconds after loading the URL to allow the page to fully load.
    """
    driver.get(venue_url)
    time.sleep(5)


def click_button_by_id(driver, button_id):
    """
    Clicks a button by its ID.

    :param driver: The WebDriver instance.
    :param button_id: The ID of the button to be clicked.
    :return: None.
    """
    button = driver.find_element_by_id(button_id)
    button.click()
    sleep_random_time()


def fill_form_by_id(driver, element_id, text):
    """
    Fill Form By ID

    This method is used to fill an input form field on a web page by its element ID.

    :param driver: The instance of WebDriver that represents the browser session.
    :param element_id: The ID attribute of the input form field.
    :param text: The text to be entered into the input form field.
    :return: None

    Example usage:
        ::

            driver = webdriver.Chrome()
            fill_form_by_id(driver, 'username', 'john_doe')

    This will locate the input form field with the specified ID and enter the given text into it.
    """
    input_box = driver.find_element_by_id(element_id)
    input_box.send_keys(text)


def wait_for_element(wait, locator, by):
    """
    Wait for an element to be present and return it.

    :param wait: Wait object from Selenium WebDriver to define the maximum wait time.
    :type wait: selenium.webdriver.support.ui.WebDriverWait

    :param locator: Locator for the element to be located.
    :type locator: str

    :param by: The method to locate the element (e.g., By.ID, By.CLASS_NAME, By.XPATH).
    :type by: str

    :return: The located element.
    :rtype: selenium.webdriver.remote.webelement.WebElement

    :raises TimeoutException: if the element is not located within the specified wait time.
    """
    try:
        return wait.until(EC.presence_of_element_located((by, locator)))
    except TimeoutException as ex:
        print(f"Exception: {str(ex)} waiting for presence of element located by {by}: {locator}")
        raise ex


def click_on_element_by_locator(driver, locator, by):
    """
    :param driver: WebDriver instance to interact with the web browser.
    :param locator: The locator strategy used to find the element. Can be any valid locator strategy supported by Selenium.
    :param by: The value of the locator used to identify the element.
    :return: None

    This method clicks on the element located using the provided locator strategy and value. It first finds the element using the WebDriver instance and then simulates a click action on it.

    If the element cannot be interacted with, an ElementNotInteractableException is raised, and an error message is printed before re-raising the exception.
    """
    try:
        element = driver.find_element(by, locator)
        element.click()
    except ElementNotInteractableException as ex:
        print(f"Exception: {str(ex)} while trying to click on element located: {locator}")
        raise ex


## SESSION BOOKING FUNCTIONS
def book_single_session(driver, start_hour, end_hour, court):
    """
    :param driver: The WebDriver object used to control the browser.
    :param start_hour: The start hour of the session to be booked.
    :param end_hour: The end hour of the session to be booked.
    :param court: The court number of the session to be booked.
    :return: True if booking was successful, False otherwise.
    """
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
    """
    :param driver: The webdriver instance for interacting with the booking website.
    :param start_hour: The starting hour of the session to be booked.
    :param court: The court number to be booked.
    :return: True if both the half-hour sessions are successfully booked, False otherwise.

    This method books two consecutive half-hour sessions on a specified court, starting from the given start_hour. It uses the provided webdriver instance to interact with the booking website.

    The method first calculates the start and end times for the two half-hour sessions. It then attempts to book the first session using the 'book_single_session' method. If the first session booking is successful, it proceeds to book the second session using the same method.

    If both sessions are successfully booked, it returns True. If the second session booking fails, it does not undo the booking for the first session. Note that there is a TODO comment in the code indicating that handling this scenario is not implemented yet.

    If the first session booking fails, it returns False.

    Example usage:

    >>> driver = create_webdriver()
    >>> start_hour = datetime.now()  # Set the start time to the current time
    >>> court = "Court 1"
    >>> if book_half_hour_sessions(driver, start_hour, court):
    ...     print("Sessions booked successfully")
    ... else:
    ...     print("Booking failed")

    """
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
    """
    :param driver: The WebDriver object that will be used to interact with the web application.
    :param start_hour: The starting hour of the sessions to be booked. Can be provided as a string in the format 'HH:MM' or as a datetime object.
    :param num_sessions: The number of sessions to be booked.
    :param court: The court number or identifier for the sessions.
    :return: A list containing the success status of each booked session.

    Book sessions function that allows the user to book multiple sessions at a given start hour for a specific court. This function takes in the WebDriver object, start hour, number of sessions, and court identifier as parameters. The start hour can be provided as a string in the format 'HH:MM' or as a datetime object. The function iterates over the number of sessions, booking each session one hour apart from the previous one.

    Within each iteration, a random short wait time is added between actions using the `sleep_random_time` function. The `book_single_session` function is called to attempt to book a session for the provided start hour, end hour (calculated as start_hour + timedelta(hours=1)), and court. If the booking is unsuccessful, another attempt is made by calling the `book_half_hour_sessions` function with the start hour and court.

    The success status of each booking is stored in a list, and the start hour is incremented by one hour for the next iteration. Finally, the function returns the list of success statuses.
    """
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
    """

    This method returns a mapping of venue names to their corresponding URLs.

    :return: A mapping of venue names to their corresponding URLs.

    """
    venue_to_url = CaseInsensitiveDict()
    venue_to_url.update({
        'Tivoli': URL_TIVOLI,
        'Svoboda': URL_SVOBODA,
        'Koseze': URL_KOSEZE
    })
    return venue_to_url


def login_to_website(driver, venue_url, user_email, password):
    """
    Logs in to a website using the given credentials.

    :param driver: The WebDriver object used for browser automation.
    :type driver: WebDriver

    :param venue_url: The URL of the website to login to.
    :type venue_url: str

    :param user_email: The email address of the user.
    :type user_email: str

    :param password: The password of the user.
    :type password: str

    :return: None
    :rtype: NoneType
    """
    navigate_to_website(driver, venue_url)
    click_button_by_id(driver, LOGIN_BUTTON)
    fill_form_by_id(driver, USERNAME_INPUT, user_email)
    fill_form_by_id(driver, PASSWORD_INPUT, password)
    click_button_by_id(driver, SIGNIN_BUTTON)


def choose_day(driver, day):
    """
    :param driver: The web driver object used to interact with the web page.
    :param day: The day of the week to choose.
    :return: None

    This method clicks on the button corresponding to the given day on the web page using the provided web driver object.
    """
    day_button = driver.find_element_by_xpath(f'//a[text()="{day}"]')
    day_button.click()


def rebook_failed_sessions_on_backup_court(driver, args, booking_results, start_hour):
    """
    :param driver: The Selenium WebDriver instance.
    :param args: An object containing the arguments passed to the script.
    :param booking_results: A list of boolean values indicating whether the booking for each session was successful or not.
    :param start_hour: The starting hour for the session bookings.

    :return: None.

    This method rebooks failed sessions on a backup court. It iterates over the booking_results list and checks if the booking for each session was successful. If not, and a backup_court_name is provided in the args object, it attempts to book the session on the backup court.

    The method uses the start_hour parameter to calculate the start time for each session. It then calls the book_sessions method with the appropriate parameters to attempt the booking on the backup court.

    If the booking on the backup court also fails, an exception is raised with a detailed error message indicating the court names and start time that could not be booked.
    """
    for index, booking_successful in enumerate(booking_results):
        if not booking_successful and args.backup_court_name is not None:
            new_start_time = start_hour + timedelta(hours=index)
            if not book_sessions(driver, new_start_time, num_sessions=1, court=args.backup_court_name):
                raise Exception(
                    f"Could not book sessions for either {args.court_name} or {args.backup_court_name} "
                    f"at {new_start_time.strftime('%H:%M')}."
                )


def manage_primary_and_backup_bookings(driver, args):
    """
    Manage primary and backup bookings.

    :param driver: The web driver object used to interact with the booking system.
    :param args: The arguments required for managing the bookings.
        - hour: The start hour of the sessions in 'HH:MM' format.
        - num_sessions: The number of sessions to book.
        - court_name: The name of the court to book.

    :return: None

    """
    start_hour = datetime.strptime(args.hour, '%H:%M')
    booking_results = book_sessions(driver, start_hour, num_sessions=args.num_sessions, court=args.court_name)
    if not all(booking_results):
        rebook_failed_sessions_on_backup_court(driver, args, booking_results, start_hour)

