param(
    [int]$TimeIndex = 1,
    [double[]]$SigmaGrids = @(10, 15, 30, 55, 75),
    [double]$SharpEdgeWidthFraction = 0.1171875,
    [int]$BlocksPerAxis = 16,
    [string]$Config = 'configs/pipeline.yaml',
    [switch]$OverwriteBlockStatistics,
    [switch]$WithPressureGradient
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$BlockOutputRoot = Join-Path $ProjectRoot 'block_statistics\output'
$BlockScratchRoot = Join-Path $ProjectRoot 'block_statistics\.scratch'

function Invoke-Python {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code ${LASTEXITCODE}: $($Arguments -join ' ')"
    }
}

function Get-SigmaTag {
    param([double]$Value)
    return $Value.ToString('G8', [Globalization.CultureInfo]::InvariantCulture).
        Replace('-', 'm').Replace('.', 'p')
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

    # This separate full-domain report feeds the per-regime section of the
    # GUI's Weak asymmetry page. It is also resumable by result manifest hash.
    $RegimePiArguments = @(
        '-m', 'jhtdb_pipeline', 'compute-regime-pi',
        '--time-index', "$TimeIndex",
        '--sigma-grids'
    )
    $RegimePiArguments += $SigmaGrids | ForEach-Object { "$_" }
    $RegimePiArguments += @(
        '--filter-type', 'smooth_sharp',
        '--sharp-edge-width-fraction', "$SharpEdgeWidthFraction",
        '--config', $ConfigPath
    )
    Invoke-Python $RegimePiArguments

    # Block work is intentionally serial: each sigma uses the same scratch area
    # and computes exact full-domain SijSij without spatial sampling.
    foreach ($Sigma in $SigmaGrids) {
        $BlockArguments = @(
            'block_statistics\compute_block_statistics.py',
            '--time-index', "$TimeIndex",
            '--sigma-grid', "$Sigma",
            '--filter-type', 'smooth_sharp',
            '--sharp-edge-width-fraction', "$SharpEdgeWidthFraction",
            '--blocks-per-axis', "$BlocksPerAxis",
            '--output-root', $BlockOutputRoot,
            '--scratch-root', $BlockScratchRoot,
            '--config', $ConfigPath
        )
        if ($OverwriteBlockStatistics) {
            $BlockArguments += '--overwrite'
        }
        Invoke-Python $BlockArguments

        $FrameTag = 't{0:D6}' -f $TimeIndex
        $FractionTag = Get-SigmaTag $SharpEdgeWidthFraction
        $SigmaTag = Get-SigmaTag $Sigma
        $ResultId = "${FrameTag}_filter_smooth_sharp_a${FractionTag}kc_sigma_${SigmaTag}"
        $BlockDirectory = Join-Path $BlockOutputRoot $ResultId
        Invoke-Python @(
            'block_statistics\plot_vs_strain.py',
            '--input', $BlockDirectory
        )
    }

    Invoke-Python @('-m', 'jhtdb_pipeline', 'status', '--config', $ConfigPath)
    Write-Host "Full multi-sigma pipeline completed. Block outputs: $BlockOutputRoot"
}
finally {
    Pop-Location
}
