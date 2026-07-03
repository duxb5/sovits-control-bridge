$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $root "sovits-control.pid"
$apiPidFile = Join-Path $root "gptsovits-api.pid"

function Stop-PidFileProcess($Path, $Name) {
    if (-not (Test-Path $Path)) {
        Write-Host "$Name is not registered as running."
        return
    }

    $pidText = (Get-Content -LiteralPath $Path -Raw).Trim()
    if (-not $pidText) {
        Remove-Item -LiteralPath $Path -Force
        Write-Host "Removed empty $Name PID file."
        return
    }

    $process = Get-Process -Id $pidText -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $process.Id -Force
        Write-Host "Stopped $Name (PID $($process.Id))."
    } else {
        Write-Host "$Name process was not running (stale PID $pidText)."
    }

    Remove-Item -LiteralPath $Path -Force
}

Stop-PidFileProcess $pidFile "SoVITS Voice Bridge"
Stop-PidFileProcess $apiPidFile "GPT-SoVITS API launcher"
