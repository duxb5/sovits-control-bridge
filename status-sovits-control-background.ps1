$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root "sovits-control.pid"
$stdout = Join-Path $root "logs\sovits-control.out.log"
$stderr = Join-Path $root "logs\sovits-control.err.log"

if (Test-Path $pidFile) {
    $pidText = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    $process = Get-Process -Id $pidText -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "SoVITS Voice Bridge: running (PID $pidText)"
    } else {
        Write-Host "SoVITS Voice Bridge: not running (stale PID $pidText)"
    }
} else {
    $listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 18088 -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        Write-Host "SoVITS Voice Bridge: port 18088 is listening (PID $($listener.OwningProcess))"
    } else {
        Write-Host "SoVITS Voice Bridge: not running"
    }
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
