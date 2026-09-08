param(
    [int]$Port = 8000,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project virtual environment not found. Create .venv and install requirements-api.txt."
}

$Arguments = @(
    "-m", "uvicorn", "services.api.app.main:app",
    "--host", "127.0.0.1",
    "--port", $Port.ToString()
)
if (-not $NoReload) {
    $Arguments += "--reload"
}

Push-Location $ProjectRoot
try {
    & $Python @Arguments
}
finally {
    Pop-Location
}
