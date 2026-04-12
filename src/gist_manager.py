"""GitHub Gist persistence layer for reservation state.

If GIST_TOKEN or GIST_ID is absent every method is a silent no-op so the
booking workflow runs unchanged without any credentials configured.
"""
import json
import logging
from dataclasses import asdict
from datetime import date
from typing import Optional
from urllib import request as urllib_request
from urllib.error import HTTPError

from .models import Reservation

logger = logging.getLogger(__name__)

_GIST_FILENAME = "reservations.json"
_API_BASE = "https://api.github.com"


class GistManager:
    def __init__(self, token: Optional[str], gist_id: Optional[str]) -> None:
        self._token = token
        self._gist_id = gist_id
        self._enabled = bool(token and gist_id)

    # --- Public interface ---

    def load(self) -> list[Reservation]:
        if not self._enabled:
            return []
        try:
            data = self._api_get(f"/gists/{self._gist_id}")
            raw = data["files"][_GIST_FILENAME]["content"]
            records = json.loads(raw)
            return [Reservation(**r) for r in records]
        except Exception as exc:
            logger.warning("GistManager.load failed: %s", exc)
            return []

    def save(self, reservations: list[Reservation]) -> None:
        if not self._enabled:
            return
        payload = json.dumps([asdict(r) for r in reservations], indent=2)
        try:
            self._api_patch(
                f"/gists/{self._gist_id}",
                {"files": {_GIST_FILENAME: {"content": payload}}},
            )
        except Exception as exc:
            logger.warning("GistManager.save failed: %s", exc)

    def add(self, reservation: Reservation) -> None:
        if not self._enabled:
            return
        reservations = self.load()
        reservations.append(reservation)
        self.save(reservations)

    def update(self, reservation_id: str, **fields) -> None:
        if not self._enabled:
            return
        reservations = self.load()
        for r in reservations:
            if r.id == reservation_id:
                for k, v in fields.items():
                    setattr(r, k, v)
        self.save(reservations)

    def all_upcoming(self) -> list[Reservation]:
        if not self._enabled:
            return []
        today = date.today().isoformat()
        return [
            r for r in self.load()
            if r.status == "confirmed" and r.date >= today
        ]

    # --- Private helpers ---

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

    def _api_get(self, path: str) -> dict:
        req = urllib_request.Request(
            f"{_API_BASE}{path}",
            headers=self._headers(),
        )
        with urllib_request.urlopen(req) as resp:
            return json.loads(resp.read())

    def _api_patch(self, path: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        req = urllib_request.Request(
            f"{_API_BASE}{path}",
            data=data,
            headers=self._headers(),
            method="PATCH",
        )
        with urllib_request.urlopen(req) as resp:
            return json.loads(resp.read())
