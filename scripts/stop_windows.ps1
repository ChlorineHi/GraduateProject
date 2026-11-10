# Stop processes recorded by start_windows.ps1. Not executed on the Linux host.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)
function Stop-Tree([int]$procId) {
  $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $procId" -ErrorAction SilentlyContinue)
  foreach ($child in $children) {
    Stop-Tree ([int]$child.ProcessId)
  }
  Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}
foreach ($name in @("logs\api.pid", "logs\web.pid")) {
  if (Test-Path $name) {
    $procId = Get-Content $name | Select-Object -First 1
    if ($procId) {
      Stop-Tree ([int]$procId)
    }
    Remove-Item $name -Force -ErrorAction SilentlyContinue
  }
}
Write-Output "stop_windows.ps1 finished"
