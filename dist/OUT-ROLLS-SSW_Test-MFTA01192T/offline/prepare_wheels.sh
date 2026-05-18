#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
WHEEL_DIR="offline/wheels"
TARGET_PLATFORM="${TARGET_PLATFORM:-win_amd64}"
TARGET_PYTHON_VERSION="${TARGET_PYTHON_VERSION:-313}"
TARGET_IMPLEMENTATION="${TARGET_IMPLEMENTATION:-cp}"
TARGET_ABI="${TARGET_ABI:-cp313}"

mkdir -p "$WHEEL_DIR"

echo "Using Python: $("$PYTHON_BIN" --version)"
echo "Downloading wheels into: $WHEEL_DIR"
echo "Target platform: $TARGET_PLATFORM"
echo "Target Python: $TARGET_IMPLEMENTATION $TARGET_PYTHON_VERSION ($TARGET_ABI)"

"$PYTHON_BIN" -m pip install --upgrade pip

# Download dependencies
"$PYTHON_BIN" -m pip download -r requirements.txt -d "$WHEEL_DIR" \
  --only-binary=:all: \
  --platform "$TARGET_PLATFORM" \
  --python-version "$TARGET_PYTHON_VERSION" \
  --implementation "$TARGET_IMPLEMENTATION" \
  --abi "$TARGET_ABI"

# Download build/install requirements for editable install of this project as a wheel.
# This helps ensure setuptools/build backends are available offline.
"$PYTHON_BIN" -m pip download -d "$WHEEL_DIR" setuptools wheel pip \
  --only-binary=:all: \
  --platform "$TARGET_PLATFORM" \
  --python-version "$TARGET_PYTHON_VERSION" \
  --implementation "$TARGET_IMPLEMENTATION" \
  --abi "$TARGET_ABI"

# Some platform-marked transitive dependencies (e.g. click -> colorama on Windows)
# may not always be resolved during cross-platform download. Include explicitly.
"$PYTHON_BIN" -m pip download -d "$WHEEL_DIR" colorama \
  --only-binary=:all: \
  --platform "$TARGET_PLATFORM" \
  --python-version "$TARGET_PYTHON_VERSION" \
  --implementation "$TARGET_IMPLEMENTATION" \
  --abi "$TARGET_ABI"

echo "Done. Copy the whole repo (including offline/wheels/) to the offline machine."

