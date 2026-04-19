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
- Initialized project structure: `config.py`, `manager.py`, `executor.py`, `modes.md`
- `config.py`: dynamic Windows host IP via `ip route show`, `VAULT_PATH` from `$OBSIDIAN_LLM_VAULT_PATH` env var
- `manager.py`: CLI `--prompt` entry point, LLM classifies intent against `modes.md` using Pydantic structured output (`response_format=RoutingResult`), asks user for missing params interactively, prepends `VAULT_PATH` to all path params
- `executor.py`: `monthly_summary` workflow — reads notes from `VAULT_PATH/Days/<year>/<MM-Month>/`, batches files to fit within KV cache limits, queries LLM per batch, appends results to output file
- Replaced manual JSON parsing (`extract_json_from_response`) with Pydantic `BaseModel` + lmstudio `response_format` structured output throughout
- Added `pydantic` dependency via `uv add pydantic`
- `.vscode/launch.json`: added `LAIWM: manager.py` debug config with `${input:prompt}` popup and `OBSIDIAN_LLM_VAULT_PATH` env var baked in
- **Bug**: LLM injected junk path segments ("my", "vault root") into `folder` param → fixed by building the notes path directly from `config.VAULT_PATH` in executor, ignoring `folder` entirely for `monthly_summary`
- **Bug**: `prepend_vault_path` crashed on `None` folder value → guarded with `if key in params and params[key]`
- **Bug**: model crashed (exit code `18446744072635812000`) on full 22-note context → root cause: GPU VRAM (~1.35 GB free after model weights) limits KV cache to ~9,400 tokens despite 32768 context window → set `BATCH_TOKEN_LIMIT = 7_000` (~28k chars), notes split into batches automatically
- Switched to CPU-only inference in LMStudio for stability (slower but no OOM crashes)
- `<think>` blocks stripped from all LLM output via regex in `_query_llm`
- `user.md` profile injected into every batch prompt; its char count subtracted from `BATCH_CHAR_LIMIT` to avoid overflow
- Prompt rewritten: first-person tone, uses name "János", lists events/habits concisely, ends with 2-3 sentence summary
- `lms.set_sync_api_timeout(3600)` — 1 hour timeout for slow CPU inference

# DAY 3 — 2026-03-24
Replaced LM Studio entirely with Ollama + IPEX-LLM. Root cause for the switch: LM Studio's Vulkan runtime crashes on Intel Arc iGPU mid-inference (after ~4 batches), and CPU-only mode was taking 2 hours to process 30 notes. IPEX-LLM gives Ollama a proper Intel GPU backend via SYCL/oneAPI instead of Vulkan — stable, fast, and the 1.7b model on iGPU now responds in seconds.
Setup required on Windows side: Miniforge + conda env llm, ipex-llm[xpu_2.6] and ipex-llm[cpp] installed, init-ollama.bat run as admin to swap in the GPU-patched Ollama binary. Server startup sequence: OLLAMA_NUM_GPU=999, ZES_ENABLE_SYSMAN=1, SYCL_CACHE_PERSISTENT=1, OLLAMA_HOST=0.0.0.0 (critical — without this Ollama binds only to 127.0.0.1 and is unreachable from WSL2), then ollama serve. Saved as start-ollama.bat.
Code changes: Swapped lmstudio SDK for ollama SDK. Model changed to qwen3:1.7b, port 1234 → 11434. All LLM call sites updated to client.chat(model, messages) / response.message.content pattern. Structured output calls now use format=Model.model_json_schema() + model_validate_json() in both manager.py and executor.py. All magic numbers (BATCH_TOKEN_LIMIT, BATCH_CHAR_LIMIT, LLM_TIMEOUT, PER_FILE_YEARLY_LIMIT) moved to config.py. Fixed duplicate /no_think line in monthly summary prompt, MAX_CONTEXT_CHARS undefined reference, unused variables and imports.
Monthly summary UX: Console now prints only date range + bullet points — batch processing noise suppressed. Previous batch summaries fed into next prompt to prevent repetition across batches.

# DAY 4 — 2026-03-27
Switched model from qwen3:1.7b to qwen3:8b. With the IPEX-LLM iGPU backend the 8b model is faster than LM Studio's 4b was on CPU-only, and noticeably smarter — better routing decisions and more coherent summaries. RAM pressure is manageable since the iGPU shares system memory and IPEX-LLM handles offloading efficiently.

Monthly summary output quality overhaul. The core problem was that the model completely ignored prompt instructions and produced long opinionated essays with headers, emojis, intro/outro paragraphs, and follow-up questions. Three changes in combination fixed it: (1) sandwich prompting — rules stated before the notes and repeated as a reminder after, (2) `MONTHLY_BATCH_CHAR_LIMIT = 4_000` to force smaller synthesis batches so the model has less context to get confused by, (3) explicit DO NOT rules covering every failure mode observed (no intro, no outro, no headers, no emojis, no opinions, no questions). `user.md` updated with a Summary Preferences section so the user profile itself also reinforces these constraints.

Three-pass summarization pipeline. Previous single-pass batching lost detail from early notes as context grew. New pipeline: Pass 1 — each daily note summarized independently to 1–3 bullets (focused, no dilution); Pass 2 — condensed day summaries batched and synthesized (entire month typically fits in one batch now, ~6k chars vs ~30k for raw notes); Pass 3 — final consolidation pass distills all batch outputs to max 15 key bullets. Quality improved significantly at the cost of ~29 extra LLM calls for Pass 1, acceptable given iGPU speed. `-summary` ending files excluded from `collect_md_files` to prevent feeding prior output back into new runs.

`--debug` CLI flag added. Sets `config.DEBUG = True`, enabling `config.dbg()` calls throughout the pipeline. Logs: routing result (mode, confidence, extracted params, missing params), resolved final params, and each LLM response (length + first 200 chars). Prompt content intentionally excluded from debug output to keep it readable.

**Hardware research — NPU vs iGPU**: Intel AI Boost NPU (Intel Core Ultra built-in) investigated as a second inference device. Verdict: NPU is 3–5x more energy-efficient and suited for background/always-on tasks (email summarization, lightweight inference), but has very limited SRAM (~48MB) and is too slow for large models. qwen3:8b batch summarization is a "generate now" use case — staying with iGPU.

Project restructured for maintainability. `executor.py` dissolved: each workflow extracted to its own file under a new `workflows/` package (`monthly_summary.py`, `semantic_search.py`, `yearly_summary.py`, `note_cleaner.py`). `workflows/__init__.py` owns the dispatch table and `run_workflow()`. Shared utilities (`query_llm`, `read_file`, `collect_md_files`, `write_output`, `read_user_profile`, `OUTPUT_DIR`) moved to `utils.py` at the project root, breaking the circular import that arose when `monthly_summary` was first extracted. Import chain is now clean: `manager → workflows → utils + config`.