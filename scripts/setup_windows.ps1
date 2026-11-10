# UrbanNoiseLab native Windows setup. Docker is not used.
# This file was syntax-checked only if a PowerShell parser was available.
# It was not executed on the Linux host that produced this change.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (Test-Path "apps\web\package-lock.json") {
  npm ci --prefix apps/web
} else {
  npm install --prefix apps/web
}
Write-Output "setup_windows.ps1 finished"
