class SportifiqError(Exception):
    """Base class for all Sportifiq errors."""


class SlotUnavailableError(SportifiqError):
    """Raised by SportifiqPage.book_slot() when no bookable slot is found."""


class LoginError(SportifiqError):
    """Raised when login to Sportifiq fails."""
