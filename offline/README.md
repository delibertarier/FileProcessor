## Offline dependencies (no internet installs)

This folder is intended to keep a **local wheelhouse** inside the repo, so you can install on machines without internet access.

### Folder layout

- `offline/wheels/` – downloaded Python wheels (`*.whl`) for all dependencies (and optionally this project).

### Prepare wheels (on a machine with internet)

From the repo root:

- macOS / Linux:

```bash
bash offline/prepare_wheels.sh
```

- Windows (PowerShell):

```powershell
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
  especially for packages like `lxml`.

