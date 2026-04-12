import os
from functools import lru_cache
from pathlib import Path

import yaml
from cryptography.fernet import Fernet

from .models import VenueConfig

_VENUES_FILE = Path(__file__).parent.parent / "config" / "venues.yaml"


@lru_cache(maxsize=None)
def _load_venues_data() -> dict:
    with open(_VENUES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
