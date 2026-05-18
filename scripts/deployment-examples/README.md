# Deployment example `flows.yaml` files

Reference **production folder paths** (from your server configs).  
The bundle script reads `input_dir`, `success_dir`, `error_dir`, `archive_dir`, and `in_progress_dir` from the **first flow** in each file here.

Flow settings (`file_glob`, mapping sheet, mode, …) come from [`config/flows.yaml`](../../config/flows.yaml) — see `config/production_paths.yaml` for which flow names each deployment uses.

| Folder | Role |
|--------|------|
| `IN-SSW-ROLLS_Test-MFTA01193T` | Inbound test |
| `IN-SSW-ROLLS_Prod-MFTA01193` | Inbound prod |
| `OUT-ROLLS-SSW_Test-MFTA01192T` | Outbound test |
| `OUT-ROLLS-SSW_Prod-MFTA01192` | Outbound prod |

If a deployment runs multiple flows (e.g. `ssw_inbound` and `emcs_arc_all`), they all use the same paths from the matching IN or OUT example file.
