# Start the API and the Vite dev server on Windows. No containers.
# Not executed on the Linux host.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
New-Item -ItemType Directory -Force -Path logs | Out-Null
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  throw "missing .venv; run scripts/setup_windows.ps1 first"
}
$env:PYTHONPATH = "src"
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m","uvicorn","urbannoise.api:app","--host","127.0.0.1","--port","8000" -RedirectStandardOutput "logs\api.log" -RedirectStandardError "logs\api.err.log" -PassThru | Select-Object -ExpandProperty Id | Set-Content logs\api.pid
Start-Process -FilePath "npm" -ArgumentList "run","dev","--prefix","apps/web","--","--host","127.0.0.1","--port","5173","--strictPort" -RedirectStandardOutput "logs\web.log" -RedirectStandardError "logs\web.err.log" -PassThru | Select-Object -ExpandProperty Id | Set-Content logs\web.pid
Write-Output "api http://127.0.0.1:8000"
Write-Output "web http://127.0.0.1:5173"
