import sys
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


def run_tests() -> int:
    junit_file = Path("tests") / "artifacts" / "pytest-results.xml"
    junit_file.parent.mkdir(parents=True, exist_ok=True)

    # Execute pytest with JUnit output for later parsing.
    # Use subprocess to controlar timeout e evitar travar em imports async no Windows.
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests",
        "--junitxml",
        str(junit_file),
        "--maxfail=5",
        "--disable-warnings",
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).resolve().parent.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode
    except subprocess.TimeoutExpired as exc:
        print(f"pytest excedeu timeout de {exc.timeout} segundos", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return 124
    except KeyboardInterrupt:
        print("Execução interrompida pelo usuário (KeyboardInterrupt).", file=sys.stderr)
        return 130


def parse_junit(path: Path) -> dict[str, int]:
    if not path.exists():
        raise FileNotFoundError(f"JUnit report not found: {path}")

    tree = ET.parse(path)
    root = tree.getroot()

    total = 0
    failures = 0
    errors = 0
    skipped = 0

    # root might be <testsuites> or <testsuite>
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]

    for suite in suites:
        total += int(suite.attrib.get("tests", 0))
        failures += int(suite.attrib.get("failures", 0))
        errors += int(suite.attrib.get("errors", 0))
        skipped += int(suite.attrib.get("skipped", 0))

    return {
        "total": total,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "passed": total - failures - errors - skipped,
    }


def print_report(stats: dict[str, int]):
    total = stats["total"]
    failed = stats["failures"] + stats["errors"]
    passed = stats["passed"]
    skipped = stats["skipped"]

    fail_rate = (failed / total * 100) if total > 0 else 0.0

    print("\n=== TEST HEALTH REPORT ===")
    print(f"Total tests run : {total}")
    print(f"Passed          : {passed}")
    print(f"Failed          : {failed}")
    print(f"Skipped         : {skipped}")
    print(f"Fail rate       : {fail_rate:.2f}%")
    print("==========================\n")


def main():
    status = run_tests()
    junit_file = Path("tests") / "artifacts" / "pytest-results.xml"

    try:
        stats = parse_junit(junit_file)
        print_report(stats)
    except Exception as exc:
        print(f"Erro ao ler relatório JUnit: {exc}", file=sys.stderr)
        # se falhar na parse, ainda repassa o status original

    # Retorna código de erro para CI falhar se testes falharem
    sys.exit(status)


if __name__ == "__main__":
    main()
