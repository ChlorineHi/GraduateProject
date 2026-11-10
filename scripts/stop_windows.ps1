# Stop the API and Vite processes recorded under logs/.
# Signals only those pid files, and only when the command line is this app.
# Does not free a port by killing whatever else is listening.
# Does not call Set-ExecutionPolicy.
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop_windows.ps1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Stop-RecordedProcess {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Pattern
  )
  $pidFile = Join-Path $Root "logs\$Name.pid"
  if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "${Name}: no pid file"
    return
  }
  $text = (Get-Content -LiteralPath $pidFile -Raw).Trim()
  if ($text -notmatch '^[0-9]+$' -or [int]$text -le 1) {
    throw "$Name pid file is invalid"
  }
  $procId = [int]$text
  $running = Get-Process -Id $procId -ErrorAction SilentlyContinue
  if ($null -eq $running) {
    Remove-Item -LiteralPath $pidFile -Force
    Write-Host "${Name}: stale pid $procId removed"
    return
  }
  $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$procId"
  $commandLine = [string]$cim.CommandLine
  if ($commandLine -notmatch $Pattern) {
    throw "refusing to signal $Name pid ${procId}; command line does not match this app: $commandLine"
  }
  & taskkill.exe /PID $procId /T | Out-Host
  $gone = $false
  for ($i = 0; $i -lt 50; $i++) {
    if (-not (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
      $gone = $true
      break
    }
    Start-Sleep -Milliseconds 200
  }
  if (-not $gone) {
    & taskkill.exe /PID $procId /T /F | Out-Host
    Start-Sleep -Milliseconds 300
  }
  if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
    throw "$Name pid $procId is still running"
  }
  if (Test-Path -LiteralPath $pidFile) {
    Remove-Item -LiteralPath $pidFile -Force
  }
  Write-Host "${Name}: stopped $procId"
}

Stop-RecordedProcess -Name web -Pattern 'vite|npm'
Stop-RecordedProcess -Name api -Pattern 'urbannoise\.api:app'
Write-Host 'stop complete'
