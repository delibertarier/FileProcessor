# Windows Service Guide (Server 2019)

This guide shows how to run FileProcessor in always-on **daemon mode** and automatically restart it on failure using built-in Windows tooling (`sc.exe`).

## Prerequisites

- A working Python environment on the server (ideally a venv).
- FileProcessor code deployed on the server.
- Production/test bundles use absolute FTP paths in `config/flows.yaml`; the service working directory should be the **bundle root** (folder containing `config/`, `file_processor/`, `examples/`).

## Smoke test on test FTP only

After deploying a **test** bundle (`AMFT_Test` paths), run once from the bundle root:

```powershell
py scripts\run_server_test.py --dry-run
py scripts\run_server_test.py
```

This script **refuses production paths**. It clears test input/success/error/in_progress folders, copies `examples/`, processes files, and prints **All good** when clean. See [scripts/README.md](scripts/README.md).

## 1) Identify paths (edit these)

Replace the placeholders below:

- `PYTHON_EXE`:
  - e.g. `C:\FileProcessor\venv\Scripts\python.exe`
- `REPO_ROOT`:
  - e.g. `C:\FileProcessor`
- `CONFIG_YAML`:
  - e.g. `C:\FileProcessor\config\flows.yaml`

## 2) Create the service

Run in an elevated Command Prompt:

```bat
sc create FileProcessorService start= auto ^
  binPath= "cmd /c ""cd /d REPO_ROOT && PYTHON_EXE -m file_processor.cli run-daemon-mode CONFIG_YAML -v"""
```

Notes:
- `cmd /c ""cd /d ... && ...""` is used so `./data/...` paths in `flows.yaml` resolve correctly.
- Replace `REPO_ROOT`, `PYTHON_EXE`, and `CONFIG_YAML` with real paths (including quoting where needed).

## 3) Configure automatic restart (Recovery)

Run:

```bat
sc failure FileProcessorService actions= restart/5000/restart/5000/restart/5000 reset= 0
```

Meaning:
- Restart after 5 seconds, repeat up to 3 times.
- `reset= 0` means the failure counter doesn’t reset (adjust if your ops policy differs).

## 4) Start and verify

Start:

```bat
sc start FileProcessorService
```

Check status:

```bat
sc query FileProcessorService
```

## 5) Logs (recommended)

The app logs via Python’s `logging` to stdout/stderr.

With a Windows Service created using `sc.exe`, stdout/stderr aren’t automatically visible like a terminal.

Two common options:
1. Configure the service to write output to a log file (by redirecting inside `cmd /c`).
2. Switch to NSSM (which can capture stdout/stderr and write them to rotating log files automatically).

If you want (tell me your preferred path), I can provide an updated `binPath=` that redirects output to a file like:
- `C:\FileProcessor\logs\file-processor.log`

## 6) If you want Task Scheduler instead

If `sc.exe` is not allowed in your environment, Task Scheduler can run the same command at startup and optionally restart on failure (less robust than a service).

