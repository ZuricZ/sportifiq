import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.booking_service import BookingService
from src.config_loader import get_password, load_venue_config
from src.driver import create_driver
from src.gist_manager import GistManager
from src.models import BookingRequest, Reservation
from src.page import SportifiqPage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_CONFIG_FILE = Path("config.json")
_KNOWN_CONFIG_KEYS = {"venue", "day", "hour", "num_sessions", "court_name", "backup_court_name", "user_email", "debug_mode"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Book a court on Sportifiq.")
    parser.add_argument("--venue", required=True, type=str.lower, help="Venue key (e.g. koseze)")
    parser.add_argument("--day", required=True, help="ISO date (e.g. 2026-04-17) or Slovenian day abbreviation (e.g. Čet)")
    parser.add_argument("--hour", required=True, help="Start time in HH:MM format")
    parser.add_argument("--num_sessions", required=True, type=int, help="Number of consecutive hourly sessions")
    parser.add_argument("--court_name", required=True, help="Exact court name as shown on the website")
    parser.add_argument("--backup_court_name", default=None, help="Fallback court name")
    parser.add_argument("--user_email", required=True, help="Sportifiq account email")
    parser.add_argument("--debug_mode", action="store_true", default=False, help="Run with visible browser window")

    # config.json provides defaults; CLI args always win
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            defaults = json.load(f)
        parser.set_defaults(**{k: v for k, v in defaults.items() if k in _KNOWN_CONFIG_KEYS})

    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    venue_config = load_venue_config(args.venue)
    password = get_password()

    request = BookingRequest(
        venue_config=venue_config,
        day=args.day,
        time=args.hour,
        num_sessions=args.num_sessions,
        court=args.court_name,
        backup_court=args.backup_court_name,
        user_email=args.user_email,
    )

    with create_driver(headless=not args.debug_mode) as driver:
        page = SportifiqPage(driver)
        page.login(venue_config.url, args.user_email, password)
        page.select_day(args.day)

        service = BookingService(page)
        results = service.run(request)

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    # Persist successful bookings to Gist (no-op if GIST_TOKEN / GIST_ID not set)
    gist = GistManager(
        token=os.environ.get("GIST_TOKEN"),
        gist_id=os.environ.get("GIST_ID"),
    )
    booked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for r in successes:
        gist.add(Reservation(
            id=uuid.uuid4().hex,
            venue=args.venue,
            date=args.day,
            time=r.time,
            court=r.court,
            booked_at=booked_at,
            status="confirmed",
            site_id=r.site_id,
        ))

    logger.info("Done: %d/%d sessions booked.", len(successes), len(results))
    for r in failures:
        logger.error("Failed: %s at %s — %s", r.court, r.time, r.message)

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
