# Start the API and the Vite dev server on Windows. No containers.
# Syntax can be checked on Linux. This file has not been executed on Windows 11.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force -Path logs | Out-Null
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  throw "missing .venv. Run scripts/setup_windows.ps1 from the repository root first."
}
$npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npm) {
  $npm = (Get-Command npm -ErrorAction SilentlyContinue).Source
}
if (-not $npm) {
  throw "npm was not found on PATH. Install Node.js, then run scripts/setup_windows.ps1."
}
if (-not $env:UNLAB_DATA_DIR) {
  $env:UNLAB_DATA_DIR = Join-Path $root "data"
}
$apiPort = if ($env:UNLAB_API_PORT) { $env:UNLAB_API_PORT } else { "8000" }
$webPort = if ($env:UNLAB_WEB_PORT) { $env:UNLAB_WEB_PORT } else { "5173" }
$env:PYTHONPATH = "src"
$api = Start-Process -FilePath ".\.venv\Scripts\python.exe" -WorkingDirectory $root -ArgumentList "-m","uvicorn","urbannoise.api:app","--host","127.0.0.1","--port",$apiPort -RedirectStandardOutput "logs\api.log" -RedirectStandardError "logs\api.err.log" -PassThru
Set-Content -Path logs\api.pid -Value $api.Id
$web = Start-Process -FilePath $npm -WorkingDirectory $root -ArgumentList "run","dev","--prefix","apps/web","--","--host","127.0.0.1","--port",$webPort,"--strictPort" -RedirectStandardOutput "logs\web.log" -RedirectStandardError "logs\web.err.log" -PassThru
Set-Content -Path logs\web.pid -Value $web.Id
Write-Output "api http://127.0.0.1:$apiPort"
Write-Output "web http://127.0.0.1:$webPort"
Write-Output "data $env:UNLAB_DATA_DIR"
