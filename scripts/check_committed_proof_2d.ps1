# Offline regression check. Read Git blobs as bytes, never checkout text or a
# PowerShell text pipeline, so core.autocrlf cannot change the hashed evidence.
param([string]$Revision = 'HEAD')
$ErrorActionPreference = 'Stop'

function Read-GitBlob([string]$Path) {
    $info = [System.Diagnostics.ProcessStartInfo]::new()
    $info.FileName = 'git'
    $info.WorkingDirectory = Split-Path $PSScriptRoot -Parent
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = $true
    $info.ArgumentList.Add('cat-file')
    $info.ArgumentList.Add('blob')
    $info.ArgumentList.Add("${Revision}:$Path")
    $process = [System.Diagnostics.Process]::Start($info)
    $bytes = [System.IO.MemoryStream]::new()
    try {
        $process.StandardOutput.BaseStream.CopyTo($bytes)
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) { throw "Cannot read Git blob: ${Revision}:$Path" }
        return ,$bytes.ToArray()
    } finally {
        $bytes.Dispose()
        $process.Dispose()
    }
}

$proof = [System.Text.Encoding]::UTF8.GetString(
    (Read-GitBlob 'docs/milestone-2d-phase6-proof.json')
) | ConvertFrom-Json
$actual = [Convert]::ToHexString(
    [System.Security.Cryptography.SHA256]::HashData((Read-GitBlob $proof.live_proof))
).ToLowerInvariant()
if ($actual -cne $proof.live_proof_sha256) {
    throw "Committed proof hash mismatch: actual=$actual recorded=$($proof.live_proof_sha256)"
}
Write-Output "PASS committed_phase5_proof_sha256=$actual"
