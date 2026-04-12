from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VenueConfig:
    name: str
    url: str
    courts: list[str] = field(default_factory=list)
    backup_courts: list[str] = field(default_factory=list)


@dataclass
class BookingRequest:
    venue_config: VenueConfig
    day: str
    time: str  # "HH:MM"
    num_sessions: int
    court: str
    user_email: str
    backup_court: Optional[str] = None


@dataclass
class BookingResult:
    success: bool
    court: str
    time: str
    message: str = ""


@dataclass
class SiteBooking:
    """An upcoming reservation scraped directly from the Sportifiq website."""
    site_id: str       # Sportifiq numeric booking ID (from /members/bookings/{site_id})
    venue: str         # venue key derived from the URL subdomain (e.g. "koseze")
    venue_name: str    # display name as shown on site (e.g. "TKCC - Koseze")
    date: str          # YYYY-MM-DD
    time: str          # "HH:MM - HH:MM" (site format, spaces around dash)
    court: str
