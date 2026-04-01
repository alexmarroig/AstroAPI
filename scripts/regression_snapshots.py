import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


# =========================
# CONFIG
# =========================

HEALTH_ENDPOINT = "/health"
MAX_WAIT_SECONDS = 30
RETRY_INTERVAL = 1.5


# =========================
# MODELS
# =========================

@dataclass(frozen=True)
class Case:
    name: str
    method: str
    path: str
    payload: Dict[str, Any]


# =========================
# UTILS
# =========================

def _resolve_api_key(value: str | None) -> str:
    if value and value.strip():
        return value.strip()

    env_key = os.getenv("API_KEY") or os.getenv("ASTRO_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    raise SystemExit("Missing API key. Use --api-key or set API_KEY/ASTRO_API_KEY.")


def wait_for_api(base_url: str) -> None:
    print("[WAIT] Waiting for API readiness...")

    deadline = time.time() + MAX_WAIT_SECONDS

    while time.time() < deadline:
        try:
            r = requests.get(base_url.rstrip("/") + HEALTH_ENDPOINT, timeout=2)
            if r.status_code == 200:
                print("[OK] API is ready")
                return
        except Exception:
            pass

        time.sleep(RETRY_INTERVAL)

    raise RuntimeError("API did not become ready in time")


def request_with_retry(
    method: str,
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:

    for attempt in range(10):
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=30)
            else:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)

            if resp.status_code >= 400:
                print(f"[HTTP {resp.status_code}] {resp.text}")

            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.ConnectionError:
            print(f"[RETRY] API not ready (attempt {attempt + 1})")
            time.sleep(1.5)

    raise RuntimeError(f"Failed to connect after retries -> {url}")


def _req(base_url: str, api_key: str, user_id: str, case: Case) -> Dict[str, Any]:
    url = base_url.rstrip("/") + case.path

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-User-Id": user_id,
    }

    return request_with_retry(case.method.upper(), url, headers, case.payload)


# =========================
# NORMALIZATION
# =========================

def _normalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalize(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_normalize(x) for x in obj]
    return obj


# =========================
# SNAPSHOT IO
# =========================

def _save(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# =========================
# DIFF ENGINE
# =========================

def simple_diff(a: Any, b: Any, path="") -> List[str]:
    diffs = []

    if type(a) != type(b):
        diffs.append(f"{path}: TYPE {type(a)} != {type(b)}")
        return diffs

    if isinstance(a, dict):
        keys = set(a.keys()) | set(b.keys())
        for k in keys:
            new_path = f"{path}.{k}" if path else k
            if k not in a:
                diffs.append(f"{new_path}: missing in actual")
            elif k not in b:
                diffs.append(f"{new_path}: missing in expected")
            else:
                diffs.extend(simple_diff(a[k], b[k], new_path))

    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{path}: list size {len(a)} != {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                diffs.extend(simple_diff(x, y, f"{path}[{i}]"))

    else:
        if a != b:
            diffs.append(f"{path}: {a} != {b}")

    return diffs


# =========================
# MAIN
# =========================

def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--out", default="snapshots")
    parser.add_argument("--mode", choices=["record", "compare"], required=True)

    args = parser.parse_args()

    out_dir = Path(args.out)
    api_key = _resolve_api_key(args.api_key)

    # Wait for API readiness before hitting endpoints.
    wait_for_api(args.base_url)

    cases: List[Case] = [
        Case(
            name="natal_1",
            method="POST",
            path="/v1/chart/natal",
            payload={
                "natal_year": 1990,
                "natal_month": 1,
                "natal_day": 1,
                "natal_hour": 10,
                "natal_minute": 30,
                "natal_second": 0,
                "lat": -23.55052,
                "lng": -46.633308,
                "timezone": "America/Sao_Paulo",
                "house_system": "P",
                "zodiac_type": "tropical",
            },
        ),
        Case(
            name="solar_return_2026",
            method="POST",
            path="/v1/solar-return/calculate",
            payload={
                "natal": {
                    "data": "1990-01-01",
                    "hora": "10:30:00",
                    "timezone": "America/Sao_Paulo",
                    "local": {"lat": -23.55052, "lon": -46.633308},
                },
                "alvo": {
                    "ano": 2026,
                    "timezone": "America/Sao_Paulo",
                    "local": {"lat": -23.55052, "lon": -46.633308},
                },
                "preferencias": {
                    "perfil": "padrao",
                    "sistema_casas": "P",
                    "zodiaco": "tropical",
                },
            },
        ),
    ]

    failures: List[Tuple[str, str]] = []

    for case in cases:
        print(f"[RUN] {case.name}")

        live = _normalize(_req(args.base_url, api_key, args.user_id, case))
        snap_path = out_dir / f"{case.name}.json"

        if args.mode == "record":
            _save(snap_path, live)
            print(f"[RECORDED] {snap_path}")

        else:
            expected = _normalize(_load(snap_path))

            diffs = simple_diff(live, expected)

            if diffs:
                failures.append((case.name, str(snap_path)))
                print(f"[DIFF] {case.name}")
                for d in diffs[:10]:
                    print("  -", d)
            else:
                print(f"[OK] {case.name}")

    if failures:
        print("\nFAILURES:")
        for name, path in failures:
            print(f"- {name}: {path}")
        sys.exit(1)

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    main()
