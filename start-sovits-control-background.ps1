$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
. .\set-powershell-utf8.ps1

$logDir = Join-Path $root "logs"
$pidFile = Join-Path $root "sovits-control.pid"
$stdout = Join-Path $logDir "sovits-control.out.log"
$stderr = Join-Path $logDir "sovits-control.err.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (Test-Path $pidFile) {
    $existingPid = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    if ($existingPid -and (Get-Process -Id $existingPid -ErrorAction SilentlyContinue)) {
        Write-Host "SoVITS Voice Bridge is already running (PID $existingPid)."
        Write-Host "Open: http://127.0.0.1:18088"
        return
    }
    Remove-Item -LiteralPath $pidFile -Force
}

$listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 18088 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    Write-Host "Port 18088 is already listening (PID $($listener.OwningProcess))."
    Write-Host "Open: http://127.0.0.1:18088"
    return
}

powershell -ExecutionPolicy Bypass -File .\start-gptsovits-api.ps1

$python = (& py -X utf8 -c "import sys; print(sys.executable)").Trim()
if (-not $python) {
    throw "Could not resolve Python executable with py launcher."
}

$process = Start-Process `
    -FilePath $python `
    -ArgumentList @("-X", "utf8", ".\sovits-control-server.py") `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ASCII
Write-Host "Started SoVITS Voice Bridge in background (PID $($process.Id))."
Write-Host "Open: http://127.0.0.1:18088"
Write-Host "Logs:"
Write-Host "  $stdout"
Write-Host "  $stderr"
