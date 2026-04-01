import argparse
import os
import concurrent.futures
import requests


def _resolve_api_key(value: str | None) -> str:
    if value and value.strip():
        return value.strip()
    env_key = os.getenv("API_KEY") or os.getenv("ASTRO_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    raise SystemExit("Missing API key. Use --api-key or set API_KEY/ASTRO_API_KEY.")

def call(url: str, api_key: str, user_id: str, payload: dict) -> str:
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "X-User-Id": user_id},
        json=payload,
        timeout=180,
    )
    if resp.status_code >= 400:
        print(f"[HTTP {resp.status_code}] {resp.text}")
    resp.raise_for_status()
    return resp.text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--api-key")
    ap.add_argument("--user-id", required=True)
    args = ap.parse_args()

    api_key = _resolve_api_key(args.api_key)
    url = args.base_url.rstrip("/") + "/v1/chart/natal"
    payload = {
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
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(call, url, api_key, args.user_id, payload) for _ in range(5)]
        results = [f.result() for f in futures]

    first = results[0]
    assert all(r == first for r in results), "Respostas divergentes em concorrencia."
    print("OK: 5 requests simultaneas retornaram o mesmo payload.")


if __name__ == "__main__":
    main()
