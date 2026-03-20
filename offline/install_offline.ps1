$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "py" }
$WheelDir = "offline\wheels"

if (-Not (Test-Path $WheelDir)) {
  throw "Missing $WheelDir. Run offline/prepare_wheels.ps1 on an internet-connected machine first."
}

Write-Host "Using Python:"
& $PythonBin --version

if (-Not (Test-Path ".venv")) {
  & $PythonBin -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

Write-Host "Installing dependencies from local wheels..."
pip install --no-index --find-links $WheelDir -r requirements.txt

Write-Host "Installing this project (editable) from local files..."
pip install --no-index --find-links $WheelDir -e .

Write-Host "Done. You can run:"
Write-Host "  python -m file_processor.cli --help"

