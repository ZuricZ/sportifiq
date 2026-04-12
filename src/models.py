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
