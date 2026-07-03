$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
. .\set-powershell-utf8.ps1
$gptSoVitsRoot = Join-Path $root "GPT-SoVITS"
$logs = Join-Path $gptSoVitsRoot "logs"
$stdout = Join-Path $logs "api-v2-9880.out.log"
$stderr = Join-Path $logs "api-v2-9880.err.log"
$pidFile = Join-Path $root "gptsovits-api.pid"
$launcher = Join-Path $root "scripts\start-gptsovits-api-wsl.sh"
$runtimePython = Join-Path $gptSoVitsRoot "runtime\python.exe"

New-Item -ItemType Directory -Force -Path $logs | Out-Null

$existing = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 9880 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "GPT-SoVITS API already listening on 127.0.0.1:9880"
    return
}

if ((Test-Path $launcher) -and (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    $resolvedLauncher = (Resolve-Path -LiteralPath $launcher).Path
    $launcherDrive = $resolvedLauncher.Substring(0, 1).ToLowerInvariant()
    $launcherTail = ($resolvedLauncher.Substring(2) -replace "\\", "/")
    $wslLauncher = "/mnt/$launcherDrive$launcherTail"

    $process = Start-Process `
        -FilePath "wsl.exe" `
        -ArgumentList @("-e", "bash", $wslLauncher) `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
} elseif (Test-Path $runtimePython) {
    $process = Start-Process `
        -FilePath $runtimePython `
        -ArgumentList @("-X", "utf8", "api_v2.py", "-a", "127.0.0.1", "-p", "9880", "-c", "GPT_SoVITS/configs/tts_infer.yaml") `
        -WorkingDirectory $gptSoVitsRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
} else {
    throw "Could not find a GPT-SoVITS launcher. Expected WSL launcher at $launcher or runtime Python at $runtimePython"
}

Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ASCII
Write-Host "Started GPT-SoVITS API on 127.0.0.1:9880 (PID $($process.Id))"
