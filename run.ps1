param(
    [ValidateSet('demo', 'test', 'benchmark')][string]$Task = 'demo',
    [string]$Scenario = 'all'
)
$ErrorActionPreference = 'Stop'
# Use an installed interpreter when present, with the existing bundled runtime as fallback.
$mosaicPython = Get-Command python -ErrorAction SilentlyContinue
$mosaicExe = if ($mosaicPython) { $mosaicPython.Source } else {
    Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
}
if (-not (Test-Path -LiteralPath $mosaicExe)) {
    throw 'Python was not found. Install Python 3.11 or newer and reopen the terminal.'
}
Push-Location $PSScriptRoot
try {
    if ($Task -eq 'test') {
        & $mosaicExe -m unittest discover -s services/api/tests -v
    } elseif ($Task -eq 'benchmark') {
        & $mosaicExe benchmark.py baseline --text ../../outputs/benchmark-v1/synthetic-bidder.txt --output ../../outputs/benchmark-v2/baseline-report.json
    } else {
        & $mosaicExe demo.py --scenario $Scenario
    }
    $mosaicExit = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $mosaicExit
