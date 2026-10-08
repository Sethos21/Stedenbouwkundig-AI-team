[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Peildatum,
    [Parameter(Mandatory = $true)][string]$BeschikbaarOp,
    [string]$DocumentIdentity,
    [switch]$Live
)
$ErrorActionPreference = 'Stop'
if (-not $Live) { throw 'Live opt-in vereist: gebruik -Live na de code-review.' }
if (-not $env:DSO_API_KEY) { throw 'DSO_API_KEY ontbreekt in deze PowerShell-omgeving.' }
$root = Split-Path -Parent $PSScriptRoot
$python = Get-Item -LiteralPath "$root/.tools/source-venv/Scripts/python.exe" -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-ChildItem -LiteralPath "$root/.tools/python" -Filter python.exe -Recurse | Select-Object -First 1
}
if (-not $python) { throw 'Lokale Python ontbreekt; zie README.md.' }
$arguments = @('-B', "$PSScriptRoot/dso_phase2_probe.py", '--live', '--peildatum', $Peildatum, '--beschikbaar-op', $BeschikbaarOp)
if ($DocumentIdentity) { $arguments += @('--document-identity', $DocumentIdentity) }
# The child inherits the environment. Never put the credential in arguments or output.
& $python.FullName @arguments
if ($LASTEXITCODE -ne 0) { throw 'DSO-test gestopt; geschoonde status staat hierboven.' }
