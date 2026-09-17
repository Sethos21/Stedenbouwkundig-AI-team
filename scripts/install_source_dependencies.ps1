$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$basePython = Join-Path $projectRoot '.tools/python/cpython-3.12.14-windows-x86_64-none/python.exe'
if (-not (Test-Path -LiteralPath $basePython)) { throw 'Projectlokale Python 3.12 ontbreekt; zie README.md' }
$localTemp = Join-Path $projectRoot '.tools/install-temp'
New-Item -ItemType Directory -Force -Path $localTemp | Out-Null
$oldTemp = $env:TEMP
$oldTmp = $env:TMP
try {
    $env:TEMP = $localTemp
    $env:TMP = $localTemp
    $python = Join-Path $projectRoot '.tools/source-venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        & $basePython -B -m venv "$projectRoot/.tools/source-venv"
        if ($LASTEXITCODE -ne 0) { throw 'Aanmaken projectlokale venv mislukt' }
    }
    & $python -B -m pip --isolated --disable-pip-version-check install --no-user --no-compile --only-binary=:all: --cache-dir "$projectRoot/.tools/pip-cache" --requirement "$projectRoot/requirements.txt"
    if ($LASTEXITCODE -ne 0) { throw 'Installatie bronvalidatie-dependencies mislukt' }
    & $python -B -c "import sys, platform, struct, shapely, numpy; print(sys.version); print(platform.system(), platform.machine(), struct.calcsize('P') * 8); print('Shapely', shapely.__version__, 'GEOS', shapely.geos_version_string, 'NumPy', numpy.__version__); print(shapely.__file__); print(numpy.__file__)"
    if ($LASTEXITCODE -ne 0) { throw 'Dependency-import mislukt' }
} finally {
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
}
