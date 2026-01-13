import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from astro.ephemeris import solar_return_datetime, sun_longitude_at
from astro.solar_return import compute_natal_sun_longitude, compute_solar_return_reference
from astro.utils import angle_diff

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_jsonl(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _tz_offset_minutes(dt: datetime, timezone: str) -> int:
    tzinfo = ZoneInfo(timezone)
    offset = dt.replace(tzinfo=tzinfo).utcoffset()
    if offset is None:
        raise ValueError(f"Offset missing for timezone: {timezone}")
    return int(offset.total_seconds() // 60)


def test_solar_return_reference_longitude_matches_natal():
    cases = _load_jsonl(FIXTURES_DIR / "solar_return_reference.jsonl")
    for case in cases:
        natal = case["natal"]
        expected = case["expected"]
        natal_dt = datetime.fromisoformat(f"{natal['date']}T{natal['time']}")
        offset = _tz_offset_minutes(natal_dt, natal["timezone"])

        reference = compute_solar_return_reference(
            natal_dt=natal_dt,
            target_year=case["target"]["year"],
            tz_offset_minutes=offset,
            engine="v2",
        )

        delta = abs(angle_diff(reference["solar_return_sun_lon"], reference["natal_sun_lon"]))
        assert delta <= expected["tolerance_deg"], case


def test_solar_return_reference_utc_matches():
    cases = _load_jsonl(FIXTURES_DIR / "solar_return_reference.jsonl")
    for case in cases:
        natal = case["natal"]
        expected = case["expected"]
        natal_dt = datetime.fromisoformat(f"{natal['date']}T{natal['time']}")
        offset = _tz_offset_minutes(natal_dt, natal["timezone"])

        solar_return_utc = solar_return_datetime(
            natal_dt=natal_dt,
            target_year=case["target"]["year"],
            tz_offset_minutes=offset,
            engine="v2",
        )

        assert solar_return_utc.isoformat() == expected["utc"], case


def test_natal_reference_sun_longitude():
    cases = _load_jsonl(FIXTURES_DIR / "natal_reference.jsonl")
    for case in cases:
        natal = case["natal"]
        expected = case["expected"]
        natal_dt = datetime.fromisoformat(f"{natal['date']}T{natal['time']}")
        offset = _tz_offset_minutes(natal_dt, natal["timezone"])

        result = compute_natal_sun_longitude(
            year=natal_dt.year,
            month=natal_dt.month,
            day=natal_dt.day,
            hour=natal_dt.hour,
            minute=natal_dt.minute,
            second=natal_dt.second,
            tz_offset_minutes=offset,
        )

        assert result["utc_datetime"] == expected["utc"], case
        assert abs(result["sun_lon"] - expected["sun_lon"]) <= expected["tolerance_deg"], case


def test_return_sun_longitude_matches_expected_fixture():
    cases = _load_jsonl(FIXTURES_DIR / "solar_return_reference.jsonl")
    for case in cases:
        natal = case["natal"]
        expected = case["expected"]
        natal_dt = datetime.fromisoformat(f"{natal['date']}T{natal['time']}")
        offset = _tz_offset_minutes(natal_dt, natal["timezone"])

        solar_return_utc = solar_return_datetime(
            natal_dt=natal_dt,
            target_year=case["target"]["year"],
            tz_offset_minutes=offset,
            engine="v2",
        )
        sun_lon = round(sun_longitude_at(solar_return_utc), 6)

        assert abs(sun_lon - expected["sun_lon"]) <= expected["tolerance_deg"], case
