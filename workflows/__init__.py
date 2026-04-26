import sys

import config
from . import monthly_summary, semantic_search

WORKFLOWS = {
    "semantic_search": lambda p: semantic_search.run(
        folder=p.get("folder", ""), query=p["query"], max_results=int(p.get("max_results", 5))
    ),
    "monthly_summary": lambda p: monthly_summary.run(
        year=int(p["year"]), month=int(p["month"])
    ),
}


def run_workflow(mode: str, params: dict) -> None:
    """Look up the workflow for the given mode name and execute it with the resolved params."""
    if mode not in WORKFLOWS:
        config.log(f"Unknown mode: {mode}. Available: {', '.join(WORKFLOWS)}")
        sys.exit(1)
    WORKFLOWS[mode](params)