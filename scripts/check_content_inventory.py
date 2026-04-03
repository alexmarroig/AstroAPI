from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import asyncpg

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from interpretations import (
    ASPECT_INTERPRETATIONS,
    PLANET_HOUSE_INTERPRETATIONS,
    PLANET_SIGN_INTERPRETATIONS,
    SYNASTRY_INTERPRETATIONS,
    TRANSIT_INTERPRETATIONS,
)


DEFAULT_MIN_SEED = 705
CRITICAL_TYPES = ("planet_sign", "planet_house", "aspect")


@dataclass
class DbTarget:
    host: str | None
    port: int | None
    user: str | None
    database: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita inventario de interpretacoes (DB modules + dicionarios locais)."
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Arquivo JSON de saida (default: scripts/artifacts/content_inventory_<timestamp>.json).",
    )
    parser.add_argument(
        "--min-seed",
        type=int,
        default=DEFAULT_MIN_SEED,
        help=f"Volume minimo esperado de modulos em public.modules (default: {DEFAULT_MIN_SEED}).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Retorna erro tambem quando houver warnings (alem dos critical).",
    )
    return parser.parse_args()


def get_output_paths(explicit_output: str | None) -> tuple[Path, Path]:
    if explicit_output:
        json_path = Path(explicit_output).resolve()
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        json_path = (Path(__file__).resolve().parent / "artifacts" / f"content_inventory_{timestamp}.json").resolve()

    txt_path = json_path.with_suffix(".txt")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    return json_path, txt_path


def parse_db_target(dsn: str | None) -> DbTarget:
    if not dsn:
        return DbTarget(host=None, port=None, user=None, database=None)
    parsed = urlparse(dsn)
    database = parsed.path.lstrip("/") if parsed.path else None
    return DbTarget(
        host=parsed.hostname,
        port=parsed.port,
        user=parsed.username,
        database=database or None,
    )


def local_dictionary_counts() -> dict[str, int]:
    return {
        "planet_sign": len(PLANET_SIGN_INTERPRETATIONS),
        "planet_house": len(PLANET_HOUSE_INTERPRETATIONS),
        "aspect": len(ASPECT_INTERPRETATIONS),
        "transit": len(TRANSIT_INTERPRETATIONS),
        "synastry": len(SYNASTRY_INTERPRETATIONS),
    }


async def inspect_modules_table(dsn: str) -> dict[str, Any]:
    conn = await asyncpg.connect(dsn=dsn, statement_cache_size=0, command_timeout=60)
    try:
        exists = await conn.fetchval("SELECT to_regclass('public.modules') IS NOT NULL")
        report: dict[str, Any] = {"exists": bool(exists)}
        if not exists:
            report.update(
                {
                    "total": 0,
                    "by_type": {},
                    "validation": {
                        "missing_id": 0,
                        "missing_type": 0,
                        "missing_content": 0,
                        "invalid_content_shape": 0,
                        "invalid_planet_sign": 0,
                        "invalid_planet_house": 0,
                        "invalid_aspect": 0,
                    },
                }
            )
            return report

        total = int(await conn.fetchval("SELECT COUNT(*) FROM public.modules"))
        by_type_rows = await conn.fetch(
            """
            SELECT COALESCE(NULLIF(TRIM(type), ''), '<null>') AS module_type, COUNT(*)::int AS count
            FROM public.modules
            GROUP BY 1
            ORDER BY 1
            """
        )
        by_type = {str(row["module_type"]): int(row["count"]) for row in by_type_rows}

        validation_row = await conn.fetchrow(
            """
            SELECT
              COUNT(*) FILTER (WHERE id IS NULL OR TRIM(id::text) = '')::int AS missing_id,
              COUNT(*) FILTER (WHERE type IS NULL OR TRIM(type) = '')::int AS missing_type,
              COUNT(*) FILTER (WHERE content IS NULL)::int AS missing_content,
              COUNT(*) FILTER (
                WHERE content IS NOT NULL
                  AND (jsonb_typeof(content) <> 'object'
                       OR NOT (content ? 'summary')
                       OR NOT (content ? 'interpretation'))
              )::int AS invalid_content_shape,
              COUNT(*) FILTER (
                WHERE type = 'planet_sign'
                  AND (planet IS NULL OR TRIM(planet) = '' OR sign IS NULL OR TRIM(sign) = '')
              )::int AS invalid_planet_sign,
              COUNT(*) FILTER (
                WHERE type = 'planet_house'
                  AND (planet IS NULL OR TRIM(planet) = '' OR house IS NULL)
              )::int AS invalid_planet_house,
              COUNT(*) FILTER (
                WHERE type = 'aspect'
                  AND (planet IS NULL OR TRIM(planet) = '' OR aspect IS NULL OR TRIM(aspect) = '')
              )::int AS invalid_aspect
            FROM public.modules
            """
        )

        report.update(
            {
                "total": total,
                "by_type": by_type,
                "validation": {k: int(validation_row[k]) for k in validation_row.keys()},
            }
        )
        return report
    finally:
        await conn.close()


