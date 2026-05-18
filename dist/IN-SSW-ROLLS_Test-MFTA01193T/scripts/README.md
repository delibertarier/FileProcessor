# Scripts

## Production bundle (`prepare_production_bundle.py`)

Builds one deploy folder per Windows app instance (test/prod × inbound/outbound).

| Source | What it provides |
|--------|------------------|
| [`config/flows.yaml`](../config/flows.yaml) | Flow definitions (mode, `file_glob`, mapping sheet, …) |
| [`deployment-examples/<name>/flows.yaml`](deployment-examples/) | Production **IN/OUT paths** only |

The **`examples/`** app folder is always copied in full and is never purged.

### 1. Configure deployments

```bash
cp config/production_paths.example.yaml config/production_paths.yaml
```

Edit `deployments:` — each entry needs:

- `example` — folder under `scripts/deployment-examples/` (defaults to deployment name)
- `flow_names` — list of flow `name` values from `config/flows.yaml`

All listed flows get the **same** directory paths from that example’s `flows.yaml`.

Example: inbound test with two flows sharing `E:\FTP\AMFT_Test\IN\MFTA01193T\...`:

```yaml
IN-SSW-ROLLS_Test-MFTA01193T:
  example: IN-SSW-ROLLS_Test-MFTA01193T
  flow_names:
    - ssw_inbound
    - emcs_arc_all
```

Update paths on the server? Edit the matching file under `scripts/deployment-examples/`, not `config/flows.yaml`.

When you add or change flows in `config/flows.yaml`, update `flow_names` in `production_paths.yaml` for each deployment that should include them.

### 2. Build bundles

```bash
python scripts/prepare_production_bundle.py --purge-local-data
```

One folder:

```bash
python scripts/prepare_production_bundle.py --deployment OUT-ROLLS-SSW_Prod-MFTA01192 --purge-local-data
```

List deployments:

```bash
python scripts/prepare_production_bundle.py --list-deployments
```

Output under `dist/<deployment-name>/` with generated `config/flows.yaml`.

### 3. Install on the server

Per deployment folder — see [INSTALL.md](../INSTALL.md) and [WINDOWS_SERVICE_GUIDE.md](../WINDOWS_SERVICE_GUIDE.md).

### 4. Optional: purge FTP working folders (on server)

```powershell
python scripts\prepare_production_bundle.py --deployment OUT-ROLLS-SSW_Prod-MFTA01192 --purge-server-dirs
```

Purges OUT, error, and in_progress for that example’s paths — not the pickup `IN` folder.

### Regenerate

```bash
python scripts/prepare_production_bundle.py --purge-local-data
```

Do not hand-edit generated `config/flows.yaml` in bundles.
