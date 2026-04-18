from src.libs.models import BookingResult, SiteBooking, VenueConfig, BookingRequest


def test_booking_result_defaults():
    r = BookingResult(success=True, court="BALON HC1", time="13:00-14:00")
    assert r.message == ""


def test_booking_result_failure():
    r = BookingResult(success=False, court="BALON HC1", time="13:00-14:00", message="Slot unavailable")
    assert not r.success
    assert r.message == "Slot unavailable"


def test_site_booking_fields():
    b = SiteBooking(
        site_id="11300768",
        venue="koseze",
        venue_name="TKCC - Koseze",
        date="2026-04-17",
        time="19:00 - 20:00",
        court="BALON HC1",
    )
    assert b.site_id == "11300768"
    assert b.venue == "koseze"
    assert b.date == "2026-04-17"


def test_venue_config_defaults():
    vc = VenueConfig(name="Test", url="https://test.sportifiq.com/members/location")
    assert vc.courts == []
    assert vc.backup_courts == []


def test_booking_request_optional_backup():
    vc = VenueConfig(name="Koseze", url="https://tk-cc-koseze.sportifiq.com/members/location",
                     courts=["BALON HC1"])
    req = BookingRequest(
        venue_config=vc,
        day="2026-04-19",
        time="13:00",
        num_sessions=1,
        court="BALON HC1",
        user_email="user@example.com",
    )
    assert req.backup_court is None
