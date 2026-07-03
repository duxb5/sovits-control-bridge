$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root "sovits-auto-clipboard.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "SoVITS clipboard auto reader is not registered as running."
    return
}

$pidText = (Get-Content -LiteralPath $pidFile -Raw).Trim()
if (-not $pidText) {
    Remove-Item -LiteralPath $pidFile -Force
    Write-Host "Removed empty PID file."
    return
}

$process = Get-Process -Id $pidText -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $process.Id -Force
    Write-Host "Stopped SoVITS clipboard auto reader (PID $($process.Id))."
} else {
    Write-Host "SoVITS clipboard auto reader process was not running (stale PID $pidText)."
}

Remove-Item -LiteralPath $pidFile -Force
