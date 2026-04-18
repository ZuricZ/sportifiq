# Design: src/ Refactor

**Date:** 2026-04-18  
**Motivation:** Apply KISS, SRP, and separation of concerns to the `src/` package.
The codebase had grown organically: pure functions were buried inside a Selenium class,
the same login block was copy-pasted across three entry points, `BookingService` was a
class wrapping a single function, and two bugs had crept in silently.

---

## New Structure

```
src/
├── libs/                    library code (imported by runners and tests)
│   ├── __init__.py
│   ├── booking_service.py   book() function (was BookingService class)
│   ├── config_loader.py     unchanged
│   ├── driver.py            unchanged
│   ├── exceptions.py        NEW — SportifiqError, SlotUnavailableError, LoginError
│   ├── log.py               unchanged
│   ├── models.py            unchanged
│   ├── page.py              slimmed — delegates parsing to scraper.py
│   ├── scraper.py           NEW — pure parsing functions
│   └── session.py           NEW — shared login context manager
├── templates/
│   └── reminder_email.html  unchanged
├── book.py                  runner (was main.py)
├── cancel.py                runner (was cancel.py, slimmed)
├── remind.py                runner (was reminder.py, slimmed)
└── get_pwd.py               one-time setup script (bug fix only)
```

---

## Changes by File

### NEW: `src/libs/scraper.py`

Pure functions extracted from `SportifiqPage`. Zero I/O, fully unit-testable.

```python
SLO_MONTHS: dict[str, int]          # was SportifiqPage._SLO_MONTHS

def fmt_time(t: datetime) -> str    # was SportifiqPage._fmt
def parse_slo_date(raw: str) -> str | None   # was SportifiqPage._parse_slo_date
def parse_booking_data(
    href: str, venue_name: str, court: str,
    time_str: str, raw_date: str
) -> SiteBooking | None              # was the parsing half of _parse_booking_card
```

`parse_booking_data` receives raw strings and returns a `SiteBooking`. The Selenium
half (reading `.text`, `.get_attribute()`) stays in `page.py` as `_extract_card_data(card)`.

### NEW: `src/libs/session.py`

The same 7-line setup block appeared in `main.py`, `cancel.py`, and `reminder.py`.
Extracted as a context manager (Rule of Three).

```python
@contextmanager
def sportifiq_session(venue: str, email: str, headless: bool = True) -> Iterator[SportifiqPage]:
    venue_config = load_venue_config(venue)
    password = get_password()
    with create_driver(headless=headless) as driver:
        page = SportifiqPage(driver)
        page.login(venue_config.url, email, password)
        yield page
```

### NEW: `src/libs/exceptions.py`

```python
class SportifiqError(Exception): pass
class SlotUnavailableError(SportifiqError): pass
class LoginError(SportifiqError): pass
```

### CHANGED: `src/libs/booking_service.py`

`BookingService` held no state — `__init__` only stored `page`. Converted to a
module-level function. Private helpers become module-level private functions.

```python
# Before
service = BookingService(page)
results = service.run(request)

# After
results = book(page, request)
```

### CHANGED: `src/libs/page.py`

- Removes `_fmt`, `_parse_slo_date`, `_SLO_MONTHS` (now in `scraper.py`)
- `_parse_booking_card` → `_extract_card_data(card)` calls `scraper.parse_booking_data()`
- `book_slot()` raises `SlotUnavailableError` instead of returning `False`
  (distinguishes "slot taken" from unexpected errors, which now propagate)
- `book_slot()` 65-line body split into `_find_slot_link()`, `_select_duration()`, `_confirm_booking()`

### CHANGED: `src/book.py` (was `src/main.py`)

- Uses `sportifiq_session()` — removes the inline setup block
- Adds back `import json` (was accidentally removed; `json.load()` was still called — silent bug)

### CHANGED: `src/cancel.py`

- Uses `sportifiq_session()` — removes the inline setup block

### CHANGED: `src/remind.py` (was `src/reminder.py`)

- Uses `sportifiq_session()` — removes the inline setup block

### CHANGED: `src/get_pwd.py`

- Wraps body in `if __name__ == "__main__":` — currently has side effects on import

---

## Test Changes

| Old | New |
|-----|-----|
| `tests/test_page.py::TestFmt` | `tests/test_scraper.py::TestFmtTime` |
| `tests/test_page.py::TestParseSloDate` | `tests/test_scraper.py::TestParseSloDate` |
| `tests/test_page.py::TestParseBookingCard` | `tests/test_scraper.py::TestParseBookingData` — raw strings instead of mock Selenium elements |
| `tests/test_booking_service.py` | Updated: `book(page, request)` instead of `BookingService(page).run(request)`; `side_effect` uses `SlotUnavailableError` for failures |

`freeze_today` fixture patches `src.libs.scraper.date` (was `src.page.date`).

All imports across tests update from `src.x` → `src.libs.x`.

---

## GitHub Actions

Workflow `python -m` invocations update:

| Before | After |
|--------|-------|
| `python -m src.main` | `python -m src.book` |
| `python -m src.cancel` | `python -m src.cancel` (unchanged) |
| `python -m src.reminder` | `python -m src.remind` |

---

## What Is NOT Changed

- All logic in `page.py` (Selenium interactions, wait patterns, fallback behaviour)
- `config_loader.py`, `driver.py`, `log.py`, `models.py` — no changes to content
- `src/templates/reminder_email.html` — unchanged
- GitHub Actions secrets, environments, workflow logic

---

## Verification

```bash
python -m pytest tests/ -v   # all tests pass (count may differ as test_scraper.py replaces some test_page.py tests)
python -m src.book --help     # entry point works
python -m src.cancel --help
python -m src.remind --help
```