def evaluate_report(
    *,
    modules_report: dict[str, Any],
    min_seed: int,
) -> tuple[list[str], list[str]]:
    critical: list[str] = []
    warnings: list[str] = []

    if not modules_report.get("exists"):
        critical.append("Tabela public.modules nao existe.")
        return critical, warnings

    total = int(modules_report.get("total", 0))
    if total < min_seed:
        critical.append(f"Volume de modules abaixo do minimo: {total} < {min_seed}.")

    by_type = modules_report.get("by_type", {})
    for module_type in CRITICAL_TYPES:
        if int(by_type.get(module_type, 0)) <= 0:
            critical.append(f"Tipo critico sem conteudo: {module_type}.")

    validation = modules_report.get("validation", {})
    for key, value in validation.items():
        value_int = int(value)
        if value_int <= 0:
            continue
        if key in {"missing_id", "missing_type", "missing_content"}:
            critical.append(f"Falha critica em validacao ({key}={value_int}).")
        else:
            warnings.append(f"Inconsistencia encontrada ({key}={value_int}).")

    return critical, warnings


def write_text_summary(path: Path, report: dict[str, Any]) -> None:
    status = report["status"]
    modules = report["modules"]
    lines = [
        "Content Inventory Report",
        f"generated_at_utc: {report['generated_at_utc']}",
        f"status: {status['status']}",
        f"db_target: user={report['db_target'].get('user')} host={report['db_target'].get('host')} port={report['db_target'].get('port')}",
        f"modules_exists: {modules.get('exists')}",
        f"modules_total: {modules.get('total')}",
        "modules_by_type:",
    ]
    for module_type, count in sorted(modules.get("by_type", {}).items()):
        lines.append(f"  - {module_type}: {count}")
    lines.append("validation:")
    for key, value in modules.get("validation", {}).items():
        lines.append(f"  - {key}: {value}")
    lines.append("local_dictionary_counts:")
    for key, value in report["local_dictionary_counts"].items():
        lines.append(f"  - {key}: {value}")
    if status["critical_issues"]:
        lines.append("critical_issues:")
        for issue in status["critical_issues"]:
            lines.append(f"  - {issue}")
    if status["warnings"]:
        lines.append("warnings:")
        for issue in status["warnings"]:
            lines.append(f"  - {issue}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def async_main(args: argparse.Namespace) -> int:
    dsn = os.getenv("DATABASE_URL", "").strip()
    db_target = parse_db_target(dsn)
    modules_report: dict[str, Any]
    db_error: str | None = None

    if not dsn:
        modules_report = {
            "exists": False,
            "total": 0,
            "by_type": {},
            "validation": {},
        }
        db_error = "DATABASE_URL nao configurada."
    else:
        try:
            modules_report = await inspect_modules_table(dsn)
        except Exception as exc:
            modules_report = {
                "exists": False,
                "total": 0,
                "by_type": {},
                "validation": {},
            }
            db_error = f"{type(exc).__name__}: {exc}"

    critical, warnings = evaluate_report(modules_report=modules_report, min_seed=args.min_seed)
    if db_error:
        critical.insert(0, f"Falha de conexao/consulta no banco: {db_error}")

    status_label = "ok"
    if critical:
        status_label = "critical"
    elif warnings:
        status_label = "warning"

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "db_target": {
            "host": db_target.host,
            "port": db_target.port,
            "user": db_target.user,
            "database": db_target.database,
        },
        "thresholds": {
            "min_seed": args.min_seed,
            "critical_types": list(CRITICAL_TYPES),
        },
        "modules": modules_report,
        "local_dictionary_counts": local_dictionary_counts(),
        "status": {
            "status": status_label,
            "critical_issues": critical,
            "warnings": warnings,
        },
    }

    json_path, txt_path = get_output_paths(args.output)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_text_summary(txt_path, report)

    print(f"STATUS={status_label.upper()}")
    print(f"REPORT_JSON={json_path}")
    print(f"REPORT_TXT={txt_path}")
    print(
        f"DB_TARGET=user={report['db_target']['user']} host={report['db_target']['host']} port={report['db_target']['port']}"
    )

    if critical:
        for issue in critical:
            print(f"CRITICAL: {issue}")
    if warnings:
        for warning in warnings:
            print(f"WARNING: {warning}")

    if critical:
        return 1
    if args.strict and warnings:
        return 2
    return 0


def main() -> None:
    args = parse_args()
    raise SystemExit(asyncio.run(async_main(args)))


if __name__ == "__main__":
    main()
