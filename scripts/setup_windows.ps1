# UrbanNoiseLab Windows setup.
# Does not call Set-ExecutionPolicy and does not change machine-wide configuration.
# Process-scoped bypass:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Resolve-Python311 {
  $candidates = @(
    @{ Exe = 'python'; Prefix = @() },
    @{ Exe = 'python3'; Prefix = @() },
    @{ Exe = 'py'; Prefix = @('-3') }
  )
  foreach ($candidate in $candidates) {
    if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
    & $candidate.Exe @($candidate.Prefix + @('-c', 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)')) | Out-Null
    if ($LASTEXITCODE -eq 0) { return $candidate }
  }
  throw 'python 3.11+ is required (tried python, python3, and py -3) and was not found on PATH'
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw 'npm is required and was not found on PATH'
}

$python = Resolve-Python311
$venvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
  & $python.Exe @($python.Prefix + @('-m', 'venv', (Join-Path $Root '.venv')))
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if (-not (Test-Path -LiteralPath $venvPython)) {
  throw "venv python was not created at $venvPython"
}

& $venvPython -m pip install -e '.[dev]'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
Push-Location (Join-Path $Root 'apps\web')
try {
  if ($npmCmd) {
    & $npmCmd.Source install
  } else {
    & npm install
  }
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Pop-Location
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root 'logs') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root 'data') | Out-Null
$example = Join-Path $Root '.env.example'
$envFile = Join-Path $Root '.env'
if ((-not (Test-Path -LiteralPath $envFile)) -and (Test-Path -LiteralPath $example)) {
  Copy-Item -LiteralPath $example -Destination $envFile
  Write-Host 'created .env from .env.example inside the repository'
}

Write-Host 'setup complete'
Write-Host 'UNLAB_DATA_DIR is the local data directory (default ./data).'
Write-Host 'UNLAB_JWT_SECRET in .env.example is demo-only. Replace it before any non-demo use.'
Write-Host 'Demo account passwords in README.md are demo-only.'
