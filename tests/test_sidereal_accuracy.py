from astro.ephemeris import compute_chart


def test_sidereal_chart_uses_distinct_longitudes():
    tropical = compute_chart(
        year=2024,
        month=3,
        day=20,
        hour=12,
        minute=0,
        second=0,
        lat=0.0,
        lng=0.0,
        tz_offset_minutes=0,
        zodiac_type="tropical",
    )
    sidereal = compute_chart(
        year=2024,
        month=3,
        day=20,
        hour=12,
        minute=0,
        second=0,
        lat=0.0,
        lng=0.0,
        tz_offset_minutes=0,
        zodiac_type="sidereal",
        ayanamsa="lahiri",
    )

    sun_delta = (tropical["planets"]["Sun"]["lon"] - sidereal["planets"]["Sun"]["lon"]) % 360
    assert 20 < sun_delta < 30


def test_tropical_result_remains_stable_after_sidereal_call():
    baseline = compute_chart(
        year=2024,
        month=8,
        day=15,
        hour=6,
        minute=30,
        second=0,
        lat=-23.55,
        lng=-46.63,
        tz_offset_minutes=-180,
        zodiac_type="tropical",
    )

    compute_chart(
        year=2024,
        month=8,
        day=15,
        hour=6,
        minute=30,
        second=0,
        lat=-23.55,
        lng=-46.63,
        tz_offset_minutes=-180,
        zodiac_type="sidereal",
        ayanamsa="lahiri",
    )

    recalculated = compute_chart(
        year=2024,
        month=8,
        day=15,
        hour=6,
        minute=30,
        second=0,
        lat=-23.55,
        lng=-46.63,
        tz_offset_minutes=-180,
        zodiac_type="tropical",
    )

    assert recalculated["planets"]["Sun"]["lon"] == baseline["planets"]["Sun"]["lon"]
    assert recalculated["houses"]["asc"] == baseline["houses"]["asc"]
