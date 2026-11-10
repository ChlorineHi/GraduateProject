# Run the project test suite with the virtualenv created by setup_windows.ps1.
# Does not start or stop servers, does not call Set-ExecutionPolicy, and does
# not change machine-wide configuration.
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test_windows.ps1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $pythonCmd) { $pythonCmd = Get-Command py -ErrorAction SilentlyContinue }
if (-not $pythonCmd) {
  throw 'python is required and was not found on PATH'
}

$venvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
  throw 'missing .venv. Run: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1'
}

$env:PYTHONPATH = if ($env:PYTHONPATH) { "$Root\src;$env:PYTHONPATH" } else { "$Root\src" }
& $venvPython -m pytest -q --tb=line
exit $LASTEXITCODE
