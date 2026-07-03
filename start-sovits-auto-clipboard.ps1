$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
. .\set-powershell-utf8.ps1

powershell -ExecutionPolicy Bypass -File .\start-gptsovits-api.ps1
py -X utf8 .\sovits-auto-clipboard.py @args
