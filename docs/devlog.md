**LAIWM — Dev Log**

# DAY 1 — 2026-03-21
- Set up local LLM environment for the LAIWM project
- Installed Ollama initially, switched to LM Studio after discovering Intel Arc iGPU Vulkan support — exposes 17.92 GB shared VRAM instead of CPU-only
- Tried `qwen3:8b`, too large — crashed due to RAM exhaustion competing with WSL; settled on `qwen3:4b`
- **Key lesson**: Qwen3 has thinking mode on by default → 3+ minute responses on trivial prompts → must disable via `/no_think` or system prompt
- Confirmed LM Studio API server on `localhost:1234`
- **Gotcha**: PowerShell `curl` is aliased to `Invoke-WebRequest`, breaks standard flags → must use `curl.exe`
- **Gotcha**: API body must be passed via file (`-d @body.json`) to avoid shell escaping issues
- **Gotcha**: WSL and LM Studio compete for the same RAM pool — avoid heavy load simultaneously
- Verified API returns valid response via file-based curl

# DAY 2 — 2026-03-22
Project scaffolded: `config.py` (dynamic Windows host IP, `VAULT_PATH` from env), `manager.py` (CLI `--prompt` → LLM intent routing via Pydantic structured output), `executor.py` (monthly_summary batch pipeline reading `VAULT_PATH/Days/`). Pydantic `BaseModel` + `response_format` replaced all manual JSON parsing throughout.

Three bugs hit in sequence: LLM injected junk strings ("my", "vault root") into path params — fixed by building the notes path directly from `config.VAULT_PATH`, ignoring `folder` entirely; `prepend_vault_path` crashed on `None` folder — guarded; model OOM-crashed on full 22-note context (exit code `18446744072635812000`) — root cause was GPU KV cache limit (~9,400 tokens), fixed with `BATCH_TOKEN_LIMIT = 7_000`. `<think>` blocks stripped from all output. `user.md` profile injected into every batch prompt. 1-hour timeout set.

# DAY 3 — 2026-03-24
LM Studio dropped — Vulkan runtime crashed on Intel Arc after ~4 batches, CPU-only took 2 hours per run. Switched to Ollama + IPEX-LLM for a proper Intel GPU backend via SYCL/oneAPI. Setup: Miniforge + conda env, `ipex-llm[xpu_2.6]`, `init-ollama.bat` to swap in the GPU-patched binary. Critical: `OLLAMA_HOST=0.0.0.0` required — without it Ollama binds to 127.0.0.1 and is unreachable from WSL2.

Code: swapped lmstudio SDK for ollama SDK, model → qwen3:1.7b, port 1234 → 11434. Structured output switched to `format=Model.model_json_schema()` + `model_validate_json()`. All magic numbers moved to `config.py`. Monthly summary console cleaned up; previous batch summaries fed into next prompt to prevent repetition.

# DAY 4 — 2026-03-27
Model → qwen3:8b. Faster than LM Studio's 4b on CPU despite being larger, noticeably smarter.

Monthly summary quality was bad — model ignored all instructions and wrote opinionated essays with headers and emojis. Three changes fixed it together: sandwich prompting (rules before and after the notes), `MONTHLY_BATCH_CHAR_LIMIT = 4_000` to shrink per-batch context, and explicit DO NOT rules for every observed failure mode. Three-pass pipeline added: Pass 1 summarizes each note independently, Pass 2 batches the condensed summaries, Pass 3 distills to 15 bullets max. Prevents detail loss from early notes that plagued single-pass batching.

`--debug` flag added. `executor.py` dissolved — each workflow extracted to `workflows/` package. Shared utilities moved to `utils.py`, breaking the circular import. NPU investigated as second inference device; too slow and too little SRAM for these models. Staying with iGPU.

# DAY 5 — 2026-04-19
Upgraded model to qwen3:14b. Tried gemma3:12b first — crashes mid-inference on IPEX-LLM, SYCL backend doesn't fully support its architecture yet. qwen3:14b is a significant intelligence step up from 8b with no compatibility risk.

Removed `yearly_summary` and `note_cleaner` — not worth maintaining. Project now has two workflows: `monthly_summary` and `semantic_search`.

Docs reorganised into `docs/`. `technologies.md` added. `classifier.py` extracted from `manager.py`. Repo pushed to GitHub.

Pushed back on `folder` being required for semantic search — defeats the purpose of whole-vault search. Made it optional, defaulting to vault root. Also challenged the plan's claim that no LLM calls are needed at search time — proposed re-ranking the top vector results through qwen3:14b. Claude confirmed this is the standard RAG retrieval + re-ranking pattern and suggested listwise re-ranking (all candidates in one call).

