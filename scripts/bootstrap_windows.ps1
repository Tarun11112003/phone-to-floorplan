param(
    [string]$EnvironmentDirectory = '.venv',
    [string]$Wheelhouse = '',
    [switch]$WithOpenMVS
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$environmentPath = [IO.Path]::GetFullPath((Join-Path $projectRoot $EnvironmentDirectory))
if (-not $environmentPath.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Environment must stay inside the project directory.'
}
$pythonExecutable = Join-Path $environmentPath 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    & py -3.12 -m venv $environmentPath
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required; environment creation failed.' }
}
& $pythonExecutable --version
if ($LASTEXITCODE -ne 0) { throw 'Existing environment cannot start. Choose a fresh -EnvironmentDirectory; it will not be deleted.' }
$pipOptions = @()
if ($Wheelhouse) { $pipOptions = @('--no-index', '--find-links', $Wheelhouse) }
Push-Location $projectRoot
try {
    & $pythonExecutable -m pip install @pipOptions -r requirements/windows-cpu.txt
    if ($LASTEXITCODE -ne 0) { throw 'Pinned CPU dependencies failed to install.' }
    & $pythonExecutable -m pip install @pipOptions -e '.[capture]'
    if ($LASTEXITCODE -ne 0) { throw 'Project/capture dependencies failed to install.' }
    if ($WithOpenMVS) {
        & $pythonExecutable scripts/install_openmvs.py
        if ($LASTEXITCODE -ne 0) { throw 'Pinned OpenMVS installation failed.' }
    }
    & $pythonExecutable -m floorplan.cli --help
    if ($LASTEXITCODE -ne 0) { throw 'CLI preflight failed.' }
} finally { Pop-Location }
Write-Output 'CPU environment ready. Calibration/raw captures are separate assets. Experimental RGB is not part of this baseline.'
