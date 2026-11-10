# Stop processes recorded by start_windows.ps1. Not executed on the Linux host.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
foreach ($name in @("logs\api.pid", "logs\web.pid")) {
  if (Test-Path $name) {
    $procId = Get-Content $name | Select-Object -First 1
    if ($procId) {
      Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $name -Force -ErrorAction SilentlyContinue
  }
}
Write-Output "stop_windows.ps1 finished"
