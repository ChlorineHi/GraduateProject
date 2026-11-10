# UrbanNoiseLab native Windows setup. Docker is not used.
# This file was syntax-checked only if a PowerShell parser was available.
# It was not executed on the Linux host that produced this change.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm was not found on PATH. Install Node.js LTS, then run this script again."
}
if (Get-Command py -ErrorAction SilentlyContinue) {
  py -3 -m venv .venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  python -m venv .venv
} else {
  throw "Python was not found. Install Python 3.11 or newer and enable the py launcher or python on PATH."
}
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (Test-Path "apps\web\package-lock.json") {
  npm ci --prefix apps/web
} else {
  npm install --prefix apps/web
}
Write-Output "setup_windows.ps1 finished"
