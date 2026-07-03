$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.Console]::InputEncoding = $utf8NoBom
[System.Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:PYTHONUTF8 = "1"
chcp 65001 | Out-Null
