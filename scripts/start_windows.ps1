# Start uvicorn and Vite on 127.0.0.1. Logs and pid files go under logs/.
# Does not call Set-ExecutionPolicy and does not change machine-wide configuration.
# If a port is taken, exit without killing the process that owns it.
# Process-scoped bypass:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_windows.ps1
#   $env:UNLAB_API_PORT='8010'; $env:UNLAB_WEB_PORT='5174'; powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_windows.ps1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Import-UnlabEnv {
  param([string]$Path)
  if (-not (Test-Path -LiteralPath $Path)) { return }
  foreach ($raw in Get-Content -LiteralPath $Path) {
    $line = $raw.Trim()
    if ($line.Length -eq 0 -or $line.StartsWith('#')) { continue }
    if ($line -notmatch '^(UNLAB_[A-Za-z0-9_]+)=(.*)$') { continue }
    $name = $Matches[1]
    $value = $Matches[2].Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    if (-not (Test-Path -LiteralPath "Env:$name")) {
      Set-Item -Path "Env:$name" -Value $value
    }
  }
}

function Test-LoopbackPort {
  param([int]$Port)
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
    $waited = $async.AsyncWaitHandle.WaitOne(400, $false)
    if (-not $waited) { return $false }
    try { $client.EndConnect($async) } catch { return $false }
    return [bool]$client.Connected
  } catch {
    return $false
  } finally {
    $client.Close()
  }
}

function Test-RecordedProcess {
  param([string]$Name)
  $pidFile = Join-Path $Root "logs\$Name.pid"
  if (-not (Test-Path -LiteralPath $pidFile)) { return $false }
  $text = (Get-Content -LiteralPath $pidFile -Raw).Trim()
  if ($text -notmatch '^[0-9]+$') {
    Remove-Item -LiteralPath $pidFile -Force
    return $false
  }
  $running = Get-Process -Id ([int]$text) -ErrorAction SilentlyContinue
  if ($null -eq $running) {
    Remove-Item -LiteralPath $pidFile -Force
    return $false
  }
  return $true
}

function Wait-Http {
  param([string]$Url, [int]$Tries)
  for ($i = 0; $i -lt $Tries; $i++) {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { return $true }
    } catch {
    }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

Import-UnlabEnv (Join-Path $Root '.env')
if (-not $env:UNLAB_API_PORT) { $env:UNLAB_API_PORT = '8000' }
if (-not $env:UNLAB_WEB_PORT) { $env:UNLAB_WEB_PORT = '5173' }
if (-not $env:UNLAB_DATA_DIR) { $env:UNLAB_DATA_DIR = './data' }

if ($env:UNLAB_API_PORT -notmatch '^[0-9]+$' -or [int]$env:UNLAB_API_PORT -lt 1 -or [int]$env:UNLAB_API_PORT -gt 65535) {
  throw 'UNLAB_API_PORT must be a TCP port'
}
if ($env:UNLAB_WEB_PORT -notmatch '^[0-9]+$' -or [int]$env:UNLAB_WEB_PORT -lt 1 -or [int]$env:UNLAB_WEB_PORT -gt 65535) {
  throw 'UNLAB_WEB_PORT must be a TCP port'
}
if ($env:UNLAB_API_PORT -eq $env:UNLAB_WEB_PORT) {
  throw 'UNLAB_API_PORT and UNLAB_WEB_PORT must differ'
}

$venvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
  throw 'missing .venv. Run: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1'
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw 'npm is required and was not found on PATH'
}
if (-not (Test-Path -LiteralPath (Join-Path $Root 'apps\web\node_modules'))) {
  throw 'missing apps/web/node_modules. Run setup_windows.ps1'
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root 'logs') | Out-Null
New-Item -ItemType Directory -Force -Path $env:UNLAB_DATA_DIR | Out-Null

