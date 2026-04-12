import argparse
import logging
import sys

from src.config_loader import get_password, load_venue_config
from src.driver import create_driver
from src.page import SportifiqPage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cancel a Sportifiq reservation.")
    parser.add_argument("--venue", required=True, type=str.lower, help="Venue key (e.g. koseze)")
    parser.add_argument("--site_id", required=True, help="Sportifiq numeric booking ID (from /members/bookings/{id})")
    parser.add_argument("--user_email", required=True, help="Sportifiq account email")
    parser.add_argument("--debug_mode", action="store_true", default=False, help="Run with visible browser window")
    parser.add_argument("--dry_run", action="store_true", default=False, help="Log what would be cancelled without clicking")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    logger.info("Cancelling Sportifiq booking site_id=%s at venue=%s.", args.site_id, args.venue)

    if args.dry_run:
        logger.info("Dry run — no browser opened, nothing cancelled.")
        sys.exit(0)

    venue_config = load_venue_config(args.venue)
    password = get_password()

    with create_driver(headless=not args.debug_mode) as driver:
        page = SportifiqPage(driver)
        page.login(venue_config.url, args.user_email, password)
        success = page.cancel_booking(args.site_id)

    if success:
        logger.info("Cancelled booking site_id=%s.", args.site_id)
    else:
        logger.error(
            "Could not cancel site_id=%s — not found on site or already cancelled.",
            args.site_id,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
