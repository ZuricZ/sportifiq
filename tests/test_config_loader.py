"""Tests for config_loader.py."""
import os
from unittest.mock import patch

import pytest

from src.libs.config_loader import get_password, load_venue_config


# ---------------------------------------------------------------------------
# load_venue_config
# ---------------------------------------------------------------------------

class TestLoadVenueConfig:
    def test_koseze_loads_correctly(self):
        vc = load_venue_config("koseze")
        assert vc.name == "Koseze"
        assert "tk-cc-koseze.sportifiq.com" in vc.url
        assert "BALON HC1" in vc.courts

    def test_case_insensitive(self):
        vc = load_venue_config("KOSEZE")
        assert vc.name == "Koseze"

    def test_unknown_venue_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown venue"):
            load_venue_config("does_not_exist")

    def test_venue_url_ends_with_location(self):
        vc = load_venue_config("koseze")
        assert vc.url.endswith("/members/location")

    def test_tivoli_loads(self):
        vc = load_venue_config("tivoli")
        assert vc.name == "Tivoli"

    def test_svoboda_loads(self):
        vc = load_venue_config("svoboda")
        assert vc.name == "Svoboda"


# ---------------------------------------------------------------------------
# get_password
# ---------------------------------------------------------------------------

class TestGetPassword:
    def test_returns_env_var_when_set(self):
        with patch.dict(os.environ, {"SPORTIFIQ_PASSWORD": "secret123"}):
            assert get_password() == "secret123"

    def test_missing_env_and_missing_files_raises(self):
        env = {k: v for k, v in os.environ.items() if k != "SPORTIFIQ_PASSWORD"}
        with patch.dict(os.environ, env, clear=True):
            with patch("src.libs.config_loader.Path.read_bytes", side_effect=FileNotFoundError):
                with pytest.raises(FileNotFoundError, match="Password not found"):
                    get_password()
