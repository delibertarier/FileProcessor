# Data folder layout

Organise by **direction**: internal ↔ external.

## Outbound (internal → external)

**CSV from your systems → XML for external systems.**

- `outbound/in/` — Drop CSV files here. They are processed and converted to XML.
- `outbound/success/` — Generated XML and original CSV after successful processing.
- `outbound/error/` — Failed runs: original file + any generated output for debugging.
- `outbound/archive/` — Optional long-term storage of processed files.
- `outbound/in_progress/` — Files currently being processed (transactional).

## Inbound (external → internal)

**XML from external systems → CSV for your systems.**

- `inbound/in/` — Drop XML files here. They are converted to CSV.
- `inbound/success/` — Generated CSV (and original XML) after successful processing.
- `inbound/error/` — Failed runs: original file + diagnostics.
- `inbound/archive/` — Optional long-term storage.
- `inbound/in_progress/` — Files currently being processed.

## Summary

| Direction  | Input format | Output        | Input folder      | Generated output   | Original file after success |
|-----------|--------------|---------------|-------------------|--------------------|-----------------------------|
| Outbound  | CSV          | XML           | `outbound/in/`    | `outbound/success/` | `outbound/archive/`          |
| Inbound   | XML          | CSV           | `inbound/in/`     | `inbound/success/`  | `inbound/archive/`           |

Use one flow in `config/flows.yaml` for outbound (e.g. `rolls_flow`) and one for inbound (e.g. `rolls_inbound`), each pointing at these directories. The processor writes **generated** files (XML or CSV) into the success dir and moves the **original** input file into the archive dir after a successful run.
