# Scripts

## Dev smoke test (`run_dev_test.py`)

From the repo root:

```bash
.venv/bin/python scripts/run_dev_test.py
.venv/bin/python scripts/run_dev_test.py -v
.venv/bin/python scripts/run_dev_test.py --outbound-only
.venv/bin/python scripts/run_dev_test.py --skip-run   # purge + copy examples only
```

Exit code `1` if any file ends up in an `error/` folder (e.g. known EMCS namespace issue on `ARC_ALL*.xml`).

1. Clears `data/` (keeps `.gitkeep`)
2. Copies `examples/out/TRA*.TXT` → `data/outbound/in/`
3. Copies `examples/in/SSW/TE_FELUY_*.xml` and `examples/in/EMCS/ARC_ALL*.xml` → `data/inbound/in/`
4. Runs `run_once` for all flows in `config/flows.yaml`
5. Prints counts under success / error / archive

## Production bundle (`prepare_production_bundle.py`)

Builds one deploy folder per Windows app instance.

| Source | Role |
|--------|------|
| [`deployment-examples/<name>/flows.yaml`](deployment-examples/) | **Test/prod paths** (always used) |
| [`config/flows.yaml`](../config/flows.yaml) | Flow settings, filtered by direction |

| Deployment | Flows taken from config |
|------------|-------------------------|
| `IN-*` (incoming) | `xml_to_csv` only |
| `OUT-*` (outgoing) | `csv_to_xml` only |

The **`examples/`** app folder is always copied in full. **Production FTP folders are never purged** by this script.

### 1. Configure

```bash
cp config/production_paths.example.yaml config/production_paths.yaml
```

List deployments (names match folders under `scripts/deployment-examples/`).  
`flow_names` is optional — by default all flows with the correct mode are included.

### 2. Build

```bash
python scripts/prepare_production_bundle.py --purge-local-data
```

If `dist/<deployment>/` already exists, the script asks before overwriting. Use `--force` to replace without prompting (required in non-interactive shells).

### 3. Verify

```bash
# Inbound test: two xml_to_csv flows, same FTP paths
cat dist/IN-SSW-ROLLS_Test-MFTA01193T/config/flows.yaml

# Outbound prod: csv_to_xml only
cat dist/OUT-ROLLS-SSW_Prod-MFTA01192/config/flows.yaml
```

### 4. Deploy

Zip each `dist/<deployment-name>/` to the matching server folder. See [INSTALL.md](../INSTALL.md).

`--purge-local-data` only clears the dev `data/` skeleton inside the bundle zip, not files on the server.

### Path or flow changes

- **FTP paths** → edit `scripts/deployment-examples/<deployment>/flows.yaml`
- **Mapping / file_glob** → edit `config/flows.yaml`, rebuild

Do not hand-edit generated `config/flows.yaml` in bundles.
