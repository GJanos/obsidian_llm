# Workflow Modes

Each mode is defined with its name, description, required parameters, and optional parameters.

---

## monthly_summary

**Description**: Summarize all Markdown notes from a specific year and month. Notes are matched by their file path or filename containing a date pattern such as YYYY-MM, YYYY/MM, or a filename starting with YYYY-MM.

**Required Parameters**:
- `folder` (string): Path to the folder (or vault root) containing .md files.
- `year` (integer): The 4-digit year to filter by (e.g. 2026).
- `month` (integer): The month number to filter by, 1-12 (e.g. 3 for March).

**Optional Parameters**:
- none

---
