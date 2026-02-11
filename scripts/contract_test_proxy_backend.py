#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("API_KEY", "test-api-key")

from main import app  # noqa: E402

ALLOWED_PREFIXES = (
    "/v1/chart/",
    "/v1/interpretation/",
    "/v1/ai/",
    "/v1/cosmic-weather",
    "/v1/time/",
    "/v1/solar-return/",
)


@dataclass
class Envelope:
    path: str
    method: str
    body: dict[str, Any] | None = None
    query: dict[str, Any] | None = None


def normalize_render_data_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    for field in ("year", "month", "day", "hour", "minute", "second"):
        natal_field = f"natal_{field}"
        if field not in normalized and natal_field in payload:
            normalized[field] = payload[natal_field]
        normalized.pop(natal_field, None)
    return normalized


def simulate_proxy_to_backend(
    client: TestClient,
    envelope: Envelope,
    *,
    authorization: str = "Bearer test-api-key",
    x_user_id: str | None = "contract-test-user",
):
def simulate_proxy_to_backend(client: TestClient, envelope: Envelope):
    path = envelope.path
    if not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        raise AssertionError(f"Path bloqueado pelo proxy: {path}")

    body = dict(envelope.body or {})
    if path == "/v1/chart/render-data":
        body = normalize_render_data_payload(body)

    headers: dict[str, str] = {
        "Authorization": authorization,
        "Content-Type": "application/json",
    }
    if x_user_id is not None:
        headers["X-User-Id"] = x_user_id
    headers = {
        "Authorization": "Bearer test-api-key",
        "X-User-Id": "contract-test-user",
        "Content-Type": "application/json",
    }

    return client.request(
        envelope.method.upper(),
        path,
        headers=headers,
        params=envelope.query or None,
        json=body if envelope.method.upper() not in {"GET", "HEAD"} else None,
    )


def assert_has_keys(payload: dict[str, Any], keys: list[str], endpoint: str) -> None:
    missing = [key for key in keys if key not in payload]
    if missing:
        raise AssertionError(f"{endpoint} sem campos essenciais: {missing}; payload={json.dumps(payload)[:500]}")


