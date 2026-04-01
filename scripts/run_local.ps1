param(
  [string]$ApiKey,
  [string]$ProjectRef,
  [string]$DbPassword,
  [string]$DbHost,
  [string]$DbPort,
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$UserId = "00000000-0000-0000-0000-000000000001",
  [ValidateSet("baseline","verify","all")]
  [string]$Mode = "all"
)

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")
$ScriptFingerprint = "run_local.ps1 v2026-04-01.3"
Write-Host ("Script fingerprint: {0}" -f $ScriptFingerprint)

function Mask-DbUrl([string]$url) {
  if ([string]::IsNullOrWhiteSpace($url)) { return "" }
  # mask password between ":" and "@"
  return ($url -replace "://([^:]+):([^@]+)@", "://${1}:****@")
}

function Read-Secret([string]$prompt) {
  $secure = Read-Host $prompt -AsSecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

function Read-WithDefault([string]$prompt, [string]$defaultValue) {
  $raw = Read-Host "$prompt [$defaultValue]"
  if ([string]::IsNullOrWhiteSpace($raw)) {
    return $defaultValue
  }
  return $raw.Trim()
}

function Stop-PortProcess([int]$port) {
  $lines = netstat -ano | findstr ":$port"
  if (-not $lines) { return }
  $pids = @()
  foreach ($line in $lines) {
    $parts = $line -split "\s+"
    if ($parts.Length -ge 5) {
      $pid = $parts[-1]
      if ($pid -match "^\d+$") { $pids += $pid }
    }
  }
  $pids = $pids | Select-Object -Unique
  foreach ($pid in $pids) {
    try {
      Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
      Write-Host "Stopped PID $pid on port $port."
    } catch {}
  }
}

function Build-Dsn([string]$dbUser, [string]$password, [string]$dbHostName, [int]$port) {
  if ([string]::IsNullOrWhiteSpace($dbUser)) { return "" }
  if ([string]::IsNullOrWhiteSpace($dbHostName)) { return "" }
  $encoded = [System.Uri]::EscapeDataString($password)
  return ("postgresql://{0}:{1}@{2}:{3}/postgres" -f $dbUser, $encoded, $dbHostName, $port)
}

function Wait-ServerReady {
  param(
    [string]$Url = "http://127.0.0.1:8000/docs",
    [int]$TimeoutSeconds = 30
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $resp = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
      if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) { return $true }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  return $false
}

function Start-Uvicorn([string]$modeLabel) {
  Write-Host "Starting uvicorn ($modeLabel)..."
  return Start-Process -PassThru -NoNewWindow -FilePath "uvicorn" -ArgumentList "main:app --reload --port 8000"
}

function Stop-Uvicorn($process) {
  if ($process -and $process.Id) {
    Write-Host "Stopping uvicorn..."
    Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
  }
}

# ---------- Inputs ----------
if (-not $ApiKey) {
  $ApiKey = Read-Secret "API_KEY (nao sera exibida)"
}

if (-not $ProjectRef) {
  $ProjectRef = Read-Host "SUPABASE project_ref (ex: grzlgxwyyhruywszwviv)"
}

if (-not $DbPassword) {
  $firstPassword = Read-Secret "DB password (nao sera exibida)"
  $confirmPassword = Read-Secret "Confirm DB password (nao sera exibida)"
  if ($firstPassword -ne $confirmPassword) {
    Write-Host "DB password mismatch: as senhas digitadas nao coincidem."
    exit 1
  }
  $DbPassword = $firstPassword
}

if (-not $DbHost) {
  $DbHost = Read-WithDefault "DB host" "aws-0-us-west-2.pooler.supabase.com"
}

if (-not $DbPort) {
  $DbPort = Read-WithDefault "DB port" "6543"
}

$ProjectRef = $ProjectRef.Trim()
$DbHost = $DbHost.Trim()
$DbPort = $DbPort.Trim()

if ([string]::IsNullOrWhiteSpace($ApiKey)) { Write-Host "API_KEY invalida."; exit 1 }
if ([string]::IsNullOrWhiteSpace($ProjectRef)) { Write-Host "project_ref invalido."; exit 1 }
if ([string]::IsNullOrWhiteSpace($DbPassword)) { Write-Host "DB password invalida."; exit 1 }
if ([string]::IsNullOrWhiteSpace($DbHost)) { Write-Host "DB host invalido."; exit 1 }

$parsedPort = 0
if (-not [int]::TryParse($DbPort, [ref]$parsedPort)) {
  Write-Host "DB port invalido: use numero inteiro."
  exit 1
}

# ---------- Candidate matrix (avoid reserved 'host') ----------
$candidateMatrix = @(
  @{
    label = "provided"
    dbHost = $DbHost
    port = $parsedPort
    users = @("postgres.$ProjectRef", "postgres")
  }
)

Write-Host "API_KEY set: " ($ApiKey.Length -gt 0)
Write-Host "DB candidates:"
foreach ($candidate in $candidateMatrix) {
  Write-Host ("- {0}: host={1} port={2} users={3}" -f $candidate.label, $candidate.dbHost, $candidate.port, ($candidate.users -join ","))
}

# ---------- Validate DB connection with asyncpg ----------
Write-Host "Validating DB connection..."

$validate = @'
import os, sys, asyncio, json
import asyncpg

password = os.getenv("DB_PASSWORD", "")
candidates_raw = os.getenv("DB_CANDIDATES_JSON", "[]").strip()

try:
    candidates = json.loads(candidates_raw)
except Exception:
    print("DB FAIL: invalid DB_CANDIDATES_JSON")
    sys.exit(1)

if isinstance(candidates, dict):
    candidates = [candidates]

if not isinstance(candidates, list):
    print("DB FAIL: candidates payload must be a list")
    sys.exit(1)

async def try_conn(host: str, port: int, user: str):
    conn = await asyncpg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database="postgres",
        statement_cache_size=0,
        command_timeout=60,
        timeout=15,
        ssl="require",
    )
    try:
        await conn.execute("select 1")
    finally:
        await conn.close()

