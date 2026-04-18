import os
from functools import lru_cache
from pathlib import Path

import yaml
from cryptography.fernet import Fernet

from .models import VenueConfig

_VENUES_FILE = Path("config/venues.yaml")


@lru_cache(maxsize=None)
def _load_venues_data() -> dict:
    with open(_VENUES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


_USERS_FILE = Path("config/users.yaml")


@lru_cache(maxsize=None)
def _load_users_data() -> dict:
    with open(_USERS_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_settings() -> dict:
    """Return the top-level settings block from users.yaml (gh_pages_url etc.)."""
    return _load_users_data().get("settings", {})


def load_user_schedule(user_key: str, venue: str, day: str) -> dict:
    """Return the schedule entry matching user+venue+day.

    Raises ValueError if the combination is not found in users.yaml.
    """
    data = _load_users_data()
    user = data.get("users", {}).get(user_key)
    if not user:
        raise ValueError(f"Unknown user '{user_key}'.")
    for sched in user.get("schedules", []):
        if sched.get("venue", "").lower() == venue.lower() and sched.get("day", "").lower() == day.lower():
            return sched
    raise ValueError(f"No schedule found for user={user_key}, venue={venue}, day={day}.")


def load_venue_config(venue_name: str) -> VenueConfig:
    data = _load_venues_data()
    venues: dict = data.get("venues", {})
    venue_data = venues.get(venue_name.lower())
    if venue_data is None:
        raise ValueError(f"Unknown venue '{venue_name}'. Available: {sorted(venues)}")

    return VenueConfig(
        name=venue_data["name"],
        url=venue_data["url"],
        courts=venue_data.get("courts", []),
        backup_courts=venue_data.get("backup_courts", []),
    )


def get_password() -> str:
    """Return the Sportifiq password.

    Checks SPORTIFIQ_PASSWORD env var first (used in GitHub Actions),
    then falls back to the key.key / password.dat files created by get_pwd.py.
    """
    env_password = os.environ.get("SPORTIFIQ_PASSWORD")
    if env_password:
        return env_password
    return _decrypt_password_from_file()


def _decrypt_password_from_file() -> str:
    try:
        key = Path("key.key").read_bytes()
        encrypted = Path("password.dat").read_bytes()
    except FileNotFoundError:
        raise FileNotFoundError(
            "Password not found. Set the SPORTIFIQ_PASSWORD environment variable "
            "or run get_pwd.py to create key.key / password.dat."
        )
    return Fernet(key).decrypt(encrypted).decode("utf-8")
