"""Email reminder for upcoming court reservations.

Scrapes upcoming bookings directly from the Sportifiq website (no external
state store needed).  Sends a digest of ALL upcoming reservations, each with
a Cancel link.

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
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.config_loader import get_password, load_settings, load_venue_config
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
    return f"{base}/?id={booking.site_id}&t={token}&exp={exp}&user={user_key}&venue={booking.venue}"


def _build_upcoming_table(upcoming: list[SiteBooking], cancel_links: dict[str, str] | None = None) -> str:
    if not upcoming:
        return "<p style='color:#6b7280;font-style:italic'>No upcoming reservations.</p>"
    today = date.today().isoformat()
    rows = ""
    for i, b in enumerate(upcoming):
        days_out = (date.fromisoformat(b.date) - date.fromisoformat(today)).days
        if days_out == 0:
            days_label, badge_color = "Today", "#dc2626"
        elif days_out == 1:
            days_label, badge_color = "Tomorrow", "#ea580c"
        else:
            days_label, badge_color = f"{days_out}d", "#16a34a"

        border_top = "border-top:1px solid #f3f4f6;" if i > 0 else ""
        cancel_td = ""
        if cancel_links and b.site_id in cancel_links:
            cancel_td = (
                f"<td style='padding:16px 24px 16px 0;text-align:right;vertical-align:middle;white-space:nowrap'>"
                f"<a href='{cancel_links[b.site_id]}' style='color:#dc2626;font-size:13px;font-weight:600;"
                f"text-decoration:none;border:1px solid #fca5a5;padding:5px 14px;border-radius:6px;"
                f"display:inline-block'>Cancel</a></td>"
            )

        rows += f"""
<tr>
  <td style="padding:16px 16px 16px 24px;{border_top}vertical-align:middle;width:52px">
    <span style="display:inline-block;background:{badge_color};color:#fff;font-size:11px;font-weight:700;
    padding:3px 8px;border-radius:6px;letter-spacing:0.03em;white-space:nowrap">{days_label}</span>
  </td>
  <td style="padding:16px 12px;{border_top}vertical-align:middle">
    <div style="font-size:15px;font-weight:600;color:#111827">{b.date} &nbsp;<span style="color:#6b7280;font-weight:400">{b.time}</span></div>
    <div style="font-size:13px;color:#9ca3af;margin-top:3px">{b.court} &middot; {b.venue_name}</div>
  </td>
  {cancel_td}
</tr>"""

    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
  style="border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;background:#ffffff">
  {rows}
</table>"""


def _build_email(
    all_upcoming: list[SiteBooking],
    cancel_links: dict[str, str],
) -> tuple[str, str]:
    """Return (subject, html_body) — digest of all upcoming bookings."""
    n = len(all_upcoming)
    subject = f"🎾 {n} upcoming court booking{'s' if n != 1 else ''}"
    table = _build_upcoming_table(all_upcoming, cancel_links)
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:40px 16px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

        <!-- Header -->
        <tr><td style="background:#1e3a5f;border-radius:12px 12px 0 0;padding:32px 40px;text-align:center">
          <div style="font-size:32px;margin-bottom:8px">🎾</div>
          <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.02em">Court Bookings</h1>
          <p style="margin:8px 0 0;color:#93c5fd;font-size:14px">Your upcoming reservations</p>
        </td></tr>

        <!-- Body -->
        <tr><td style="background:#ffffff;padding:32px 40px">
          <p style="margin:0 0 24px;color:#374151;font-size:15px;line-height:1.6">
            Hi! Here's a summary of your upcoming court bookings.
            Use the <strong style="color:#dc2626">Cancel</strong> button on any booking you'd like to remove.
          </p>
          {table}
          <p style="margin:20px 0 0;color:#9ca3af;font-size:12px">
            ⏱ Cancel links expire in 48 hours.
          </p>
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#f9fafb;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;padding:20px 40px;text-align:center">
          <p style="margin:0;color:#9ca3af;font-size:12px">Sent by Sportifiq Booking Bot</p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
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
        print(html)
    else:
        _send_email(notify_email, subject, html)
        logger.info("Digest sent — %d upcoming booking(s).", len(all_upcoming))


if __name__ == "__main__":
    main()
