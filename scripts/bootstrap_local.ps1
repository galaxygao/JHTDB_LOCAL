param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location -LiteralPath $ProjectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv')) {
        python -m venv .venv
    }
    $Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    & $Python -m pip install --upgrade pip
    & $Python -m pip install --editable '.[dev]'
    & $Python -m compileall -q src
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        throw "Local bootstrap validation failed with exit code $LASTEXITCODE"
    }
    Write-Host "Local environment ready: $ProjectRoot\.venv"
}
finally {
    Pop-Location
}
