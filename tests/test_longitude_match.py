from datetime import datetime
from zoneinfo import ZoneInfo

import swisseph as swe

from astro.ephemeris import PLANETS, compute_chart, find_longitude_match
from astro.utils import angle_diff, to_julian_day


def _tz_offset_minutes(dt: datetime, timezone: str) -> int:
    tzinfo = ZoneInfo(timezone)
    offset = dt.replace(tzinfo=tzinfo).utcoffset()
    if offset is None:
        raise ValueError(f"Offset missing for timezone: {timezone}")
    return int(offset.total_seconds() // 60)


def _planet_longitude(utc_dt: datetime, planet_id: int) -> float:
    jd_ut = to_julian_day(utc_dt)
    result, _ = swe.calc_ut(jd_ut, planet_id)
    return result[0] % 360.0


GOLDEN_CASES = [
    {
        "label": "Sao Paulo natal -> London target",
        "planet": "Moon",
        "natal": {
            "dt": datetime(1995, 11, 7, 22, 56, 0),
            "timezone": "America/Sao_Paulo",
            "lat": -23.5505,
            "lng": -46.6333,
        },
        "target": {
            "start": datetime(2026, 1, 26, 0, 0, 0),
            "end": datetime(2026, 1, 28, 23, 59, 59),
            "timezone": "Europe/London",
            "lat": 51.5074,
            "lng": -0.1278,
        },
        "expected": {
            "local_datetime": "2026-01-27T09:53:26",
            "utc_datetime": "2026-01-27T09:53:26",
            "planet_lon": 53.411838,
            "delta_deg": 0.0,
        },
    },
    {
        "label": "Tokyo natal -> New York target",
        "planet": "Moon",
        "natal": {
            "dt": datetime(1988, 5, 23, 5, 15, 0),
            "timezone": "Asia/Tokyo",
            "lat": 35.6762,
            "lng": 139.6503,
        },
        "target": {
            "start": datetime(2025, 9, 17, 0, 0, 0),
            "end": datetime(2025, 9, 19, 23, 59, 59),
            "timezone": "America/New_York",
            "lat": 40.7128,
            "lng": -74.0060,
        },
        "expected": {
            "local_datetime": "2025-09-18T18:39:15",
            "utc_datetime": "2025-09-18T22:39:15",
            "planet_lon": 142.631843,
            "delta_deg": 0.0,
        },
    },
    {
        "label": "Paris natal -> Los Angeles target",
        "planet": "Moon",
        "natal": {
            "dt": datetime(2001, 9, 12, 13, 45, 0),
            "timezone": "Europe/Paris",
            "lat": 48.8566,
            "lng": 2.3522,
        },
        "target": {
            "start": datetime(2024, 2, 18, 0, 0, 0),
            "end": datetime(2024, 2, 20, 23, 59, 59),
            "timezone": "America/Los_Angeles",
            "lat": 34.0522,
            "lng": -118.2437,
        },
        "expected": {
            "local_datetime": "2024-02-19T17:03:39",
            "utc_datetime": "2024-02-20T01:03:39",
            "planet_lon": 101.274828,
            "delta_deg": 0.0,
        },
    },
]


def test_longitude_match_golden_cases():
    for case in GOLDEN_CASES:
        natal = case["natal"]
        target = case["target"]
        planet_name = case["planet"]

        natal_offset = _tz_offset_minutes(natal["dt"], natal["timezone"])
        natal_chart = compute_chart(
            year=natal["dt"].year,
            month=natal["dt"].month,
            day=natal["dt"].day,
            hour=natal["dt"].hour,
            minute=natal["dt"].minute,
            second=natal["dt"].second,
            lat=natal["lat"],
            lng=natal["lng"],
            tz_offset_minutes=natal_offset,
        )
        target_lon = natal_chart["planets"][planet_name]["lon"]

        target_offset = _tz_offset_minutes(target["start"], target["timezone"])
        result = find_longitude_match(
            planet_id=PLANETS[planet_name],
            target_lon=target_lon,
            start_local=target["start"],
            end_local=target["end"],
            tz_offset_minutes=target_offset,
            tolerance_deg=0.1,
            step_minutes=60,
            refine_steps=14,
        )

        assert result == case["expected"], case["label"]


def test_longitude_match_within_tolerance():
    case = GOLDEN_CASES[0]
    natal = case["natal"]
    target = case["target"]

    natal_offset = _tz_offset_minutes(natal["dt"], natal["timezone"])
    natal_chart = compute_chart(
        year=natal["dt"].year,
        month=natal["dt"].month,
        day=natal["dt"].day,
        hour=natal["dt"].hour,
        minute=natal["dt"].minute,
        second=natal["dt"].second,
        lat=natal["lat"],
        lng=natal["lng"],
        tz_offset_minutes=natal_offset,
    )
    target_lon = natal_chart["planets"]["Moon"]["lon"]

    target_offset = _tz_offset_minutes(target["start"], target["timezone"])
    result = find_longitude_match(
        planet_id=PLANETS["Moon"],
        target_lon=target_lon,
        start_local=target["start"],
        end_local=target["end"],
        tz_offset_minutes=target_offset,
        tolerance_deg=0.1,
        step_minutes=60,
        refine_steps=14,
    )

    utc_dt = datetime.fromisoformat(result["utc_datetime"])
    lon = _planet_longitude(utc_dt, PLANETS["Moon"])
    delta = angle_diff(lon, target_lon)
    assert delta < 0.1
