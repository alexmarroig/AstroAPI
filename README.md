# AstroAPI

## Installation
Use `requirements.txt` as the source of truth for runtime dependencies:

```bash
pip install -r requirements.txt
```

## Local smoke test
Run without reload to see raw startup/runtime exceptions:

```bash
uvicorn main:app --port 8000 --log-level debug
```

## Local cache validation (PowerShell)
`scripts/run_local.ps1` provides a one-command flow for baseline and verify:

- prints a script fingerprint at startup
- asks for `API_KEY`, `project_ref`, and DB password twice (`DB password` + `Confirm DB password`)
- keeps secrets hidden (SecureString input, password never printed)
- validates DB connectivity before starting `uvicorn`
- tests common users for selected host:
  - `postgres.<project_ref>`
  - `postgres`
- sets `API_KEY`, `ASTRO_API_KEY`, and `DATABASE_URL` only after successful DB validation
- logs only masked DSN (`****`) plus selected `user/host/port`

### Modes
- `baseline`: cache OFF + snapshot record
- `verify`: cache ON + snapshot compare + concurrency test
- `all`: baseline then verify

### Commands
```powershell
cd C:\Users\gaming\Desktop\Projetos\Inner-Sky\Backend\AstroAPI
.\scripts\run_local.ps1 -Mode baseline
.\scripts\run_local.ps1 -Mode verify
.\scripts\run_local.ps1 -Mode all
```

Use custom DB host/port if needed:

```powershell
.\scripts\run_local.ps1 -Mode verify -DbHost "aws-0-us-west-2.pooler.supabase.com" -DbPort "6543"
```

### Deterministic validation output
- `DB_OK_JSON=...`: DB validated and candidate selected.
- `DB_HINT=INVALID_PASSWORD`: wrong DB password for that project/host/user.
- `DB_HINT=TENANT_OR_USER_NOT_FOUND`: host/project/user mismatch.
- `DB_HINT=NETWORK_TIMEOUT`: network or firewall or VPN or DNS issue.
- `DB_HINT=GENERIC`: non-classified DB error.

If DB validation fails, script aborts before starting `uvicorn`.

## Test health report
`scripts/report_test_health.py` runs `pytest` and generates a summary report.

```bash
cd Backend/AstroAPI
python scripts/report_test_health.py
```

## Interpretation inventory audit
Use `scripts/check_content_inventory.py` to validate `public.modules` coverage and compare with local interpretation dictionaries.

```bash
cd Backend/AstroAPI
python scripts/check_content_inventory.py
```

Output:
- JSON artifact: `scripts/artifacts/content_inventory_<timestamp>.json`
- Text summary: `scripts/artifacts/content_inventory_<timestamp>.txt`

Key statuses:
- `STATUS=OK`: table exists, minimum seed reached, no critical gaps.
- `STATUS=WARNING`: table exists, but with non-critical inconsistencies.
- `STATUS=CRITICAL`: DB/table unavailable or critical coverage/validation failure.

## Solar return flags
- `SOLAR_RETURN_ENGINE=v1|v2`
  - `v1` (default): simple nearest-time search
  - `v2`: robust bracket + bisection search
- `SOLAR_RETURN_COMPARE=1`
  - when `SOLAR_RETURN_ENGINE=v2`, logs precision delta vs `v1` without changing response payload
