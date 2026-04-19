from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

import config
from utils import OUTPUT_DIR, collect_md_files, query_llm, read_file, write_output


class _SearchScore(BaseModel):
    score: int
    excerpt: str


def run(folder: str, query: str, max_results: int = 5) -> None:
    files = collect_md_files(folder)
    if not files:
        print(f"[LAIWM] No .md files found in {folder}")
        return

    print(f"[LAIWM] Searching {len(files)} files...")
    scored = []
    for i, path in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] {Path(path).name}")
        content = read_file(path)[:3_000]
        prompt = (
            f'Rate the relevance of this note to the query: "{query}"\n\n'
            f"Note content:\n{content} /no_think"
        )
        try:
            result = config.client.chat(
                model=config.MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                format=_SearchScore.model_json_schema()
            )
            parsed = _SearchScore.model_validate_json(result.message.content)
            scored.append((parsed.score, parsed.excerpt, path))
        except Exception:
            scored.append((0, "", path))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_results]

    lines = [f"# Semantic Search Results\n\n**Query**: {query}\n"]
    for rank, (score, excerpt, path) in enumerate(top, 1):
        lines.append(f"## {rank}. {Path(path).name} (score: {score}/10)\n")
        lines.append(f"**Path**: `{path}`\n")
        if excerpt:
            lines.append(f"**Excerpt**: {excerpt}\n")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    write_output(f"semantic_search_{ts}.md", "\n".join(lines))
