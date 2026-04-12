import argparse
import logging
import os
import sys

from src.config_loader import get_password, load_venue_config
from src.driver import create_driver
from src.gist_manager import GistManager
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
    parser.add_argument("--reservation_id", required=True, help="Reservation ID from the Gist")
    parser.add_argument("--user_email", required=True, help="Sportifiq account email")
    parser.add_argument("--debug_mode", action="store_true", default=False, help="Run with visible browser window")
    parser.add_argument("--dry_run", action="store_true", default=False, help="Log what would be cancelled without clicking")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    gist = GistManager(
        token=os.environ.get("GIST_TOKEN"),
        gist_id=os.environ.get("GIST_ID"),
    )

    # Look up the reservation in the Gist to confirm it exists
    reservations = gist.load()
    reservation = next((r for r in reservations if r.id == args.reservation_id), None)

    if reservation is None:
        logger.error(
            "Reservation '%s' not found in Gist. "
            "Available IDs: %s",
            args.reservation_id,
            [r.id for r in reservations] or "(none — Gist may not be configured)",
        )
        sys.exit(1)

    if reservation.status == "cancelled":
        logger.warning("Reservation '%s' is already cancelled.", args.reservation_id)
        sys.exit(0)

    logger.info(
        "Reservation to cancel: %s %s %s @ %s (%s)",
        reservation.date,
        reservation.time,
        reservation.court,
        reservation.venue,
        reservation.id,
    )

    if args.dry_run:
        logger.info("Dry run — no browser opened, nothing cancelled.")
        sys.exit(0)

    venue_config = load_venue_config(args.venue)
    password = get_password()

    with create_driver(headless=not args.debug_mode) as driver:
        page = SportifiqPage(driver)
        page.login(venue_config.url, args.user_email, password)
        success = page.cancel_booking(args.reservation_id)

    if success:
        gist.update(args.reservation_id, status="cancelled")
        logger.info("Cancelled reservation %s.", args.reservation_id)
    else:
        logger.error(
            "Could not cancel reservation %s — booking not found on site or already cancelled.",
            args.reservation_id,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
