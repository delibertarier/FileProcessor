# Ops Guide

## What this software does

FileProcessor runs one or more configured **flows**. Each flow watches an input folder for new files, processes them using a **mapping Excel** (and optional XSD/skeleton for XML validation/template), and then writes outputs to a **success** folder. The original input file is moved to **archive** after success, or to **error** after failure.

It has two main modes:

- `run-once`: process everything currently in the input folders, then exit.
- `run-daemon-mode`: stay running and automatically process files as they arrive.

## Runs/commands (Windows Server)

Use these commands from the repo root (Windows PowerShell):

- One-time run:
  - `py -m file_processor.cli run-once config/flows.yaml -v`
- Daemon mode:
  - `py -m file_processor.cli run-daemon-mode config/flows.yaml -v`

`-v` enables more verbose logging.

For production, run daemon mode as a Windows Service. See `WINDOWS_SERVICE_GUIDE.md`.

### Exact Windows Service commands (`sc.exe`)

Run these in an elevated PowerShell/Command Prompt and replace paths:

```bat
sc create FileProcessorService start= auto ^
  binPath= "cmd /c ""cd /d D:\APPS\FileProcessor && D:\APPS\FileProcessor\.venv\Scripts\python.exe -m file_processor.cli run-daemon-mode config/flows.yaml -v"""
```

Configure automatic restart:

```bat
sc failure FileProcessorService actions= restart/5000/restart/5000/restart/5000 reset= 0
```

Start and verify:

```bat
sc start FileProcessorService
sc query FileProcessorService
sc qc FileProcessorService
```

## Configuration reference (this repo)

The active flow definitions are in `config/flows.yaml`.

### Flow: `rolls_outbound` (CSV → XML)

- Purpose: internal → external (CSV in → XML out)
- Mode: `csv_to_xml`
- Input folder: `./data/outbound/in`
- Filename rule: `file_glob: "*.csv"`
- Delimiter (CSV): `|`
- Mapping Excel: `./examples/mapping ROLLS SSW outgoing.xlsx`
- XML template: `./examples/skeleton_PldaSswDeclaration.xml`
- XSD validation: `./examples/PLDASSW.xsd`
- Output folders:
  - Success XML: `./data/outbound/success`
  - Error XML + diagnostics: `./data/outbound/error`
  - Archive original CSV: `./data/outbound/archive`
  - Processing/transaction: `./data/outbound/in_progress`

### Flow: `rolls_inbound` (XML → CSV)

- Purpose: external → internal (XML in → CSV out)
- Mode: `xml_to_csv`
- Input folder: `./data/inbound/in`
- Filename rule: `file_glob: "*.xml"`
- CSV delimiter for output: `;`
- Mapping Excel: `./examples/mapping ROLLS SSW outgoing.xlsx`
- Output folders:
  - Success CSV: `./data/inbound/success`
  - Error CSV + diagnostics: `./data/inbound/error`
  - Archive original XML: `./data/inbound/archive`
  - Processing/transaction: `./data/inbound/in_progress`

## File lifecycle (transaction model)

For each detected file, FileProcessor uses a transactional approach:

- Step 1: move/rename the input file into `in_progress` (so it won’t be picked up twice)
- Step 2: process the file
- Step 3a (success): write generated output into `success_dir`, then move the original input into `archive_dir`
- Step 3b (failure): move the original input into `error_dir` and persist any generated output for debugging in `error_dir`

Output naming:

- XML outputs are written as `<input-stem>_<suffix>.xml` where `<suffix>` is used when multiple documents are produced.
- CSV outputs are written as `<input-stem>.csv`.

## Daemon mode behavior (run-daemon-mode)

When starting `run-daemon-mode`:

- It performs a **catch-up** scan of the current contents of the input folders and processes any matching files already present.
- Then it starts watching for new files and processes them when they are created in the input folders.

Operational expectation:

- If file producers put files in the folder, they should be fully written before creation/move (to avoid partial reads).
- File name patterns matter: a file that does not match `file_glob` will not be processed.

## How to monitor in production (Windows Server)

### 1) Windows Service basics (keep it running)

Best practice is to run FileProcessor as a Windows Service (via `sc.exe`) with restart-on-failure.
See `WINDOWS_SERVICE_GUIDE.md` for exact commands.

Ops checks:

- `sc query FileProcessorService`
- `sc qc FileProcessorService`

What to look for:

- service state is `RUNNING`
- startup type is automatic
- recovery/restart policy is configured

### 2) Logs on Windows

The app logs to stdout/stderr (Python logging). Depending on service setup, logs should be captured to:

- redirected log file, or
- service log capture tooling.

What to look for:

- repeated “Error processing …” exceptions
- absence of expected “Detected new file …” / “Wrote ... output ...” messages during busy hours

### 3) Folder-based monitoring (most actionable for Ops)

Monitor these directories per flow:

- `in_progress_dir` should not grow indefinitely
- `success_dir` should receive new outputs when inputs arrive
- `error_dir` should receive files only when something is wrong

Suggested alert rules:

- Staleness alert: any file in `in_progress_dir` older than N minutes (example N=15)
- Error alert: any new file appearing in `error_dir` (or error count > threshold in time window)
- Throughput alert: no new files in `success_dir` for longer than expected SLA window

These checks align with the transactional lifecycle described above.

## Common issues and quick checks

- A file is in `in/` but no output appears:
  - filename does not match `file_glob`
  - daemon isn’t running the right flow for that directory
- Input appears in `in_progress/` but never moves:
  - processing stuck or failing repeatedly
  - check service logs for the last stack trace
- Validation failures:
  - `rolls_outbound` validates against XSD; failures will route the input to `error_dir`

## Safe operational actions

- Prefer placing files into the input folder only after they are fully written.
- Use distinct filename patterns for different integrations/types so multiple flows don’t compete for the same file.
- When debugging a single file:
  - inspect the corresponding generated output and any diagnostics in `error_dir`
  - then re-drop the input file once the mapping/template is corrected

