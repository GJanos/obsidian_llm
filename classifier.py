import os
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

import config

MODES_FILE = Path(__file__).parent / "docs" / "modes.md"

PATH_PARAMS = {"folder"}

PARAM_DESCRIPTIONS = {
    "folder": "Path relative to vault (or absolute)",
    "query": "The search query or topic",
    "year": "4-digit year (e.g. 2026)",
    "month": "Month number 1-12 (e.g. 3 for March)",
    "max_results": "Number of results to return (default 5)",
}

INT_PARAMS = {"year", "month", "max_results"}
BOOL_PARAMS: set[str] = set()

_CLASSIFICATION_PROMPT = """\
You are a workflow classifier. Analyse the user request and the available workflow modes.
Extract the mode name, any parameters present in the request, and list required parameters that are missing.

Available modes:
---
{modes_doc}
---

User request: {user_prompt} /no_think"""


class RoutingResult(BaseModel):
    mode: str | None
    params: dict[str, Any]
    missing: list[str]
    confidence: float


def classify(user_prompt: str) -> RoutingResult:
    modes_doc = MODES_FILE.read_text(encoding="utf-8")
    prompt = _CLASSIFICATION_PROMPT.format(modes_doc=modes_doc, user_prompt=user_prompt)
    result = config.client.chat(
        model=config.MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        format=RoutingResult.model_json_schema()
    )
    return RoutingResult.model_validate_json(result.message.content)


def collect_missing_params(missing: list[str], params: dict) -> dict:
    if not missing:
        return params
    config.log("Some information is needed:\n")
    try:
        for name in missing:
            desc = PARAM_DESCRIPTIONS.get(name, name)
            value = input(f"  {name} ({desc}): ").strip()
            if name in INT_PARAMS:
                value = int(value)
            elif name in BOOL_PARAMS:
                value = value.lower() in ("true", "yes", "1")
            params[name] = value
    except KeyboardInterrupt:
        config.log("Cancelled.")
        sys.exit(0)
    return params


def prepend_vault_path(params: dict) -> dict:
    for key in PATH_PARAMS:
        if key in params and params[key]:
            params[key] = os.path.join(config.VAULT_PATH, params[key])
    return params


def resolve(routing: RoutingResult, user_prompt: str) -> dict:
    params = routing.params

    if not params.get("query"):
        params["query"] = user_prompt
    routing.missing = [p for p in routing.missing if p != "query"]

    for key in PATH_PARAMS:
        if key in routing.missing and key not in params:
            params[key] = ""
    missing = [p for p in routing.missing if p not in PATH_PARAMS]

    params = collect_missing_params(missing, params)
    params = prepend_vault_path(params)
    return params
