$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root "sovits-control.pid"
$apiPidFile = Join-Path $root "gptsovits-api.pid"
$stdout = Join-Path $root "logs\sovits-control.out.log"
$stderr = Join-Path $root "logs\sovits-control.err.log"
$apiStdout = Join-Path $root "GPT-SoVITS\logs\api-v2-9880.out.log"
$apiStderr = Join-Path $root "GPT-SoVITS\logs\api-v2-9880.err.log"

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

$apiListener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 9880 -State Listen -ErrorAction SilentlyContinue
if ($apiListener) {
    Write-Host "GPT-SoVITS API: port 9880 is listening (PID $($apiListener.OwningProcess))"
} elseif (Test-Path $apiPidFile) {
    $apiPidText = (Get-Content -LiteralPath $apiPidFile -Raw).Trim()
    $apiProcess = Get-Process -Id $apiPidText -ErrorAction SilentlyContinue
    if ($apiProcess) {
        Write-Host "GPT-SoVITS API: launcher running (PID $apiPidText), but port 9880 is not listening yet"
    } else {
        Write-Host "GPT-SoVITS API: not running (stale PID $apiPidText)"
    }
} else {
    Write-Host "GPT-SoVITS API: not running"
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

if (Test-Path $apiStdout) {
    Write-Host ""
    Write-Host "Recent GPT-SoVITS stdout:"
    Get-Content -LiteralPath $apiStdout -Tail 20
}

if (Test-Path $apiStderr) {
    Write-Host ""
    Write-Host "Recent GPT-SoVITS stderr:"
    Get-Content -LiteralPath $apiStderr -Tail 20
}
