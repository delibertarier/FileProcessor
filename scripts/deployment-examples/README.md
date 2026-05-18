# Deployment example `flows.yaml` files

These are your **actual test and production server configs** (folder paths on Windows FTP).

The bundle script always reads directory paths from here and applies them to flows taken from [`config/flows.yaml`](../../config/flows.yaml):

| Deployment folder | Direction | Modes included from config |
|-------------------|-----------|----------------------------|
| `IN-*` | Incoming | `xml_to_csv` only |
| `OUT-*` | Outgoing | `csv_to_xml` only |

Paths are read from the **first flow** in each example file; every included flow on that instance shares those folders.

| Folder | Environment |
|--------|-------------|
| `IN-SSW-ROLLS_Test-MFTA01193T` | Inbound test |
| `IN-SSW-ROLLS_Prod-MFTA01193` | Inbound prod |
| `OUT-ROLLS-SSW_Test-MFTA01192T` | Outbound test |
| `OUT-ROLLS-SSW_Prod-MFTA01192` | Outbound prod |

When FTP paths change on a server, update the matching file here and rebuild the bundle.
