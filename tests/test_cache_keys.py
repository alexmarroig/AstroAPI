from services.cache_keys import build_period, compute_input_hash, normalize_payload

def test_build_period():
    assert build_period("natal") is None
    assert build_period("solar_return", year=2026) == "SR:2026"
    assert build_period("transits", date_yyyy_mm_dd="2026-03-29") == "TR:2026-03-29"

def test_normalize_payload_drops_aliases_and_rounds():
    payload = {
        "birth_date": "1990-01-01",
        "birth_time": "10:30",
        "lat": -23.55051234,
        "lng": -46.63331234,
        "timezone": "America/Sao_Paulo",
        "tz_offset_minutes": -180,
    }
    normalized = normalize_payload(payload)
    assert "birth_date" not in normalized
    assert "birth_time" not in normalized
    assert normalized["lat"] == -23.550512
    assert normalized["lng"] == -46.633312
    assert normalized["timezone"] == "America/Sao_Paulo"
    assert "tz_offset_minutes" not in normalized

def test_compute_input_hash_is_stable():
    payload_a = {"lat": -23.55, "lng": -46.63, "timezone": "America/Sao_Paulo"}
    payload_b = {"lng": -46.6300001, "lat": -23.5500001, "timezone": "America/Sao_Paulo"}
    assert compute_input_hash(payload_a) == compute_input_hash(payload_b)
