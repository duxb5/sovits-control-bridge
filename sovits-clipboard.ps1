$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
. .\set-powershell-utf8.ps1

$text = Get-Clipboard -Raw
if ([string]::IsNullOrWhiteSpace($text)) {
    throw "Clipboard text is empty."
}

$text | py -X utf8 .\sovits-say.py @args
