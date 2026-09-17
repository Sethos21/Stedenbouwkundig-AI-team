$ErrorActionPreference = 'Stop'
$python = Get-Item -LiteralPath "$PSScriptRoot/.tools/source-venv/Scripts/python.exe" -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-ChildItem -LiteralPath "$PSScriptRoot/.tools/python" -Filter python.exe -Recurse | Select-Object -First 1
}
if (-not $python) { throw 'Python ontbreekt; zie README.md' }
$env:PYTHONDONTWRITEBYTECODE = '1'
& $python.FullName "$PSScriptRoot/bvc_ai.py" @args
exit $LASTEXITCODE
