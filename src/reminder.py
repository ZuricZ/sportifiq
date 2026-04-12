"""Email reminder for upcoming court reservations.

Scrapes upcoming bookings directly from the Sportifiq website (no external
state store needed).  Finds bookings due in 2 days and emails the user with
Keep / Cancel links.  The full list of ALL upcoming reservations is included
in every email.

Required env vars:
  SPORTIFIQ_PASSWORD   — account password (or use key.key / password.dat)
  CANCEL_SECRET        — HMAC signing secret for cancel tokens
  GMAIL_USER           — sender Gmail address
  GMAIL_APP_PASSWORD   — Gmail App Password
  GH_PAGES_URL         — base URL of the GitHub Pages cancel app
                         (e.g. https://ZuricZ.github.io/sportifiq)
"""
import argparse
import hashlib
import hmac
import json
import logging
import os
import smtplib
import sys
import time
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.config_loader import get_password, load_venue_config
from src.driver import create_driver
from src.models import SiteBooking
from src.page import SportifiqPage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_CONFIG_FILE = Path("config.json")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send 2-day-before court booking reminders.")
    parser.add_argument("--user_email", required=True, help="Sportifiq login email")
    parser.add_argument("--notify_email", default=None,
                        help="Recipient address for reminder emails (defaults to --user_email)")
    parser.add_argument("--user_key", required=True,
                        help="User identifier embedded in cancel links (e.g. ZZ)")
    parser.add_argument("--venue", required=True, type=str.lower, help="Venue key used for login")
    parser.add_argument("--dry_run", action="store_true", default=False,
                        help="Print email body to stdout without sending")
    return parser.parse_args()


def _make_cancel_token(site_id: str, secret: str) -> tuple[str, int]:
    """Return (hex_token, expiry_unix_timestamp) valid for 48 hours."""
    exp = int(time.time()) + 48 * 3600
    payload = f"{site_id}:{exp}"
    token = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return token, exp


def _cancel_url(booking: SiteBooking, secret: str, pages_url: str, user_key: str) -> str:
    token, exp = _make_cancel_token(booking.site_id, secret)
    base = pages_url.rstrip("/")
    return f"{base}/?id={booking.site_id}&t={token}&exp={exp}&user={user_key}"


def _build_upcoming_table(upcoming: list[SiteBooking]) -> str:
    if not upcoming:
        return "<p><em>No upcoming reservations.</em></p>"
    rows = "".join(
        f"<tr><td>{b.date}</td><td>{b.time}</td><td>{b.court}</td>"
        f"<td>{b.venue_name}</td></tr>"
        for b in upcoming
    )
    return (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse'>"
        "<thead><tr><th>Date</th><th>Time</th><th>Court</th><th>Venue</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _build_email(
    reminder: SiteBooking,
    all_upcoming: list[SiteBooking],
    cancel_link: str,
) -> tuple[str, str]:
    """Return (subject, html_body)."""
    subject = f"Reminder: court booking {reminder.date} {reminder.time} {reminder.court}"
    upcoming_table = _build_upcoming_table(all_upcoming)
    html = f"""
<html><body>
<p>Hi,</p>
<p>You have a court booking in <strong>2 days</strong>:</p>
<ul>
  <li><strong>Date:</strong> {reminder.date}</li>
  <li><strong>Time:</strong> {reminder.time}</li>
  <li><strong>Court:</strong> {reminder.court}</li>
  <li><strong>Venue:</strong> {reminder.venue_name}</li>
</ul>
<p>
  <a href="{cancel_link}"
     style="background:#e74c3c;color:white;padding:10px 20px;text-decoration:none;border-radius:4px">
    Cancel this booking
  </a>
  &nbsp;&nbsp;
  <span style="background:#27ae60;color:white;padding:10px 20px;border-radius:4px">
    Keep it &#10003;
  </span>
</p>
<p>The cancel link expires in 48 hours.</p>
<hr>
<h3>All upcoming reservations</h3>
{upcoming_table}
</body></html>
"""
    return subject, html


def _send_email(to_addr: str, subject: str, html_body: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to_addr
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(gmail_user, app_password)
        smtp.sendmail(gmail_user, to_addr, msg.as_string())


def main() -> None:
    args = _parse_args()
    notify_email = args.notify_email or args.user_email

    venue_config = load_venue_config(args.venue)
    password = get_password()

    with create_driver(headless=True) as driver:
        page = SportifiqPage(driver)
        page.login(venue_config.url, args.user_email, password)
        all_upcoming = page.get_upcoming_bookings()

    if not all_upcoming:
        logger.info("No upcoming confirmed reservations — nothing to do.")
        sys.exit(0)

    target_date = (date.today() + timedelta(days=2)).isoformat()
    to_remind = [b for b in all_upcoming if b.date == target_date]

    if not to_remind:
        logger.info("No reservations due on %s.", target_date)
        sys.exit(0)

    cancel_secret = os.environ.get("CANCEL_SECRET", "")
    pages_url = os.environ.get("GH_PAGES_URL", "https://example.github.io/sportifiq")

    for booking in to_remind:
        link = _cancel_url(booking, cancel_secret, pages_url, args.user_key)
        subject, html = _build_email(booking, all_upcoming, link)

        if args.dry_run:
            logger.info("=== DRY RUN — would send email ===")
            logger.info("Subject: %s", subject)
            logger.info("Cancel URL: %s", link)
            logger.info("All upcoming (%d):", len(all_upcoming))
            for b in all_upcoming:
                logger.info("  %s %s %s @ %s (id=%s)", b.date, b.time, b.court, b.venue_name, b.site_id)
            print(html)
        else:
            _send_email(notify_email, subject, html)
            logger.info("Reminder sent for booking %s (%s %s).", booking.site_id, booking.date, booking.time)


if __name__ == "__main__":
    main()
