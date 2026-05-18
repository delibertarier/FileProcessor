# Installation (fresh machine)

This project is a Python CLI + library. These steps assume you have **no Python environment set up yet**.

## 1) Install Python

You need **Python 3.10+**.

- **macOS**
  - Recommended: install via Homebrew:
    - `brew install python`
  - Verify:
    - `python3 --version`

- **Windows**
  - Install from the official installer (make sure you check **“Add Python to PATH”**).
  - Verify in PowerShell:
    - `py --version`

- **Linux**
  - Install via your package manager (names vary: `python3`, `python3-venv`, `python3-pip`).
  - Verify:
    - `python3 --version`

## 2) Create a virtual environment (recommended)

From the project root:

- **macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

- **Windows (PowerShell)**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

## 3) Install dependencies

From the project root:

```bash
pip install -r requirements.txt
```

## Offline installs (no internet access)

If the target system has **no internet access**, use the repo’s built-in wheelhouse folder:

- Prepare wheels on an internet-connected machine:
  - macOS / Linux: `bash offline/prepare_wheels.sh`
  - Windows: `.\offline\prepare_wheels.ps1`
- Copy the **entire repo** (including `offline/wheels/`) to the target machine.
- Install on the offline machine:
  - macOS / Linux: `bash offline/install_offline.sh`
  - Windows: `.\offline\install_offline.ps1`

## 4) Install the CLI (editable install)

From the project root:

```bash
pip install -e .
```

If you see a warning like:

- “The script `file-processor` is installed in … which is not on PATH”

You can either:

- **Add that directory to PATH**, or
- **Run via Python module** (no PATH changes needed):

```bash
python -m file_processor.cli --help
```

## 5) Quick run / test

### Batch mode (process current files then exit)

```bash
file-processor run-once config/flows.yaml -v
```

If the `file-processor` command isn’t on PATH, use:

```bash
python -m file_processor.cli run-once config/flows.yaml -v
```

### Daemon mode (watch folders continuously)

```bash
file-processor run-daemon-mode config/flows.yaml -v
```

Or via module:

```bash
python -m file_processor.cli run-daemon-mode config/flows.yaml -v
```

## Notes / common issues

- **“command not found: file-processor”**
  - Use `python -m file_processor.cli ...` or fix your PATH, then reopen your terminal.
- **Editable install fails with package discovery errors**
  - This repo is configured to package only `file_processor`. If you still see discovery errors, paste the full error output.

