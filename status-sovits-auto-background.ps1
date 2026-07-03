$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root "sovits-auto-clipboard.pid"
$stdout = Join-Path $root "logs\sovits-auto-clipboard.out.log"
$stderr = Join-Path $root "logs\sovits-auto-clipboard.err.log"

if (Test-Path $pidFile) {
    $pidText = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    $process = Get-Process -Id $pidText -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "SoVITS clipboard auto reader: running (PID $pidText)"
    } else {
        Write-Host "SoVITS clipboard auto reader: not running (stale PID $pidText)"
    }
} else {
    Write-Host "SoVITS clipboard auto reader: not running"
}

if (Test-Path $stdout) {
    Write-Host ""
    Write-Host "Recent stdout:"
    Get-Content -LiteralPath $stdout -Tail 20
}

if (Test-Path $stderr) {
    Write-Host ""
    Write-Host "Recent stderr:"
    Get-Content -LiteralPath $stderr -Tail 20
}
