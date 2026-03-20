$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "py" }
$WheelDir = "offline\wheels"

New-Item -ItemType Directory -Force -Path $WheelDir | Out-Null

Write-Host "Using Python:"
& $PythonBin --version

Write-Host "Upgrading pip..."
& $PythonBin -m pip install --upgrade pip

Write-Host "Downloading dependency wheels into $WheelDir..."
& $PythonBin -m pip download -r requirements.txt -d $WheelDir

Write-Host "Downloading setuptools/wheel for offline installs..."
& $PythonBin -m pip download -d $WheelDir setuptools wheel

Write-Host "Done. Copy the whole repo (including offline/wheels/) to the offline machine."

