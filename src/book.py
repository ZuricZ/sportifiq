"""CLI runner — book a court."""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from src.libs.booking_service import book
from src.libs.config_loader import load_venue_config
from src.libs.log import setup
from src.libs.models import BookingRequest
from src.libs.session import sportifiq_session

setup()
logger = logging.getLogger(__name__)

_CONFIG_FILE = Path("config.json")
_KNOWN_CONFIG_KEYS = {"venue", "day", "hour", "num_sessions", "court_name", "backup_court_name", "user_email", "debug_mode", "execution_time"}
_LOGIN_URL = "https://sportifiq.com/user_sessions/new"
_FAILSAFE_SECONDS = 90 * 60


def _sleep_until_server_time(target_time_str: str) -> None:
    response = requests.head(_LOGIN_URL, timeout=10)
    server_time_str = response.headers["Date"]
    gmt_time = datetime.strptime(server_time_str, "%a, %d %b %Y %H:%M:%S GMT")
    gmt_time = gmt_time.replace(tzinfo=ZoneInfo("UTC"))
    server_time = gmt_time.astimezone(ZoneInfo("Europe/Berlin"))
    hour, minute = map(int, target_time_str.split(":"))
    target = server_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
    sleep_secs = (target - server_time).total_seconds()
    if sleep_secs <= 0:
        logger.warning("execution_time %s is already past (server: %s). Proceeding immediately.", target_time_str, server_time.strftime("%H:%M:%S"))
        return
    sleep_secs = min(sleep_secs, _FAILSAFE_SECONDS)
    logger.info("Server time %s — sleeping %.0fs until %s.", server_time.strftime("%H:%M:%S"), sleep_secs, target_time_str)
    time.sleep(sleep_secs)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Book a court on Sportifiq.")
    parser.add_argument("--venue", required=True, type=str.lower)
    parser.add_argument("--day", required=True)
    parser.add_argument("--hour", required=True)
    parser.add_argument("--num_sessions", required=True, type=int)
    parser.add_argument("--court_name", required=True)
    parser.add_argument("--backup_court_name", default=None)
    parser.add_argument("--user_email", required=True)
    parser.add_argument("--execution_time", default=None)
    parser.add_argument("--debug_mode", action="store_true", default=False)
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            defaults = json.load(f)
        parser.set_defaults(**{k: v for k, v in defaults.items() if k in _KNOWN_CONFIG_KEYS})
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if os.environ.get("DRY_RUN", "").lower() in ("true", "1"):
        logger.info(
            "DRY RUN — would book: venue=%s day=%s hour=%s court=%s backup=%s user=%s",
            args.venue, args.day, args.hour, args.court_name, args.backup_court_name, args.user_email,
        )
        return

    if args.execution_time:
        _sleep_until_server_time(args.execution_time)

    venue_config = load_venue_config(args.venue)
    request = BookingRequest(
        venue_config=venue_config,
        day=args.day,
        time=args.hour,
        num_sessions=args.num_sessions,
        court=args.court_name,
        backup_court=args.backup_court_name,
        user_email=args.user_email,
    )

    with sportifiq_session(args.venue, args.user_email, headless=not args.debug_mode) as page:
        page.select_day(args.day)
        results = book(page, request)

    failures = [r for r in results if not r.success]
    logger.info("Done: %d/%d sessions booked.", len(results) - len(failures), len(results))
    for r in failures:
        logger.error("Failed: %s at %s — %s", r.court, r.time, r.message)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
