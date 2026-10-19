# رابط PowerShell برای ران‌کنندهٔ cross-platform پروژه (R18)
# استفاده:  .\scripts\dev.ps1 setup | migrate | api | web | check | ...
$RepoRoot = Split-Path -Parent $PSScriptRoot
python (Join-Path $RepoRoot "scripts\dev.py") @args
exit $LASTEXITCODE
