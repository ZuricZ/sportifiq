"""CLI runner — send upcoming booking reminder emails."""
import argparse
import hashlib
import hmac
import logging
import os
import smtplib
import sys
import time
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader

from src.libs.config_loader import load_settings
from src.libs.log import setup
from src.libs.models import SiteBooking
from src.libs.session import sportifiq_session

setup()
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send upcoming court booking reminders.")
    parser.add_argument("--user_email", required=True)
    parser.add_argument("--notify_emails", default=None, help="Comma-separated list of email addresses")
    parser.add_argument("--user_key", required=True)
    parser.add_argument("--venue", required=True, type=str.lower)
    parser.add_argument("--dry_run", action="store_true", default=False)
    return parser.parse_args()


def _make_cancel_token(site_id: str, secret: str) -> tuple[str, int]:
    exp = int(time.time()) + 48 * 3600
    payload = f"{site_id}:{exp}"
    token = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return token, exp


def _cancel_url(booking: SiteBooking, secret: str, pages_url: str, user_key: str) -> str:
    token, exp = _make_cancel_token(booking.site_id, secret)
    base = pages_url.rstrip("/")
    return f"{base}/?id={booking.site_id}&t={token}&exp={exp}&user={user_key}&venue={booking.venue}"


def _build_email(
    all_upcoming: list[SiteBooking],
    cancel_links: dict[str, str],
) -> tuple[str, str]:
    today = date.today().isoformat()
    rows = []
    for b in all_upcoming:
        days_out = (date.fromisoformat(b.date) - date.fromisoformat(today)).days
        if days_out == 0:
            days_label, badge_color = "Today", "#dc2626"
        elif days_out == 1:
            days_label, badge_color = "Tomorrow", "#ea580c"
        else:
            days_label, badge_color = f"{days_out}d", "#16a34a"
        rows.append({
            "booking": b,
            "days_label": days_label,
            "badge_color": badge_color,
            "cancel_url": cancel_links.get(b.site_id),
        })
    n = len(all_upcoming)
    subject = f"🎾 {n} upcoming court booking{'s' if n != 1 else ''}"
    env = Environment(loader=FileSystemLoader("src/templates"), autoescape=False)
    html = env.get_template("reminder_email.html").render(rows=rows)
    return subject, html


def _send_email(recipients: list[str], subject: str, html_body: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(gmail_user, app_password)
        smtp.sendmail(gmail_user, recipients, msg.as_string())


def main() -> None:
    args = _parse_args()
    if args.notify_emails:
        notify_recipients = [e.strip() for e in args.notify_emails.split(",") if e.strip()]
    else:
        notify_recipients = [args.user_email]

    with sportifiq_session(args.venue, args.user_email) as page:
        all_upcoming = page.get_upcoming_bookings()

    if not all_upcoming:
        logger.info("No upcoming confirmed reservations — nothing to do.")
        sys.exit(0)

    cancel_secret = os.environ.get("CANCEL_SECRET", "")
    pages_url = os.environ.get("GH_PAGES_URL") or load_settings().get("gh_pages_url", "")

    cancel_links = {
        b.site_id: _cancel_url(b, cancel_secret, pages_url, args.user_key)
        for b in all_upcoming
    }
    subject, html = _build_email(all_upcoming, cancel_links)

    if args.dry_run:
        logger.info("=== DRY RUN — would send email ===")
        logger.info("Subject: %s", subject)
        for b in all_upcoming:
            logger.info("  %s %s %s @ %s (id=%s) cancel=%s",
                        b.date, b.time, b.court, b.venue_name, b.site_id, cancel_links[b.site_id])
    else:
        _send_email(notify_recipients, subject, html)
        logger.info("Digest sent to %s — %d upcoming booking(s).",
                     ", ".join(notify_recipients), len(all_upcoming))


if __name__ == "__main__":
    main()
