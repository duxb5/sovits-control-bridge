$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
. .\set-powershell-utf8.ps1

$logDir = Join-Path $root "logs"
$pidFile = Join-Path $root "sovits-auto-clipboard.pid"
$stdout = Join-Path $logDir "sovits-auto-clipboard.out.log"
$stderr = Join-Path $logDir "sovits-auto-clipboard.err.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (Test-Path $pidFile) {
    $existingPid = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    if ($existingPid -and (Get-Process -Id $existingPid -ErrorAction SilentlyContinue)) {
        Write-Host "SoVITS clipboard auto reader is already running (PID $existingPid)."
        return
    }
    Remove-Item -LiteralPath $pidFile -Force
}

powershell -ExecutionPolicy Bypass -File .\start-gptsovits-api.ps1

$python = (& py -X utf8 -c "import sys; print(sys.executable)").Trim()
if (-not $python) {
    throw "Could not resolve Python executable with py launcher."
}

$processArgs = @("-X", "utf8", ".\sovits-auto-clipboard.py") + $args
$process = Start-Process `
    -FilePath $python `
    -ArgumentList $processArgs `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ASCII
Write-Host "Started SoVITS clipboard auto reader in background (PID $($process.Id))."
Write-Host "Logs:"
Write-Host "  $stdout"
Write-Host "  $stderr"
