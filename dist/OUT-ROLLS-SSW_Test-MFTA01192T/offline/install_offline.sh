#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
WHEEL_DIR="offline/wheels"

if [[ ! -d "$WHEEL_DIR" ]]; then
  echo "Missing $WHEEL_DIR. Run offline/prepare_wheels.sh on an internet-connected machine first."
  exit 1
fi

if ! ls "$WHEEL_DIR"/watchdog-*.whl >/dev/null 2>&1; then
  echo "No watchdog wheel found in $WHEEL_DIR."
  echo "Prepare wheels on a matching OS + Python environment first."
  exit 1
fi

echo "Using Python: $("$PYTHON_BIN" --version)"

# Create venv if needed
if [[ ! -d ".venv" ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
# Do not upgrade pip online here; this script must stay fully offline.

echo "Installing dependencies from local wheels..."
pip install --no-index --find-links "$WHEEL_DIR" -r requirements.txt

echo "Installing this project (editable) from local files..."
pip install --no-index --find-links "$WHEEL_DIR" -e .

echo "Done. You can run:"
echo "  python -m file_processor.cli --help"

