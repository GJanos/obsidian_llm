# Workflow Modes

Each mode is defined with its name, description, required parameters, and optional parameters.

---

## semantic_search

**Description**: Search across all Markdown notes in a folder for content semantically related to a query. Returns the most relevant excerpts with file names.

**Required Parameters**:
- `folder` (string): Absolute or relative path to the folder containing .md files.
- `query` (string): The search query or topic to look for.

**Optional Parameters**:
- `max_results` (integer, default 5): Maximum number of results to return.

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

## yearly_summary

**Description**: Summarize all Markdown notes from a specific year. Notes are matched by their file path or filename containing the 4-digit year.

**Required Parameters**:
- `folder` (string): Path to the folder (or vault root) containing .md files.
- `year` (integer): The 4-digit year to filter by.

**Optional Parameters**:
- none

---

## note_cleaner

**Description**: Clean and reformat Markdown notes by fixing formatting, removing duplicate content, standardizing headings, and improving readability. Works on a single file or all .md files in a folder.

**Required Parameters**:
- `target` (string): Path to a single .md file OR a folder containing .md files.

**Optional Parameters**:
- `dry_run` (boolean, default false): If true, print the cleaned content without writing files.
