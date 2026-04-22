import re
from datetime import datetime
from pathlib import Path

import config
import embeddings
from utils import collect_md_files, read_file, write_output
from config import dbg


_STOPWORDS = {
    "Which", "What", "When", "Where", "Who", "How", "Why", "Did", "Do",
    "Does", "Was", "Were", "Is", "Are", "Have", "Had", "The", "And",
    "But", "For", "From", "With", "That", "This", "Once", "Ever",
    "Most", "More", "Than", "My", "Me", "Its", "Their", "Our",
}

_SYNTHESIS_PROMPT = """\
You are a personal note vault assistant. Answer the question using ONLY the notes provided.
Rules:
- Answer in 1-2 sentences only. No lists, no headers, no summaries.
- State the specific fact (date, name, location) directly if it exists in the notes.
- If the answer is not in the notes, say only: "Not found in vault."
- Do not explain, do not summarise, do not add context.

Question: {query}

Notes:
{notes}"""


def _extract_keywords(query: str) -> list[str]:
    words = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', query)
    return [w for w in words if w not in _STOPWORDS]


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


def _build_candidates(
    all_scored: list[tuple[float, str]],
    keywords: list[str],
    files: list[str],
) -> list[tuple[float, str]]:
    vector_top = all_scored[:config.SEMANTIC_RECALL_COUNT]

    if not keywords:
        return vector_top

    kw_paths = _keyword_matches(keywords, files)
    dbg(f"Keyword matches: {len(kw_paths)} files for keywords {keywords}")

    score_map = {path: score for score, path in all_scored}
    kw_scored = sorted(
        [(score_map.get(p, 0.0), p) for p in kw_paths],
        reverse=True
    )[:config.KEYWORD_MATCH_LIMIT]

    candidate_map = {path: score for score, path in vector_top}
    for score, path in kw_scored:
        candidate_map[path] = score

    return [(score, path) for path, score in sorted(candidate_map.items(), key=lambda x: x[1], reverse=True)]


def _synthesize(candidates: list[tuple[float, str]], query: str) -> str:
    notes = "\n\n---\n\n".join(
        f"[{Path(path).name}]\n{read_file(path)[:800]}"
        for _, path in candidates
    )
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

    keywords = _extract_keywords(query)
    dbg(f"Extracted keywords: {keywords}")

    candidates = _build_candidates(all_scored, keywords, files)

    dbg(f"Candidate pool top 10:")
    for score, path in candidates[:10]:
        dbg(f"  {score:.3f}  {Path(path).name}")

    keyword_paths = {path for path in _keyword_matches(keywords, files)} if keywords else set()
    keyword_pool = [(s, p) for s, p in candidates if p in keyword_paths][:2]
    vector_pool = [(s, p) for s, p in candidates if p not in keyword_paths][:max(max_results - len(keyword_pool), 1)]
    pool = keyword_pool + vector_pool

    config.log(f"Stage 2 — synthesizing answer from {len(pool)} notes ({len(keyword_pool)} keyword, {len(vector_pool)} vector) with {config.MODEL_NAME}...")
    dbg("Synthesis pool:")
    for score, path in pool:
        dbg(f"  {score:.3f}  {'[KW] ' if path in keyword_paths else '     '}{Path(path).name}")

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
