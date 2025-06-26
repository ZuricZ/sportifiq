from libs.utils import CaseInsensitiveDict


WINDOW_SIZE = "1920,1080"
USER_AGENT = 'Mozilla/5.0 (Windows NT 4.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2049.0 Safari/537.36'


LOGIN_BUTTON = 'loginButton'
LOGIN_BUTTON_LINK_TEXT = 'Prijavi se'


SIGNIN_BUTTON = 'signInButton'
SIGNIN_BUTTON_NAME = 'commit'


USERNAME_INPUT = 'user_session_email'
PASSWORD_INPUT = 'user_session_password'


URL_TIVOLI = "https://tivoli.sportifiq.com/sl"
URL_SVOBODA = "https://svoboda.sportifiq.com/sl"
URL_KOSEZE = "https://tk-cc-koseze.sportifiq.com/sl"


VENUE_URL_MAPPING = CaseInsensitiveDict({
    'Tivoli': URL_TIVOLI,
    'Svoboda': URL_SVOBODA,
    'Koseze': URL_KOSEZE
})
VENUE_HALF_HOUR_SESSION_MAP = CaseInsensitiveDict({
    'Tivoli': False,
    'Svoboda': False,
    'Koseze': True
})
DAY_NAME_MAPPING = {
    "Monday": "Pon",
    "Tuesday": "Tor",
    "Wednesday": "Sre",
    "Thursday": "Čet",
    "Friday": "Pet",
    "Saturday": "Sob",
    "Sunday": "Ned"
}
