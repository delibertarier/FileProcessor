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
- **Mapping XLS** (first sheet):
  - Column 1: **source column index** in the CSV (1-based; `0` or empty for constants).
  - Column 2: **target XPath** in the XML document.
  - Column 3 (optional): **transformation rule name** (e.g. `date_yyyyMMdd_to_iso`).
  - Column 4 (optional): **constant value** (used when column 1 is `0` or empty).

These conventions can be extended in code without changing runtime configuration.

