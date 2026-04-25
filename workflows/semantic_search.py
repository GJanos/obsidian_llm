import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

import config
import embeddings
from utils import collect_md_files, read_file, write_output
from config import dbg


class _Keywords(BaseModel):
    keywords: list[str]


_KEYWORD_PROMPT = """\
Extract 2-5 search keywords from this query. Each keyword must be a single word — no phrases, no sentences. Include movie titles, place names, person names, activities, and key nouns. Exclude sentiment and relational words like "favorite", "best", "worst", "like", "love", "want". Only return an empty list if the query has no concrete searchable terms at all. /no_think

Query: {query}"""

_PRESUMMARY_PROMPT = """\
Summarize the key facts from this note in 1-3 sentences. Always include: rating, recommendation, genre, and any personal opinion or description. Keep the question in mind as context for what matters most. Always produce a summary — never skip or refuse. /no_think

Question context: {query}

Note [{filename}]:
{content}"""

_SYNTHESIS_PROMPT = """\
You are a personal note vault assistant. Answer the question using ONLY the summaries provided.
Rules:
- Answer in 1-2 sentences only. No lists, no headers, no summaries.
- State the specific fact (date, name, location) directly if it exists in the summaries.
- If the answer is not explicit, infer it from ratings, descriptions, or context in the summaries.
- Only if the answer cannot be determined even by inference, respond with exactly: "Not found in vault."
- Do not explain, do not summarise, do not add context.

Question: {query}

Summaries:
{notes}"""


def _extract_keywords(query: str) -> list[str]:
    result = config.client.chat(
        model=config.MODEL_NAME,
        messages=[{"role": "user", "content": _KEYWORD_PROMPT.format(query=query)}],
        format=_Keywords.model_json_schema()
    )
    return _Keywords.model_validate_json(result.message.content).keywords


def _keyword_matches(keywords: list[str], files: list[str]) -> set[str]:
    matched = set()
    for path in files:
        try:
            stem = Path(path).stem.lower()
            content = Path(path).read_text(encoding="utf-8", errors="replace").lower()
            if any(kw.lower() in stem or kw.lower() in content for kw in keywords):
                matched.add(path)
        except Exception:
            pass
    return matched


def _score_all(files: list[str], query: str) -> list[tuple[float, str]]:
    cache = embeddings.update_cache(files)
    query_vec = embeddings.embed_text(query)
    scored = [
        (embeddings.cosine_similarity(query_vec, cache[f]["vector"]), f)
        for f in files if f in cache
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def _presummary(path: str, query: str) -> str:
    content = read_file(path)[:2000]
    prompt = _PRESUMMARY_PROMPT.format(query=query, filename=Path(path).name, content=content)
    response = config.client.chat(
        model=config.MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.message.content.strip()
    result = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    dbg(f"  presummary {Path(path).name}: {result[:120].replace(chr(10), ' ')}")
    return result


def _synthesize(pool: list[tuple[float, str]], query: str) -> str:
    summaries = [
        f"[{Path(path).name}]\n{_presummary(path, query)}"
        for _, path in pool
    ]
    notes = "\n\n---\n\n".join(summaries)
    prompt = _SYNTHESIS_PROMPT.format(query=query, notes=notes)
    response = config.client.chat(
        model=config.MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.message.content.strip()
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()


def run(folder: str, query: str, max_results: int = config.SEMANTIC_SYNTHESIS_COUNT) -> None:
    search_root = folder if folder else config.VAULT_PATH
    files = collect_md_files(search_root)
    if not files:
        config.log(f"No .md files found in {search_root}")
        return

    config.log(f"Stage 1 — scoring {len(files)} notes...")
    all_scored = _score_all(files, query)
    cutoff = max(1, int(len(all_scored) * config.SEMANTIC_KEEP_TOP_PCT))
    top_files = [path for _, path in all_scored[:cutoff]]
    dbg(f"Kept top {config.SEMANTIC_KEEP_TOP_PCT:.0%} ({cutoff}/{len(all_scored)} notes) by vector score")

    config.log("Stage 2 — extracting keywords...")
    keywords = _extract_keywords(query)
    dbg(f"Extracted keywords: {keywords}")

    if keywords:
        kw_paths = _keyword_matches(keywords, top_files)
        dbg(f"Keyword matches: {len(kw_paths)} files")
        score_map = {path: score for score, path in all_scored}
        boosted = []
        for path in kw_paths:
            vec = score_map.get(path, 0.0)
            stem = Path(path).stem.lower()
            try:
                content = Path(path).read_text(encoding="utf-8", errors="replace").lower()
            except Exception:
                content = ""
            kw_hits = sum(1 for kw in keywords if kw.lower() in stem or kw.lower() in content)
            boosted.append((vec * (1 + 0.1 * kw_hits), path))
        pool = sorted(boosted, reverse=True)[:config.KEYWORD_MATCH_LIMIT]
    else:
        dbg("No keywords found — falling back to pure vector")
        pool = all_scored[:max_results]

    dbg(f"Synthesis pool ({len(pool)}):")
    for score, path in pool:
        preview = read_file(path)[:100].replace("\n", " ")
        dbg(f"  {score:.3f}  {Path(path).name}  |  {preview}")

    config.log(f"Stage 3 — pre-summarizing {len(pool)} notes with question in mind, then synthesizing...")
    answer = _synthesize(pool, query)
    dbg(f"Answer ({len(answer)} chars): {answer[:200].replace(chr(10), ' ')} ...")

    lines = [
        f"# Semantic Search\n\n**Query**: {query}\n",
        f"## Answer\n\n{answer}\n",
        "## Sources\n",
    ]
    for i, (sim, path) in enumerate(pool, 1):
        lines.append(f"{i}. [{Path(path).name}]({path}) — similarity: {sim:.3f}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    write_output(f"semantic_search_{ts}.md", "\n".join(lines))