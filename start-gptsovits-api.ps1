$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
. .\set-powershell-utf8.ps1
$gptSoVitsRoot = Join-Path $root "GPT-SoVITS"
$python = Join-Path $gptSoVitsRoot "runtime\python.exe"
$logs = Join-Path $gptSoVitsRoot "logs"
$stdout = Join-Path $logs "api-v2-9880.out.log"
$stderr = Join-Path $logs "api-v2-9880.err.log"

if (-not (Test-Path $python)) {
    throw "GPT-SoVITS runtime python not found: $python"
}

New-Item -ItemType Directory -Force -Path $logs | Out-Null

$existing = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 9880 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "GPT-SoVITS API already listening on 127.0.0.1:9880"
    return
}

$process = Start-Process `
    -FilePath $python `
    -ArgumentList @("-X", "utf8", "api_v2.py", "-a", "127.0.0.1", "-p", "9880", "-c", "GPT_SoVITS/configs/tts_infer.yaml") `
    -WorkingDirectory $gptSoVitsRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

Write-Host "Started GPT-SoVITS API on 127.0.0.1:9880 (PID $($process.Id))"
