$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "py" }
$WheelDir = Join-Path (Get-Location) "offline\wheels"

if (-Not (Test-Path $WheelDir)) {
  throw "Missing $WheelDir. Run offline/prepare_wheels.ps1 on an internet-connected machine first."
}

if (-Not (Get-ChildItem -Path $WheelDir -Filter "watchdog-*.whl" -ErrorAction SilentlyContinue)) {
  throw "No watchdog wheel found in $WheelDir. Prepare wheels on a matching Windows + Python environment."
}

Write-Host "Using Python:"
& $PythonBin --version

if (-Not (Test-Path ".venv")) {
  & $PythonBin -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
}

& .\.venv\bin\Activate.ps1
if ($LASTEXITCODE -ne 0) { throw "Failed to activate .venv." }

# Do not upgrade pip online here; this script must stay fully offline.
# (Any required wheels must already exist in offline/wheels.)

Write-Host "Installing dependencies from local wheels..."
pip install --no-index --find-links $WheelDir -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Offline dependency install failed." }

Write-Host "Installing this project (editable) from local files..."
pip install --no-index --find-links $WheelDir -e .
if ($LASTEXITCODE -ne 0) { throw "Offline project install failed." }

Write-Host "Installed packages in .venv:"
python -m pip list
if ($LASTEXITCODE -ne 0) { throw "Failed to list installed packages." }

Write-Host "Done. You can run:"
Write-Host "  python -m file_processor.cli --help"

