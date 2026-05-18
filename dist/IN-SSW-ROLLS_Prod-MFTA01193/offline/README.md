## Offline dependencies (no internet installs)

This folder is intended to keep a **local wheelhouse** inside the repo, so you can install on machines without internet access.

### Folder layout

- `offline/wheels/` – downloaded Python wheels (`*.whl`) for all dependencies (and optionally this project).

### Prepare wheels (on a machine with internet)

From the repo root:

- macOS / Linux:

```bash
# Defaults target Windows Server x64 + CPython 3.13:
bash offline/prepare_wheels.sh

# Optional explicit target override:
TARGET_PLATFORM=win_amd64 TARGET_PYTHON_VERSION=313 TARGET_IMPLEMENTATION=cp TARGET_ABI=cp313 bash offline/prepare_wheels.sh
```

- Windows (PowerShell):

```powershell
.\offline\prepare_wheels.ps1

# Or override target via environment vars before running:
$env:TARGET_PLATFORM = "win_amd64"
$env:TARGET_PYTHON_VERSION = "313"
$env:TARGET_IMPLEMENTATION = "cp"
$env:TARGET_ABI = "cp313"
.\offline\prepare_wheels.ps1
```

### Install offline (on the target machine with no internet)

From the repo root:

- macOS / Linux:

```bash
bash offline/install_offline.sh
```

- Windows (PowerShell):

```powershell
.\offline\install_offline.ps1
```

### Notes

- You must prepare wheels on a machine that matches the target environment (OS + CPU + Python version),
  especially for packages like `lxml` and `watchdog`.
- For Windows offline installs, prepare wheels on Windows with the same Python major/minor version
  as the target (e.g. target Python 3.13 -> prepare with Python 3.13).
- You can also cross-download Windows wheels from macOS/Linux by setting target options
  (defaults in the scripts are already `win_amd64`, `cp313`).
- Offline install scripts do not upgrade pip from the internet; they only install from `offline/wheels/`.
- `colorama` is included explicitly in wheel preparation because `click` depends on it on Windows via platform markers.