def run_contract_cases(client: TestClient) -> None:
    test_cases = [
        # timezone camelCase
        Envelope("/v1/time/resolve-tz", "POST", {"datetimeLocal": "1990-09-15T10:30:00", "timezone": "America/Sao_Paulo", "strictBirth": False, "preferFold": 0}),
        # render-data with natal_* (proxy normalization)
def main() -> None:
    client = TestClient(app)

    test_cases = [
        Envelope("/v1/time/resolve-tz", "POST", {"year": 1990, "month": 9, "day": 15, "hour": 10, "minute": 30, "timezone": "America/Sao_Paulo"}),
        Envelope("/v1/chart/render-data", "POST", {
            "natal_year": 1990,
            "natal_month": 9,
            "natal_day": 15,
            "natal_hour": 10,
            "natal_minute": 30,
            "lat": -23.5505,
            "lng": -46.6333,
            "timezone": "America/Sao_Paulo",
        }),
        # interpretation with camelCase birth
        Envelope("/v1/interpretation/natal", "POST", {
            "birthDate": "1990-09-15",
            "birthTime": "10:30",
            "lat": -23.5505,
            "lng": -46.6333,
            "timezone": "America/Sao_Paulo",
        }),
        # interpretation with snake_case birth
        Envelope("/v1/interpretation/natal", "POST", {
            "birth_date": "1990-09-15",
            "birth_time": "10:30:00",
            "lat": -23.5505,
            "lng": -46.6333,
            "timezone": "America/Sao_Paulo",
        }),
        # interpretation with numeric components only
        Envelope("/v1/interpretation/natal", "POST", {
            "year": 1990,
            "month": 9,
            "day": 15,
            "hour": 10,
            "minute": 30,
            "lat": -23.5505,
            "lng": -46.6333,
            "timezone": "America/Sao_Paulo",
        }),
        Envelope("/v1/ai/cosmic-chat", "POST", {
            "userQuestion": "Me dá um resumo curto do momento atual.",
            "astroPayload": {"sun": "Virgo", "moon": "Aries"},
            "language": "pt-BR",
        }),
        Envelope("/v1/ai/cosmic-chat", "POST", {
            "user_question": "Resumo objetivo por favor.",
            "astro_payload": {"sun": "Virgo", "moon": "Aries"},
            "language": "pt-BR",
        }),
        Envelope("/v1/solar-return/calculate", "POST", {
            "natal": {
                "data": "1990-09-15",
                "hora": "10:30:00",
                "timezone": "America/Sao_Paulo",
                "local": {"lat": -23.5505, "lon": -46.6333},
            },
            "alvo": {
                "ano": 2026,
                "timezone": "America/Sao_Paulo",
                "local": {"lat": -23.5505, "lon": -46.6333},
            },
        }),
        Envelope("/v1/solar-return/timeline", "POST", {
            "natal": {
                "data": "1990-09-15",
                "hora": "10:30:00",
                "timezone": "America/Sao_Paulo",
                "local": {"lat": -23.5505, "lon": -46.6333},
            },
            "year": 2026,
        }),
        Envelope("/v1/cosmic-weather/range", "GET", query={"from": "2026-01-01", "to": "2026-01-03", "timezone": "America/Sao_Paulo"}),
    ]

    for case in test_cases:
        response = simulate_proxy_to_backend(client, case)
        endpoint_label = f"{case.method} {case.path}"

        if case.path == "/v1/ai/cosmic-chat":
            if response.status_code == 503:
                assert_has_keys(response.json(), ["ok", "error", "detail"], endpoint_label)
                continue
            if response.status_code != 200:
                raise AssertionError(f"{endpoint_label} retornou {response.status_code}: {response.text}")
            assert_has_keys(response.json(), ["response", "usage"], endpoint_label)
            continue

        if response.status_code != 200:
            raise AssertionError(f"{endpoint_label} retornou {response.status_code}: {response.text}")

        payload = response.json()
        if case.path == "/v1/time/resolve-tz":
            assert_has_keys(payload, ["tz_offset_minutes", "metadados_tecnicos"], endpoint_label)
        elif case.path == "/v1/chart/render-data":
            assert_has_keys(payload, ["zodiac", "houses", "planets"], endpoint_label)
        elif case.path == "/v1/interpretation/natal":
            assert_has_keys(payload, ["titulo", "sintese", "summary"], endpoint_label)
        elif case.path == "/v1/solar-return/calculate":
            assert_has_keys(payload, ["mapa_revolucao", "metadados_tecnicos"], endpoint_label)
        elif case.path == "/v1/solar-return/timeline":
            assert_has_keys(payload, ["year_timeline", "metadados"], endpoint_label)
        elif case.path == "/v1/cosmic-weather/range":
            assert_has_keys(payload, ["from", "to", "items"], endpoint_label)


def run_auth_cases(client: TestClient) -> None:
    protected = Envelope("/v1/chart/render-data", "POST", {
        "year": 1990,
        "month": 9,
        "day": 15,
        "hour": 10,
        "minute": 30,
        "lat": -23.5505,
        "lng": -46.6333,
        "timezone": "America/Sao_Paulo",
    })

    invalid_token = simulate_proxy_to_backend(client, protected, authorization="Bearer wrong")
    if invalid_token.status_code != 401:
        raise AssertionError(f"Auth inválida deveria retornar 401, veio {invalid_token.status_code}: {invalid_token.text}")

    missing_user = simulate_proxy_to_backend(client, protected, x_user_id=None)
    if missing_user.status_code not in (401, 403):
        raise AssertionError(f"X-User-Id ausente deveria retornar 401/403, veio {missing_user.status_code}: {missing_user.text}")


def main() -> None:
    client = TestClient(app)
    run_contract_cases(client)
    run_auth_cases(client)
    print("Contract tests passed.")


if __name__ == "__main__":
    main()