async def main() -> int:
    last_error = None
    last_hint = "UNKNOWN"
    seen_hints = set()

    for candidate in candidates:
        label = str(candidate.get("label", "candidate")).strip()
        host = str(candidate.get("dbHost", "")).strip()
        try:
            port = int(candidate.get("port", 0))
        except Exception:
            port = 0
        users = [str(u).strip() for u in candidate.get("users", []) if str(u).strip()]

        if not host or not port or not users:
            print(f"DB_SKIP candidate={label} reason=invalid_candidate")
            continue

        for user in users:
            try:
                await try_conn(host, port, user)
                print("DB_OK_JSON=" + json.dumps({"label": label, "host": host, "port": port, "user": user}))
                return 0
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                msg = str(exc).lower()
                exc_type = type(exc).__name__
                if exc_type in {"TimeoutError", "ConnectTimeoutError"} or "timed out" in msg or "timeout" in msg:
                    last_hint = "NETWORK_TIMEOUT"
                elif exc_type == "InvalidPasswordError":
                    last_hint = "INVALID_PASSWORD"
                elif "tenant or user not found" in msg:
                    last_hint = "TENANT_OR_USER_NOT_FOUND"
                else:
                    last_hint = "GENERIC"
                seen_hints.add(last_hint)
                print(f"DB_TRY_FAIL candidate={label} host={host} port={port} user={user} hint={last_hint} error={last_error}")

    for hint in ("INVALID_PASSWORD", "TENANT_OR_USER_NOT_FOUND", "NETWORK_TIMEOUT", "GENERIC", "UNKNOWN"):
        if hint in seen_hints:
            last_hint = hint
            break
    print(f"DB_FAIL: {last_error or 'unknown error'}")
    print(f"DB_HINT={last_hint}")
    return 2

raise SystemExit(asyncio.run(main()))
'@

$env:DB_PASSWORD = $DbPassword
$env:DB_CANDIDATES_JSON = ($candidateMatrix | ConvertTo-Json -Compress)

