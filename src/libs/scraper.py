"""Pure parsing utilities — zero I/O, no Selenium."""
import re
from datetime import date, datetime
from typing import Optional

from .models import SiteBooking

SLO_MONTHS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
    "jul": 7, "avg": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def fmt_time(t: datetime) -> str:
    """Format a datetime as H:MM (no leading zero on the hour)."""
    return f"{t.hour}:{t.strftime('%M')}"


def parse_slo_date(raw: str) -> Optional[str]:
    """Convert Slovenian date string ("17. apr") to ISO "YYYY-MM-DD".

    Returns None on bad input. If the date is in the past, assumes next year.
    """
    raw = re.sub(r"[,.\s]+$", "", raw.strip())
    parts = raw.split()
    if len(parts) < 2:
        return None
    try:
        day = int(parts[0].rstrip("."))
    except ValueError:
        return None
    month = SLO_MONTHS.get(parts[1].lower()[:3])
    if not month:
        return None
    today = date.today()
    candidate = date(today.year, month, day)
    if candidate < today:
        candidate = date(today.year + 1, month, day)
    return candidate.isoformat()


def parse_booking_data(
    href: str,
    venue_name: str,
    court: str,
    time_str: str,
    raw_date: str,
) -> Optional[SiteBooking]:
    """Parse raw strings extracted from a booking card into a SiteBooking.

    Returns None if the href has no valid booking ID or the date is unparseable.
    """
    m = re.search(r"/members/bookings/(\d+)", href)
    if not m:
        return None
    site_id = m.group(1)

    subdomain_m = re.match(r"https?://([^.]+)\.sportifiq\.com", href)
    venue_subdomain = subdomain_m.group(1) if subdomain_m else ""
    venue_key = venue_subdomain.split("-")[-1] if venue_subdomain else ""

    iso_date = parse_slo_date(raw_date)
    if not iso_date:
        return None

    return SiteBooking(
        site_id=site_id,
        venue=venue_key,
        venue_name=venue_name,
        date=iso_date,
        time=time_str,
        court=court,
    )
