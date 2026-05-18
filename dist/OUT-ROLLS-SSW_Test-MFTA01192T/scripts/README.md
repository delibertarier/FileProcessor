# Scripts

## Production bundle (`prepare_production_bundle.py`)

Builds one **deploy folder per Windows app instance**. Production uses four separate installations:

| Deployment | Role | Test / Prod |
|------------|------|-------------|
| `IN-SSW-ROLLS_Test-MFTA01193T` | XML → CSV (inbound) | Test |
| `IN-SSW-ROLLS_Prod-MFTA01193` | XML → CSV (inbound) | Prod |
| `OUT-ROLLS-SSW_Test-MFTA01192T` | CSV → XML (outbound) | Test |
| `OUT-ROLLS-SSW_Prod-MFTA01192` | CSV → XML (outbound) | Prod |

Each bundle contains **one flow** in `config/flows.yaml` (not the combined dev `flows.yaml` with three flows).

The **`examples/`** folder is always copied in full and is never purged.

### 1. Set your production paths

```bash
cp config/production_paths.example.yaml config/production_paths.yaml
```

Edit `config/production_paths.yaml` under `deployments:` — one block per server install. Paths match your FTP layout (`E:\FTP\AMFT_Test\...` vs `E:\FTP\AMFT\...`, interface ids `MFTA01192T` / `MFTA01193`, etc.).

When `config/flows.yaml` changes locally (new flow name, `file_glob`, sheet name), update the matching **deployment** block here (and `production_paths.example.yaml` in git).

### 2. Build bundles (on your dev machine)

All four:

```bash
python scripts/prepare_production_bundle.py --purge-local-data
```

One deployment:

```bash
python scripts/prepare_production_bundle.py --deployment OUT-ROLLS-SSW_Prod-MFTA01192 --purge-local-data
```

List names:

```bash
python scripts/prepare_production_bundle.py --list-deployments
```

Output (default):

- `dist/IN-SSW-ROLLS_Test-MFTA01193T/`
- `dist/IN-SSW-ROLLS_Prod-MFTA01193/`
- `dist/OUT-ROLLS-SSW_Test-MFTA01192T/`
- `dist/OUT-ROLLS-SSW_Prod-MFTA01192/`

Each folder is a full app copy with its own `config/flows.yaml` and `DEPLOYMENT.txt`.

Zip each folder and copy to the matching server path (e.g. `D:\APPS\IN-SSW-ROLLS_Prod-MFTA01193`).

### 3. Install on the server

Per deployment folder:

```powershell
cd D:\APPS\OUT-ROLLS-SSW_Prod-MFTA01192
.\offline\install_offline.ps1
```

See [INSTALL.md](../INSTALL.md) and [WINDOWS_SERVICE_GUIDE.md](../WINDOWS_SERVICE_GUIDE.md). Use **one Windows service per deployment**, each pointing at that folder’s `config/flows.yaml`.

### 4. Optional: purge FTP output folders (on the server)

From inside **that** deployment’s folder, with `purge_on_server` set for that deployment only:

```powershell
python scripts\prepare_production_bundle.py --deployment OUT-ROLLS-SSW_Prod-MFTA01192 --purge-server-dirs
```

Only empties OUT / error / in_progress for that interface — not `IN` pickup folders.

### Regenerate after changes

```bash
python scripts/prepare_production_bundle.py --purge-local-data
```

Do not hand-edit generated `config/flows.yaml` in bundles; regenerate from `production_paths.yaml`.
