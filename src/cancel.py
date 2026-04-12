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
    parser.add_argument("--reservation_id", required=True, help="Reservation UUID from the Gist")
    parser.add_argument(
        "--site_id",
        default=None,
        help=(
            "Sportifiq numeric booking ID (from the site URL). "
            "Required when Gist is not configured or the booking pre-dates Gist tracking."
        ),
    )
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

    # Resolve the Sportifiq site booking ID.
    # Priority: explicit --site_id > Gist lookup > fail.
    site_booking_id = args.site_id
    gist_reservation = None

    if not site_booking_id:
        reservations = gist.load()
        gist_reservation = next((r for r in reservations if r.id == args.reservation_id), None)

        if gist_reservation is None:
            logger.error(
                "Reservation '%s' not found in Gist and --site_id was not provided. "
                "Pass --site_id <numeric_id> (from the Sportifiq booking URL) to cancel directly.",
                args.reservation_id,
            )
            sys.exit(1)

        if gist_reservation.status == "cancelled":
            logger.warning("Reservation '%s' is already cancelled.", args.reservation_id)
            sys.exit(0)

        if not gist_reservation.site_id:
            logger.error(
                "Reservation '%s' has no site_id stored in Gist. "
                "Pass --site_id <numeric_id> manually.",
                args.reservation_id,
            )
            sys.exit(1)

        site_booking_id = gist_reservation.site_id

    if gist_reservation:
        logger.info(
            "Cancelling: %s %s %s @ %s (Gist id=%s, site_id=%s)",
            gist_reservation.date,
            gist_reservation.time,
            gist_reservation.court,
            gist_reservation.venue,
            gist_reservation.id,
            site_booking_id,
        )
    else:
        logger.info("Cancelling site booking id=%s (no Gist record).", site_booking_id)

    if args.dry_run:
        logger.info("Dry run — no browser opened, nothing cancelled.")
        sys.exit(0)

    venue_config = load_venue_config(args.venue)
    password = get_password()

    with create_driver(headless=not args.debug_mode) as driver:
        page = SportifiqPage(driver)
        page.login(venue_config.url, args.user_email, password)
        success = page.cancel_booking(site_booking_id)

    if success:
        if gist_reservation:
            gist.update(args.reservation_id, status="cancelled")
        logger.info("Cancelled booking site_id=%s.", site_booking_id)
    else:
        logger.error(
            "Could not cancel site_id=%s — not found on site or already cancelled.",
            site_booking_id,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
