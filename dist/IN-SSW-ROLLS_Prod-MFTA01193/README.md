# FileProcessor

A configurable engine for translating CSV or fixed-width text files to XML (and back), with:

- Multiple **flows**, each defining:
  - Source folder and file format
  - Delimiter or fixed-width layout
  - Mapping XLS file (first sheet contains mapping)
  - Grouping and filtering rules
  - Output folder and XSD for validation
- Folder watching, transactional-style processing, and logging.

## High-level concepts

- **Flow**: A configuration object that ties together:
  - Source directory, archive directory, error directory
  - Source file format (CSV or fixed-width)
  - Delimiter (for CSV) or fixed-width column specs
  - Mapping XLS file path
  - Optional XSD path for XML validation
  - Optional row filters and grouping rules.
-- **Mapping XLS** (first sheet):
  - Column 1: **source column index** in the CSV (1-based; empty rows are skipped).
  - Column 2: **target XPath** in the XML document (stream column).
  - Columns 3–5: free for codes/remarks (ignored by the loader).
  - Column 6 (F): **transformation rule name** for that field (e.g. `first_3`, `skip`).

### Field conversions (via transforms)

Use **column 6 (F)** in the mapping XLS to apply a conversion before writing the value to XML/CSV. Examples:

| Transform name        | Use case                          | Example input → output        |
|-----------------------|-----------------------------------|-------------------------------|
| `identity`            | No change (default)               | `foo` → `foo`                 |
| `strip`               | Trim whitespace                   | `  bar  ` → `bar`             |
| `first_3`             | First 3 characters only           | `ABCDEFG` → `ABC`             |

Put the transform name in **column 6 (F)** on the same row as the source column and XPath. Unknown names fall back to `identity`. Custom transforms can be added in `file_processor/transformations.py` and made available via the `TRANSFORMATIONS` dict or dynamic names like `first_3`, `first_10`, etc.

## How the app works (for non-technical users)

Think of the app as a **mail-sorting machine for files**:

- **Inbox folders**: Where new files arrive (CSV or XML).
- **Sorting rules**: A mapping Excel file that tells the app which pieces of information go where.
- **Converters**: Optional rules to clean up or reformat values (for example, changing date formats).
- **Outbox folders**: Where the transformed files are delivered.
- **Archive and error folders**: Where original files are stored after processing or when something goes wrong.

Visually, each flow behaves like this:

```mermaid
flowchart LR
    A[Input folder<br/>(CSV or XML)] --> B[FileProcessor app]
    B --> C[Read file line by line<br/>or XML element by element]
    C --> D[Apply mapping rules<br/>(from Excel)]
    D --> E[Apply conversions<br/>(e.g. date format)]
    E --> F[Build new file<br/>(XML or CSV)]
    F --> G[Validate (if XML + XSD)]
    G -->|OK| H[Write result to<br/>Success folder]
    G -->|Error| I[Write file and details<br/>to Error folder]
    A --> J[Original file moved to<br/>Archive folder after success]
```

- **You control** where the inbox/outbox/archive/error folders are and which mapping Excel is used by editing `config/flows.yaml`.
- The same engine can run multiple flows in parallel (for different partners or file types), each with its own folders and mapping file.

