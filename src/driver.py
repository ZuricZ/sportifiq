from contextlib import contextmanager
from typing import Generator

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver

_WINDOW_SIZE = "1920,1080"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@contextmanager
def create_driver(headless: bool = True) -> Generator[WebDriver, None, None]:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--window-size={_WINDOW_SIZE}")
    options.add_argument(f"--user-agent={_USER_AGENT}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-dev-shm-usage")  # required in GitHub Actions / Docker

    driver = webdriver.Chrome(options=options)
    try:
        yield driver
    finally:
        driver.quit()