$tmp = Join-Path $env:TEMP ("validate_db_" + [Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Path $tmp -Value $validate -Encoding UTF8

try {
  $validationOutput = python $tmp 2>&1
  $validationExit = $LASTEXITCODE
} finally {
  Remove-Item -Path $tmp -ErrorAction SilentlyContinue
}

foreach ($line in $validationOutput) { Write-Host $line }

if ($validationExit -ne 0) {
  Write-Host "Aborting: DB connection failed."
  $hint = $null
  foreach ($line in $validationOutput) {
    if ("$line" -match "^DB_HINT=(.+)$") { $hint = $Matches[1].Trim(); break }
  }
  switch ($hint) {
    "NETWORK_TIMEOUT" { Write-Host "Tip: timeout de rede (firewall/VPN/antivirus/DNS). Tente outra rede." }
    "INVALID_PASSWORD" { Write-Host "Tip: senha do Postgres invalida. Reset em Supabase > Settings > Database." }
    "TENANT_OR_USER_NOT_FOUND" { Write-Host "Tip: project_ref/host/usuario nao batem. Confira o projeto correto." }
    default { Write-Host "Tip: confira project_ref, host/porta do pooler e senha atual do banco." }
  }
  Remove-Item Env:DB_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:DB_CANDIDATES_JSON -ErrorAction SilentlyContinue
  exit 1
}

$selected = $null
foreach ($line in $validationOutput) {
  if ("$line" -match "^DB_OK_JSON=(.+)$") {
    try { $selected = ($Matches[1] | ConvertFrom-Json) } catch { $selected = $null }
    break
  }
}

if (-not $selected -or [string]::IsNullOrWhiteSpace($selected.user) -or [string]::IsNullOrWhiteSpace($selected.host) -or -not $selected.port) {
  Write-Host "Aborting: DB validation passed without selected connection."
  Remove-Item Env:DB_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:DB_CANDIDATES_JSON -ErrorAction SilentlyContinue
  exit 1
}

$selectedUser = "$($selected.user)"
$selectedHost = "$($selected.host)"
$selectedPort = [int]$selected.port

$DatabaseUrl = Build-Dsn $selectedUser $DbPassword $selectedHost $selectedPort
if (-not ($DatabaseUrl -match "^postgres(ql)?://")) {
  Write-Host "Aborting: generated DATABASE_URL invalida."
  Remove-Item Env:DB_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:DB_CANDIDATES_JSON -ErrorAction SilentlyContinue
  exit 1
}

$env:API_KEY = $ApiKey
$env:ASTRO_API_KEY = $ApiKey
$env:DATABASE_URL = $DatabaseUrl

Remove-Item Env:DB_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:DB_CANDIDATES_JSON -ErrorAction SilentlyContinue

Write-Host "DATABASE_URL set: " (Mask-DbUrl $DatabaseUrl)
Write-Host "DB selected: user=$selectedUser host=$selectedHost port=$selectedPort"

# Ensure port 8000 is free
Stop-PortProcess 8000

# ---------- baseline ----------
if ($Mode -in @("baseline","all")) {
  $env:CACHE_NATAL_ENABLED = "false"
  $env:CACHE_SOLAR_RETURN_ENABLED = "false"

  $uvicorn = Start-Uvicorn "flags OFF"
  Write-Host "Waiting for server..."
  if (-not (Wait-ServerReady -Url "$BaseUrl/docs" -TimeoutSeconds 30)) {
    Stop-Uvicorn $uvicorn
    Write-Host "Server did not become ready on port 8000."
    exit 1
  }

  Write-Host "Recording snapshots (flags OFF)..."
  python scripts/regression_snapshots.py --mode record --base-url $BaseUrl --user-id $UserId
  if ($LASTEXITCODE -ne 0) { Stop-Uvicorn $uvicorn; exit $LASTEXITCODE }

  Stop-Uvicorn $uvicorn
}

# ---------- verify ----------
if ($Mode -in @("verify","all")) {
  $env:CACHE_NATAL_ENABLED = "true"
  $env:CACHE_SOLAR_RETURN_ENABLED = "true"

  $uvicorn = Start-Uvicorn "flags ON"
  Write-Host "Waiting for server..."
  if (-not (Wait-ServerReady -Url "$BaseUrl/docs" -TimeoutSeconds 30)) {
    Stop-Uvicorn $uvicorn
    Write-Host "Server did not become ready on port 8000."
    exit 1
  }

  Write-Host "Comparing snapshots (flags ON)..."
  python scripts/regression_snapshots.py --mode compare --base-url $BaseUrl --user-id $UserId
  if ($LASTEXITCODE -ne 0) { Stop-Uvicorn $uvicorn; exit $LASTEXITCODE }

  Write-Host "Running concurrency test (flags ON)..."
  python scripts/concurrency_test.py --base-url $BaseUrl --user-id $UserId
  if ($LASTEXITCODE -ne 0) { Stop-Uvicorn $uvicorn; exit $LASTEXITCODE }

  Stop-Uvicorn $uvicorn
}
