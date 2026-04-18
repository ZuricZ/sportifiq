"""CLI runner — cancel a Sportifiq reservation."""
import argparse
import logging
import sys

from src.libs.log import setup
from src.libs.session import sportifiq_session

setup()
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cancel a Sportifiq reservation.")
    parser.add_argument("--venue", required=True, type=str.lower)
    parser.add_argument("--site_id", required=True)
    parser.add_argument("--user_email", required=True)
    parser.add_argument("--debug_mode", action="store_true", default=False)
    parser.add_argument("--dry_run", action="store_true", default=False)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    logger.info("Cancelling Sportifiq booking site_id=%s at venue=%s.", args.site_id, args.venue)

    if args.dry_run:
        logger.info("Dry run — no browser opened, nothing cancelled.")
        sys.exit(0)

    with sportifiq_session(args.venue, args.user_email, headless=not args.debug_mode) as page:
        success = page.cancel_booking(args.site_id)

    if success:
        logger.info("Cancelled booking site_id=%s.", args.site_id)
    else:
        logger.error("Could not cancel site_id=%s — not found or already cancelled.", args.site_id)
        sys.exit(1)


if __name__ == "__main__":
    main()
