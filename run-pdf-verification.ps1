param(
    [Parameter(Mandatory = $true)][string]$TenderPdf,
    [Parameter(Mandatory = $true)][string]$BidderPdf,
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$CaseName,
    [ValidateRange(1, 100)][int]$BatchSize = 10,
    [ValidateRange(1, 100)][int]$TopK = 5,
    [switch]$ForceOcrBidder,
    [switch]$UsePgVector,
    [string]$DatabaseUrl,
    [switch]$Resume
)

$ErrorActionPreference = 'Stop'
$mosaicPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $mosaicPython)) {
    throw 'The MOSAIC .venv is missing. Install requirements-benchmark.txt first.'
}
$resolvedTender = (Resolve-Path -LiteralPath $TenderPdf).Path
$resolvedBidder = (Resolve-Path -LiteralPath $BidderPdf).Path
if ([IO.Path]::GetExtension($resolvedTender) -ne '.pdf' -or
    [IO.Path]::GetExtension($resolvedBidder) -ne '.pdf') {
    throw 'TenderPdf and BidderPdf must both be PDF files.'
}
$caseFolder = Join-Path $PSScriptRoot "artifacts\cases\$CaseName"
if ((Test-Path -LiteralPath $caseFolder) -and -not $Resume) {
    throw "Case '$CaseName' already exists. Choose another name or add -Resume."
}
New-Item -ItemType Directory -Force -Path $caseFolder | Out-Null

$tenderExtraction = Join-Path $caseFolder 'tender-extraction.json'
$criteria = Join-Path $caseFolder 'criteria-from-tender.json'
$bidderExtraction = Join-Path $caseFolder 'bidder-extraction.json'
$index = Join-Path $caseFolder 'bidder-bge-index'
$retrieval = Join-Path $caseFolder 'retrieval-top-k.json'
$report = Join-Path $caseFolder 'verification-report.json'

function Invoke-MosaicStep {
    param([Parameter(Mandatory = $true)][string[]]$StepArguments)
    & $mosaicPython (Join-Path $PSScriptRoot 'benchmark.py') @StepArguments
    if ($LASTEXITCODE -ne 0) {
        throw "MOSAIC stage failed with exit code $LASTEXITCODE."
    }
}

$extractTender = @(
    'extract', $resolvedTender, '--output', $tenderExtraction,
    '--batch-size', [string]$BatchSize
)
if ($Resume) { $extractTender += '--resume' }
Invoke-MosaicStep $extractTender

$extractCriteria = @(
    'extract-criteria', '--records', $tenderExtraction, '--pdf', $resolvedTender,
    '--output', $criteria
)
if ($Resume) { $extractCriteria += '--resume' }
Invoke-MosaicStep $extractCriteria

$extractBidder = @(
    'extract', $resolvedBidder, '--output', $bidderExtraction,
    '--batch-size', [string]$BatchSize
)
if ($ForceOcrBidder) { $extractBidder += '--force-ocr' }
if ($Resume) { $extractBidder += '--resume' }
Invoke-MosaicStep $extractBidder

if ($UsePgVector) {
    if ($DatabaseUrl) { $env:MOSAIC_DATABASE_URL = $DatabaseUrl }
    if (-not $env:MOSAIC_DATABASE_URL) {
        throw 'UsePgVector requires -DatabaseUrl or the MOSAIC_DATABASE_URL environment variable.'
    }
    if ((Test-Path -LiteralPath $report) -and $Resume) {
        Write-Host "Verification already complete. Report: $report"
        exit 0
    }
    Invoke-MosaicStep @(
        'verify', '--records', $bidderExtraction, '--criteria', $criteria,
        '--pdf', $resolvedBidder, '--top-k', [string]$TopK, '--output', $report
    )
    Write-Host "Verification finished with PostgreSQL+pgvector. Report: $report"
    exit 0
}

if (-not (Test-Path -LiteralPath $index)) {
    Invoke-MosaicStep @(
        'embed', '--provider', 'ollama', '--records', $bidderExtraction,
        '--output', $index, '--batch-size', '8'
    )
}
if (-not (Test-Path -LiteralPath $retrieval)) {
    Invoke-MosaicStep @(
        'retrieve', '--index', $index, '--criteria', $criteria,
        '--top-k', [string]$TopK, '--output', $retrieval
    )
}

$verify = @(
    'verify-local', '--index', $index, '--criteria', $criteria,
    '--pdf', $resolvedBidder, '--top-k', [string]$TopK, '--output', $report
)
if ($Resume) { $verify += '--resume' }
Invoke-MosaicStep $verify

Write-Host "Verification finished. Report: $report"
