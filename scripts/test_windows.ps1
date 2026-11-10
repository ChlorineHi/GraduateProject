# Run pytest and the frontend production build on Windows.
# Not executed on the Linux host.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  throw "missing .venv; run scripts/setup_windows.ps1 first"
}
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest -q --tb=line
npm run build --prefix apps/web
Write-Output "test_windows.ps1 finished"
