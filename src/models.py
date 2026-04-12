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
    site_id: str = ""  # Sportifiq booking ID captured from redirect URL


@dataclass
class Reservation:
    id: str           # uuid4 hex (no dashes)
    venue: str        # venue key, e.g. "koseze"
    date: str         # YYYY-MM-DD
    time: str         # HH:MM-HH:MM
    court: str
    booked_at: str    # ISO 8601 UTC, e.g. "2026-04-12T10:00:00Z"
    status: str       # "confirmed" | "cancelled"
    reminder_sent: bool = False
    site_id: str = ""  # Sportifiq numeric booking ID (from /members/bookings/{site_id})
