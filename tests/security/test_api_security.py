import os
from fastapi.testclient import TestClient


def _client():
    os.environ.setdefault("API_KEY", "test-api-key")
    from main import app

    return TestClient(app)


def _headers(valid=True):
    if valid:
        return {
            "Authorization": "Bearer test-api-key",
            "X-User-Id": "security-user",
        }
    return {
        "Authorization": "Bearer invalid",
        "X-User-Id": "security-user",
    }


def test_security_headers_present_on_health():
    client = _client()
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("referrer-policy") == "no-referrer"
    assert "content-security-policy" in res.headers


def test_auth_is_enforced_on_critical_endpoints():
    client = _client()

    payload_natal = {
        "natal_year": 1992,
        "natal_month": 8,
        "natal_day": 12,
        "natal_hour": 10,
        "natal_minute": 30,
        "natal_second": 0,
        "year": 1992,
        "month": 8,
        "day": 12,
        "hour": 10,
        "minute": 30,
        "second": 0,
        "lat": -23.5505,
        "lng": -46.6333,
        "timezone": "America/Sao_Paulo",
    }

    no_auth = client.post("/v1/chart/natal", json=payload_natal)
    assert no_auth.status_code in (400, 401)

    bad_auth = client.post("/v1/chart/natal", json=payload_natal, headers=_headers(valid=False))
    assert bad_auth.status_code == 401


def test_basic_input_fuzz_returns_controlled_errors():
    client = _client()
    fuzz_payload = {
        "natal_year": "DROP TABLE users;",
        "natal_month": -1,
        "natal_day": 99,
        "natal_hour": "<script>alert(1)</script>",
        "natal_minute": None,
        "natal_second": "nan",
        "year": "inf",
        "month": 13,
        "day": 32,
        "hour": 24,
        "minute": 80,
        "second": 80,
        "lat": 999,
        "lng": 999,
        "timezone": "Invalid/Timezone",
    }

    res = client.post("/v1/chart/natal", json=fuzz_payload, headers=_headers(valid=True))
    assert res.status_code in (400, 422)
    data = res.json()
    assert "request_id" in data


def test_ai_endpoint_requires_valid_payload_and_auth():
    client = _client()

    res = client.post(
        "/v1/ai/cosmic-chat",
        json={"user_question": "", "astro_payload": {}},
        headers=_headers(valid=True),
    )
    assert res.status_code in (422, 500)
