<#
Starts SUPERVISOR/worker/task_worker.py as a background polling process.

Safe to run multiple times: if worker.pid already points at a live process,
this is a no-op. Logs go to logs/task_worker.log (repo root); the current
lifecycle state is always visible in SUPERVISOR/STATUS.md.
#>
$ErrorActionPreference = "Stop"

$workerDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $workerDir)
$pidFile = Join-Path $workerDir "worker.pid"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

if (Test-Path $pidFile) {
    $existingId = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($existingId -and (Get-Process -Id $existingId -ErrorAction SilentlyContinue)) {
        Write-Host "Worker already running (PID $existingId)."
        exit 0
    }
}

$proc = Start-Process -FilePath $python `
    -ArgumentList @((Join-Path $workerDir "task_worker.py")) `
    -WorkingDirectory $workerDir `
    -WindowStyle Hidden `
    -PassThru

$proc.Id | Out-File -FilePath $pidFile -Encoding ascii
Write-Host "Worker started (PID $($proc.Id))."
Write-Host "Status: $(Join-Path $repoRoot 'SUPERVISOR\STATUS.md')"
Write-Host "Log:    $(Join-Path $repoRoot 'logs\task_worker.log')"
