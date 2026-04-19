from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

import config
import embeddings
from utils import collect_md_files, read_file, write_output


class _RankedResult(BaseModel):
    filename: str
    score: int
    reason: str


class _ReRankResponse(BaseModel):
    results: list[_RankedResult]


_RERANK_RULES = (
    "You are a relevance judge. Given a search query and a list of numbered note excerpts, "
    "return ALL of them ranked by relevance to the query. "
    "Score each from 1 (irrelevant) to 10 (highly relevant). "
    "Include a short reason (one sentence). "
    "Return every candidate — do not drop any. /no_think"
)


def _vector_recall(files: list[str], query: str) -> list[tuple[float, str]]:
    cache = embeddings.update_cache(files)
    query_vec = embeddings.embed_text(query)
    scored = [
        (embeddings.cosine_similarity(query_vec, cache[f]["vector"]), f)
        for f in files if f in cache
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:config.SEMANTIC_RECALL_COUNT]


def _rerank(candidates: list[tuple[float, str]], query: str) -> list[_RankedResult]:
    excerpts = []
    for i, (_, path) in enumerate(candidates, 1):
        content = read_file(path)[:400].replace("\n", " ")
        excerpts.append(f"{i}. [{Path(path).name}]\n{content}")

    prompt = (
        f"{_RERANK_RULES}\n\n"
        f"Query: {query}\n\n"
        "Candidates:\n" + "\n\n".join(excerpts)
    )

    result = config.client.chat(
        model=config.MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        format=_ReRankResponse.model_json_schema()
    )
    return _ReRankResponse.model_validate_json(result.message.content).results


def run(folder: str, query: str, max_results: int = 5) -> None:
    search_root = folder if folder else config.VAULT_PATH
    files = collect_md_files(search_root)
    if not files:
        print(f"[LAIWM] No .md files found in {search_root}")
        return

    print(f"[LAIWM] Stage 1 — vector recall across {len(files)} notes...")
    candidates = _vector_recall(files, query)

    print(f"[LAIWM] Stage 2 — re-ranking top {len(candidates)} candidates with {config.MODEL_NAME}...")
    ranked = _rerank(candidates, query)
    ranked.sort(key=lambda r: r.score, reverse=True)
    top = ranked[:max_results]

    lines = [f"# Semantic Search Results\n\n**Query**: {query}\n"]
    for i, r in enumerate(top, 1):
        lines.append(f"## {i}. {r.filename} (score: {r.score}/10)")
        lines.append(f"{r.reason}\n")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    write_output(f"semantic_search_{ts}.md", "\n".join(lines))