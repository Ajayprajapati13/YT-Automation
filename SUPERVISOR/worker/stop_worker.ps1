<#
Stops the worker process started by start_worker.ps1, using the tracked PID
in worker.pid. Only ever stops that one tracked process id - never a broad
process search.
#>
$ErrorActionPreference = "Stop"

$workerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $workerDir "worker.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "No worker.pid found; worker does not appear to be running."
    exit 0
}

$trackedId = Get-Content $pidFile -ErrorAction SilentlyContinue
if ($trackedId -and (Get-Process -Id $trackedId -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $trackedId
    Write-Host "Stopped worker (PID $trackedId)."
} else {
    Write-Host "Worker process not found (stale PID $trackedId)."
}

Remove-Item $pidFile -ErrorAction SilentlyContinue
