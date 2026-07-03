$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
. .\set-powershell-utf8.ps1

py -X utf8 .\sovits-send.py --url http://127.0.0.1:18088/api/agent/speak @args
