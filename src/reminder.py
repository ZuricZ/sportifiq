"""Email reminder for upcoming court reservations.

Reads all upcoming reservations from the Gist, finds those due in 2 days that
haven't had a reminder sent yet, and emails the user with Keep/Cancel links.
Also includes a full table of ALL future reservations in every email.

Required env vars (all optional — script exits cleanly if Gist is unconfigured):
  GIST_TOKEN, GIST_ID, CANCEL_SECRET, GMAIL_USER, GMAIL_APP_PASSWORD, GH_PAGES_URL
"""
import argparse
import hashlib
import hmac
import logging
import os
import smtplib
import sys
import time
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.gist_manager import GistManager
from src.models import Reservation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send 2-day-before court booking reminders.")
    parser.add_argument("--user_email", required=True, help="Recipient email address")
    parser.add_argument("--dry_run", action="store_true", default=False,
                        help="Print email body to stdout without sending")
    return parser.parse_args()


def _make_cancel_token(reservation_id: str, secret: str) -> tuple[str, int]:
    """Return (hex_token, expiry_unix_timestamp) valid for 48 hours."""
    exp = int(time.time()) + 48 * 3600
    payload = f"{reservation_id}:{exp}"
    token = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return token, exp


def _cancel_url(res: Reservation, secret: str, pages_url: str) -> str:
    token, exp = _make_cancel_token(res.id, secret)
    base = pages_url.rstrip("/")
    return f"{base}/?id={res.id}&t={token}&exp={exp}"


def _build_upcoming_table(upcoming: list[Reservation]) -> str:
    if not upcoming:
        return "<p><em>No upcoming reservations.</em></p>"
    rows = "".join(
        f"<tr><td>{r.date}</td><td>{r.time}</td><td>{r.court}</td>"
        f"<td>{r.venue}</td><td>{r.status}</td></tr>"
        for r in sorted(upcoming, key=lambda r: (r.date, r.time))
    )
    return (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse'>"
        "<thead><tr><th>Date</th><th>Time</th><th>Court</th><th>Venue</th><th>Status</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _build_email(
    reminder_res: Reservation,
    all_upcoming: list[Reservation],
    cancel_link: str,
) -> tuple[str, str]:
    """Return (subject, html_body)."""
    subject = (
        f"Reminder: court booking {reminder_res.date} "
        f"{reminder_res.time} {reminder_res.court}"
    )
    upcoming_table = _build_upcoming_table(all_upcoming)
    html = f"""
<html><body>
<p>Hi,</p>
<p>You have a court booking in <strong>2 days</strong>:</p>
<ul>
  <li><strong>Date:</strong> {reminder_res.date}</li>
  <li><strong>Time:</strong> {reminder_res.time}</li>
  <li><strong>Court:</strong> {reminder_res.court}</li>
  <li><strong>Venue:</strong> {reminder_res.venue}</li>
</ul>
<p>
  <a href="{cancel_link}"
     style="background:#e74c3c;color:white;padding:10px 20px;text-decoration:none;border-radius:4px">
    Cancel this booking
  </a>
  &nbsp;&nbsp;
  <span style="background:#27ae60;color:white;padding:10px 20px;border-radius:4px">
    Keep it ✓
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

    gist = GistManager(
        token=os.environ.get("GIST_TOKEN"),
        gist_id=os.environ.get("GIST_ID"),
    )

    all_upcoming = gist.all_upcoming()
    if not all_upcoming:
        logger.info("No upcoming confirmed reservations — nothing to do.")
        sys.exit(0)

    target_date = (date.today() + timedelta(days=2)).isoformat()
    to_remind = [r for r in all_upcoming if r.date == target_date and not r.reminder_sent]

    if not to_remind:
        logger.info("No reservations due on %s that need a reminder.", target_date)
        sys.exit(0)

    cancel_secret = os.environ.get("CANCEL_SECRET", "")
    pages_url = os.environ.get("GH_PAGES_URL", "https://example.github.io/sportifiq")

    for res in to_remind:
        link = _cancel_url(res, cancel_secret, pages_url)
        subject, html = _build_email(res, all_upcoming, link)

        if args.dry_run:
            logger.info("=== DRY RUN — would send email ===")
            logger.info("Subject: %s", subject)
            logger.info("Cancel URL: %s", link)
            print(html)
        else:
            _send_email(args.user_email, subject, html)
            logger.info("Reminder sent for reservation %s (%s %s).", res.id, res.date, res.time)
            gist.update(res.id, reminder_sent=True)


if __name__ == "__main__":
    main()
