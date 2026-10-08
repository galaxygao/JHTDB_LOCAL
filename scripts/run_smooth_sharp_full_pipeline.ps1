param(
    [int]$TimeIndex = 1,
    [double[]]$SigmaGrids = @(10, 15, 30, 55, 75),
    [double]$SharpEdgeWidthFraction = 0.1171875,
    [string]$Config = 'configs/pipeline.yaml',
    [switch]$WithPressureGradient
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

function Invoke-Python {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Virtual-environment Python was not found: $Python"
}

Push-Location -LiteralPath $ProjectRoot
try {
    $ConfigPath = (Resolve-Path -LiteralPath $Config).Path

    # single-frame performs doctor, download/cache validation, all physics fields,
    # QA and atomic finalization. Completed sigma results are reused.
    $PipelineArguments = @(
        '-m', 'jhtdb_pipeline', 'single-frame',
        '--time-index', "$TimeIndex",
        '--sigma-grids'
    )
    $PipelineArguments += $SigmaGrids | ForEach-Object { "$_" }
    $PipelineArguments += @(
        '--filter-type', 'smooth_sharp',
        '--sharp-edge-width-fraction', "$SharpEdgeWidthFraction",
        '--config', $ConfigPath
    )
    if ($WithPressureGradient) { $PipelineArguments += '--with-pressure-gradient' }
    Invoke-Python $PipelineArguments

    Invoke-Python @('-m', 'jhtdb_pipeline', 'status', '--config', $ConfigPath)
    Write-Host "Main multi-sigma pipeline completed."
}
finally {
    Pop-Location
}
