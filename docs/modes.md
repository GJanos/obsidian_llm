# Workflow Modes

Each mode defines a capability the system can execute. The LLM classifier reads this file to match a user prompt to the correct workflow and extract required parameters.

---

## monthly_summary

Generates a concise, structured summary of all daily notes written during a given month. Notes are collected from `VAULT_PATH/Days/<year>/<MM-MonthName>/`, filtered to `.md` files, and processed through a three-pass LLM pipeline: per-day condensation, batch synthesis, and final consolidation. Output is a flat bullet list written to `output/monthly_summary_YYYY_MM.md`.

**Required Parameters**
- `year` (integer): The 4-digit year, e.g. `2026`.
- `month` (integer): Month number 1–12, e.g. `3` for March.

---

## semantic_search

Searches all Markdown notes in the vault for content semantically related to a query. Each file is scored by the LLM for relevance and the top results are returned with file path and a representative excerpt. Output is written to `output/semantic_search_<timestamp>.md`.

**Required Parameters**
- `query` (string): The topic or question to search for.

**Optional Parameters**
- `folder` (string): Path to search (absolute or relative to vault root). Defaults to the full vault.
- `max_results` (integer, default `5`): Maximum number of results to return.