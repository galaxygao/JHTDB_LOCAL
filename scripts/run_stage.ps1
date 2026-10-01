param(
    [ValidateSet('single-frame')]
    [string]$Stage = 'single-frame',
    [Parameter(Mandatory = $true)]
    [int]$TimeIndex,
    [Nullable[double]]$SigmaGrid,
    [string]$Config = 'configs/pipeline.yaml',
    [switch]$WithPressureGradient
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Arguments = @('-m', 'jhtdb_pipeline', $Stage, '--time-index', $TimeIndex, '--config', $Config)
if ($WithPressureGradient) { $Arguments += '--with-pressure-gradient' }
if ($null -ne $SigmaGrid) {
    $Arguments += @('--sigma-grid', $SigmaGrid)
}

Push-Location -LiteralPath $ProjectRoot
try {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "jhtdb-pipeline failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
