$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "py" }
$WheelDir = "offline\wheels"
$TargetPlatform = if ($env:TARGET_PLATFORM) { $env:TARGET_PLATFORM } else { "win_amd64" }
$TargetPythonVersion = if ($env:TARGET_PYTHON_VERSION) { $env:TARGET_PYTHON_VERSION } else { "313" }
$TargetImplementation = if ($env:TARGET_IMPLEMENTATION) { $env:TARGET_IMPLEMENTATION } else { "cp" }
$TargetAbi = if ($env:TARGET_ABI) { $env:TARGET_ABI } else { "cp313" }

New-Item -ItemType Directory -Force -Path $WheelDir | Out-Null

Write-Host "Using Python:"
& $PythonBin --version
Write-Host "Target platform: $TargetPlatform"
Write-Host "Target Python: $TargetImplementation $TargetPythonVersion ($TargetAbi)"

Write-Host "Upgrading pip..."
& $PythonBin -m pip install --upgrade pip

Write-Host "Downloading dependency wheels into $WheelDir..."
& $PythonBin -m pip download -r requirements.txt -d $WheelDir `
  --only-binary=:all: `
  --platform $TargetPlatform `
  --python-version $TargetPythonVersion `
  --implementation $TargetImplementation `
  --abi $TargetAbi

Write-Host "Downloading setuptools/wheel for offline installs..."
& $PythonBin -m pip download -d $WheelDir setuptools wheel pip `
  --only-binary=:all: `
  --platform $TargetPlatform `
  --python-version $TargetPythonVersion `
  --implementation $TargetImplementation `
  --abi $TargetAbi

# Some platform-marked transitive dependencies (e.g. click -> colorama on Windows)
# may not always be resolved during cross-platform download. Include explicitly.
Write-Host "Downloading Windows-marked transitive dependency colorama..."
& $PythonBin -m pip download -d $WheelDir colorama `
  --only-binary=:all: `
  --platform $TargetPlatform `
  --python-version $TargetPythonVersion `
  --implementation $TargetImplementation `
  --abi $TargetAbi

Write-Host "Done. Copy the whole repo (including offline/wheels/) to the offline machine."