Re-ranking proved completely unreliable in practice — every run returned either all 0/10 or all 100/10. Pushed back and argued the embedding model already ranked Rocky I, II, III correctly at 1–3, so the LLM layer was making things worse. Replaced re-ranking with LLM synthesis: top N notes passed to qwen3:14b to directly answer the question. Filename prepended to embedded content to improve recall for notes where the key term is in the filename. Recall remains noisy over 464 journal notes with overlapping hiking/travel vocabulary.

# DAY 6 — 2026-04-21
Rocky was a false positive — the embedding model found those notes easily because the filenames matched exactly. Glendalough exposed the real weakness: one specific event note drowned out by hundreds of daily notes with similar hiking vocabulary.

Synthesis was timing out and producing verbose non-answers when the wrong notes reached it. Pushed back on Claude's suggestion to use an LLM call for keyword extraction — too slow. Agreed on a zero-latency heuristic: extract capitalised words from the query, filter out common question words, fall back to pure vector if no keywords found. Hybrid search implemented: keyword grep injects matched files into the candidate pool ranked by vector score, with guaranteed slots in the synthesis pool so keyword matches always reach the LLM regardless of cosine rank. Synthesis prompt tightened to 1–2 sentences, explicit "Not found in vault." instruction. Recall still unreliable — work in progress.

# DAY 7 — 2026-04-22
Reversed keyword extraction from Day 6. The capitalised-word heuristic failed on single-word queries ("Rocky" not capitalised mid-sentence) and returned phrases instead of individual terms. Replaced with an LLM call using Pydantic structured output — returns a validated `list[str]`, `/no_think` added to suppress reasoning overhead. Prompt broadened from "proper nouns only" to cover movie titles, place names, activities, and key nouns. Single-word constraint added explicitly after observing "Rocky movie" returned as one token — structured output alone doesn't enforce atomicity.

Pre-filtering before keyword grep: drop bottom 60% by vector score first, run grep only on the surviving 40%. Fixes the hiking/travel vocabulary noise problem — correct note almost always survives the cut. Cutoff exposed as `SEMANTIC_KEEP_TOP_PCT = 0.4` in config. Boosted scoring replaces flat keyword priority: `vector_score * (1 + 0.1 * kw_hits)` so multi-keyword matches float above single-hit files without overriding the vector signal. Pool capped at `KEYWORD_MATCH_LIMIT = 5` (down from 10) to keep synthesis focused. Synthesis prompt updated to allow inference from ratings and descriptions — fixes false negatives where the answer was implied but not stated literally.

# DAY 8 — 2026-04-25
Content cleaning added to strip visual noise from notes before processing: YAML frontmatter, `<img>` tags, and mapview code blocks. Immediately hit a self-inflicted problem — stripping frontmatter also stripped `rating: 8.5`, which is exactly the data the LLM needs to answer "which Rocky was your favorite?" Walked right into it. Split into two functions: `_strip_noise()` (img/mapview only) used by `read_file()` for synthesis, and `clean_content()` (full strip including frontmatter) used only by the embedding pipeline where YAML noise hurts vector quality.

Circular import in `workflows/__init__.py` — `from workflows import` was resolving to itself instead of the submodules. Fixed with relative import `from . import`. Turned out `semantic_search.py` had gone missing from `workflows/` entirely during the session, which was the real cause.

Keyword extraction debate. Model returned only `['Rocky']` for "Which Rocky movie was my favorite?" — too narrow. Argued for extracting "movie" as well. Settled on a clear rule: extract content words (titles, places, names, activities, nouns), exclude sentiment and relational words ("favorite", "best", "worst") since they match too many unrelated notes and dilute the boosting signal. Debug logs added showing the first 100 chars of each pool file so the synthesis input is visible without running blind.

Presummary step added — question-focused LLM call per note before synthesis, same pattern as monthly_summary Pass 1. First attempt included a "No relevant information" escape hatch. Model used it for all 5 notes — because no Rocky note explicitly states "this is my favorite", it decided nothing was relevant. Pushed back, rewrote the prompt to always produce a summary (rating, recommendation, opinion, description) with no exit option. Rocky I surfaced as the favorite from the ratings comparison. Finally working.

# DAY 9 — 2026-04-26
Project polishing and finalisation for presentation. Docstrings added to all public and level-1 private functions across the codebase.

Bug caught in `monthly_summary.py`: `config.log(..., end=..., flush=True)` — `log()` doesn't accept those kwargs, raises `TypeError` on every Pass 3 run. Had gone unnoticed. Four dead config constants removed — leftovers from deleted workflows never referenced anywhere.

`_keyword_matches()` was reading each matched file twice: once to find matches, again to count hits. Merged into a single `_keyword_hits()` pass returning `{path: hit_count}`.

Startup banner and `_check_connection()` added — model and host printed on every run, friendly error if Ollama is unreachable. `.gitignore` fixed: `todo.md` and `docs/user.md` were both unprotected.

README written from scratch — motivation, hardware journey, model progression, both workflow pipelines as flow diagrams, real debug output example2.