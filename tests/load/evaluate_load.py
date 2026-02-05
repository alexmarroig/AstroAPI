import csv
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
STATS_CSV = ROOT / "artifacts" / "load_stats.csv"
THRESHOLDS = ROOT / "thresholds.json"
BASELINE = ROOT / "baseline.json"
REPORT = ROOT / "artifacts" / "load_report.json"
TRENDS = ROOT / "artifacts" / "load_trends.jsonl"


def _to_rate(value: str) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _to_ms(value: str) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def read_stats(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing load stats file: {path}")

    endpoints = {}
    global_stats = {"p95_ms": 0.0, "error_rate": 0.0, "requests": 0}

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "").strip()
            method = row.get("Method", "").strip()
            reqs = int(float(row.get("Request Count", 0) or 0))
            failures = int(float(row.get("Failure Count", 0) or 0))
            p95 = _to_ms(row.get("95%", "0"))
            error_rate = failures / reqs if reqs else 0.0

            if name == "Aggregated":
                global_stats = {"p95_ms": p95, "error_rate": error_rate, "requests": reqs}
                continue

            endpoint_name = f"{method} {name}".strip()
            endpoints[endpoint_name] = {
                "p95_ms": p95,
                "error_rate": error_rate,
                "requests": reqs,
                "failures": failures,
            }

    return {"global": global_stats, "endpoints": endpoints}


def evaluate(actual: dict, thresholds: dict, baseline: dict) -> dict:
    failures = []

    def check(name: str, observed: dict, target: dict, base: dict | None):
        p95 = observed.get("p95_ms", 0.0)
        err = observed.get("error_rate", 0.0)

        if p95 > target["p95_ms_max"]:
            failures.append(f"{name}: p95 {p95:.1f}ms > threshold {target['p95_ms_max']}ms")
        if err > target["error_rate_max"]:
            failures.append(f"{name}: error_rate {err:.3f} > threshold {target['error_rate_max']:.3f}")

        if base:
            if p95 > base.get("p95_ms", float("inf")):
                failures.append(f"{name}: p95 {p95:.1f}ms regrediu baseline {base['p95_ms']:.1f}ms")
            if err > base.get("error_rate", float("inf")):
                failures.append(f"{name}: error_rate {err:.3f} regrediu baseline {base['error_rate']:.3f}")

    check(
        "global",
        actual.get("global", {}),
        thresholds.get("global", {}),
        baseline.get("global", {}),
    )

    for endpoint, target in thresholds.get("endpoints", {}).items():
        observed = actual.get("endpoints", {}).get(endpoint)
        if not observed:
            failures.append(f"{endpoint}: endpoint ausente no relatório de carga")
            continue
        base = baseline.get("endpoints", {}).get(endpoint)
        check(endpoint, observed, target, base)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ok": not failures,
        "failures": failures,
        "actual": actual,
    }


def main() -> int:
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    actual = read_stats(STATS_CSV)
    result = evaluate(actual, thresholds, baseline)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    with TRENDS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    if not result["ok"]:
        print("Load gate failed:")
        for failure in result["failures"]:
            print(f" - {failure}")
        return 1

    print("Load gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