if ((Test-RecordedProcess -Name 'api') -or (Test-RecordedProcess -Name 'web')) {
  throw 'pid files in logs/ are still running. Run stop_windows.ps1'
}
foreach ($staleName in @('api', 'web')) {
  $stale = Join-Path $Root "logs\$staleName.pid"
  if (Test-Path -LiteralPath $stale) { Remove-Item -LiteralPath $stale -Force }
}

if (Test-LoopbackPort -Port ([int]$env:UNLAB_API_PORT)) {
  throw "127.0.0.1:$($env:UNLAB_API_PORT) is already in use. Not killing it. Set UNLAB_API_PORT to a free port."
}
if (Test-LoopbackPort -Port ([int]$env:UNLAB_WEB_PORT)) {
  throw "127.0.0.1:$($env:UNLAB_WEB_PORT) is already in use. Not killing it. Set UNLAB_WEB_PORT to a free port."
}

$env:PYTHONPATH = if ($env:PYTHONPATH) { "$Root\src;$env:PYTHONPATH" } else { "$Root\src" }
if ($env:UNLAB_JWT_SECRET) {
  Write-Host 'UNLAB_JWT_SECRET is set for this process. The value is not written to the log. Demo passwords stay demo-only.'
} else {
  Write-Host 'UNLAB_JWT_SECRET is unset. The application demo default will be used. Demo only.'
}

$apiLog = Join-Path $Root 'logs\api.log'
$apiErr = Join-Path $Root 'logs\api.err.log'
$webLog = Join-Path $Root 'logs\web.log'
$webErr = Join-Path $Root 'logs\web.err.log'
# Start-Process refuses RedirectStandard* when the target file already exists.
foreach ($logPath in @($apiLog, $apiErr, $webLog, $webErr)) {
  if (Test-Path -LiteralPath $logPath) { Remove-Item -LiteralPath $logPath -Force }
}
$banner = "----- $(Get-Date -Format o) api 127.0.0.1:$($env:UNLAB_API_PORT) UNLAB_DATA_DIR=$($env:UNLAB_DATA_DIR) web 127.0.0.1:$($env:UNLAB_WEB_PORT) -----"
Add-Content -LiteralPath (Join-Path $Root 'logs\start.txt') -Value $banner

$apiProc = Start-Process -FilePath $venvPython -ArgumentList @(
  '-m', 'uvicorn', 'urbannoise.api:app', '--host', '127.0.0.1', '--port', $env:UNLAB_API_PORT
) -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput $apiLog -RedirectStandardError $apiErr
Set-Content -LiteralPath (Join-Path $Root 'logs\api.pid') -Value $apiProc.Id -NoNewline

if (-not $env:ComSpec) {
  throw 'ComSpec is unset; cmd.exe is required to launch npm without changing execution policy'
}
$webRoot = Join-Path $Root 'apps\web'
$webCmd = "npm run dev -- --host 127.0.0.1 --port $($env:UNLAB_WEB_PORT) --strictPort"
$webProc = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/s', '/c', $webCmd) -WorkingDirectory $webRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $webLog -RedirectStandardError $webErr
Set-Content -LiteralPath (Join-Path $Root 'logs\web.pid') -Value $webProc.Id -NoNewline

$apiUrl = "http://127.0.0.1:$($env:UNLAB_API_PORT)/api/health"
$webUrl = "http://127.0.0.1:$($env:UNLAB_WEB_PORT)/"
if (-not (Wait-Http -Url $apiUrl -Tries 180)) {
  Write-Host 'error: API did not become healthy. See logs/api.log and logs/api.err.log'
  & (Join-Path $Root 'scripts\stop_windows.ps1')
  exit 1
}
if (-not (Wait-Http -Url $webUrl -Tries 180)) {
  Write-Host 'error: Vite did not become ready. See logs/web.log and logs/web.err.log'
  & (Join-Path $Root 'scripts\stop_windows.ps1')
  exit 1
}

Write-Host "api  $apiUrl"
Write-Host "web  $webUrl"
Write-Host "logs $apiLog $webLog"
Write-Host 'stop powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop_windows.ps1'
