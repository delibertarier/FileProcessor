#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
WHEEL_DIR="offline/wheels"

mkdir -p "$WHEEL_DIR"

echo "Using Python: $("$PYTHON_BIN" --version)"
echo "Downloading wheels into: $WHEEL_DIR"

"$PYTHON_BIN" -m pip install --upgrade pip

# Download dependencies
"$PYTHON_BIN" -m pip download -r requirements.txt -d "$WHEEL_DIR"

# Download build/install requirements for editable install of this project as a wheel.
# This helps ensure setuptools/build backends are available offline.
"$PYTHON_BIN" -m pip download -d "$WHEEL_DIR" setuptools wheel

echo "Done. Copy the whole repo (including offline/wheels/) to the offline machine."

