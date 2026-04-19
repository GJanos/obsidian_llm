# Technologies

---

## Part 1 — General Overview

### Python 3.12+
General-purpose programming language used for the entire project. Version 3.12+ required for `str | None` union syntax in type hints without `from __future__ import annotations`.

### uv
Fast Python package manager and project runner by Astral. Replaces pip + virtualenv. Used to manage dependencies (`uv add`, `uv run`) and defined in `pyproject.toml`. Significantly faster than pip for installs.

### Pydantic v2
Data validation library using Python type hints. Used for two purposes:
- **Structured LLM output**: `BaseModel.model_json_schema()` generates a JSON schema passed to Ollama's `format=` parameter, forcing the model to return valid typed JSON.
- **Parsing**: `model_validate_json()` deserializes the LLM's JSON response directly into a Python object with type checking.

### Ollama
Local LLM inference server. Runs models downloaded via `ollama pull`. Exposes a REST API on port 11434. The Python SDK (`ollama.Client`) wraps the API with `client.chat()` calls. Handles model loading, KV cache management, and context window allocation.

### Qwen3 (Alibaba)
Family of open-weight instruction-following language models. Key property for this project: supports `/no_think` suffix in prompts to suppress chain-of-thought reasoning (think mode), drastically reducing response latency and token waste. Sizes used: `8b` → `14b`.

### IPEX-LLM (Intel Extension for PyTorch — LLM)
Intel's optimization layer for LLM inference on Intel hardware. Provides a patched Ollama binary (`ollama-lib.exe`) that uses SYCL/oneAPI instead of Vulkan or CUDA for GPU acceleration on Intel Arc iGPUs. Installed via `pip install ipex-llm[xpu_2.6]` and `ipex-llm[cpp]` inside a conda environment. Required `init-ollama.bat` (run as admin) to swap the GPU-patched binary into the Ollama installation.

### SYCL / oneAPI (Intel)
Intel's heterogeneous compute framework (analogous to CUDA for NVIDIA). SYCL is the programming model; oneAPI is the toolkit. IPEX-LLM compiles GPU kernels against oneAPI, which then runs on Intel Arc via the Level Zero GPU driver (`level_zero:gpu:0`). Environment variables required at server startup:
- `OLLAMA_NUM_GPU=999` — offload all layers to GPU
- `ZES_ENABLE_SYSMAN=1` — enable GPU system management
- `SYCL_CACHE_PERSISTENT=1` — cache compiled SYCL kernels to disk (avoids recompilation on each start)

### WSL2 (Windows Subsystem for Linux 2)
Linux environment running inside Windows. The Python project runs inside WSL2, while the Ollama server runs natively on Windows (required for IPEX-LLM iGPU access). WSL2 and Windows share the same physical RAM pool, which constrains available VRAM. Network bridge: WSL2 gets a virtual IP; the Windows host IP is dynamically resolved via `ip route show | grep default | awk '{print $3}'`.

### Miniforge / Conda
Conda-based Python distribution used on the Windows side to manage the IPEX-LLM environment (`conda env: llm`). Required because IPEX-LLM has specific native library dependencies that are easiest to manage via conda.

### Obsidian
Personal knowledge management app. Notes are stored as plain `.md` files organized in a vault. This project reads from the vault directly via the filesystem — no Obsidian API involved.

---

## Part 2 — Project-Specific Usage

### LLM client (`config.py`)
`ollama.Client` is instantiated once at module load with the dynamically resolved Windows host IP and a 2-hour timeout (`LLM_TIMEOUT = 7200`). All workflows import from `config` and call through `utils.query_llm()` — no workflow touches the client directly.

### Structured output for routing (`classifier.py`)
`RoutingResult` is a Pydantic model with `mode`, `params`, `missing`, and `confidence` fields. Passed as `format=RoutingResult.model_json_schema()` to `client.chat()`, forcing the LLM to return valid JSON that is then deserialized with `RoutingResult.model_validate_json()`. This replaces fragile regex-based JSON extraction.

### Think-mode suppression
All prompts append `/no_think` to disable Qwen3's chain-of-thought mode. Without this, every response begins with a `<think>...</think>` block that can run for minutes and adds thousands of tokens. As a fallback, `utils.query_llm()` also strips any `<think>` blocks from the response via regex in case thinking mode leaks through.

### Three-pass summarization pipeline (`workflows/monthly_summary.py`)
Raw daily notes average ~1,900 chars each. Processing 30 notes in one pass would exceed the KV cache. The pipeline:
1. **Pass 1 — per-day condensation**: each note → 1–3 bullets (~200 chars). 30 LLM calls, one per file.
2. **Pass 2 — batch synthesis**: condensed day summaries batched by `MONTHLY_BATCH_CHAR_LIMIT = 12,000` chars → synthesized to ~10 bullets per batch.
3. **Pass 3 — final consolidation**: all batch outputs → max 25 final bullets.

Total context sent to the model never exceeds ~12k chars per call, well within the 32k+ KV cache available with qwen3:14b on the Arc iGPU.

### Sandwich prompting
Rules are stated before the notes content and repeated as a `Reminder:` after. This combats LLM tendency to ignore instructions when a long content block separates the prompt from its constraints. Critical for enforcing bullet-only output with no intro/outro.

### `OLLAMA_HOST=0.0.0.0`
Without this, Ollama binds only to `127.0.0.1` on Windows, making it unreachable from WSL2. Setting `OLLAMA_HOST=0.0.0.0` before `ollama serve` makes it listen on all interfaces including the WSL2 bridge.

### Batch limits (`config.py`)
- `BATCH_TOKEN_LIMIT = 32,000` — maximum tokens per batch, sized for qwen3:14b's context and available VRAM
- `BATCH_CHAR_LIMIT = 128,000` — character equivalent (1 token ≈ 4 chars)
- `MONTHLY_BATCH_CHAR_LIMIT = 12,000` — tighter limit for monthly synthesis batches to keep quality high
- `PER_FILE_YEARLY_LIMIT = 2,000` — max chars read per file for yearly summary to cap context usage

### Context window (`num_ctx`)
Ollama defaults to `ctx-size = 4096` if not told otherwise. For long prompts this causes a 500 crash mid-inference. The `options={"num_ctx": ...}` parameter in `client.chat()` overrides this per-request.

### Debug mode (`config.py` + `--debug` flag)
`config.DEBUG = True` enables `config.dbg()` calls throughout the pipeline. Logs include routing decisions, resolved params, and LLM response previews (first 200 chars + length). Prompt content is intentionally excluded to keep output readable. Timestamps are included in every debug line (`[DEBUG HH:MM:SS]`).
