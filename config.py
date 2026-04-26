import os
import subprocess
from datetime import datetime
import ollama

DEBUG: bool = False


def log(msg: str) -> None:
    """Print a timestamped [LAIWM] info message to stdout."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[LAIWM {ts}] {msg}")


def dbg(msg: str) -> None:
    """Print a timestamped [DEBUG] message; no-op unless DEBUG is True."""
    if DEBUG:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[DEBUG {ts}] {msg}")

MODEL_NAME = "qwen3:14b"
EMBED_MODEL = "nomic-embed-text"
SEMANTIC_SYNTHESIS_COUNT = 5    # top N notes passed to LLM for answer synthesis
KEYWORD_MATCH_LIMIT = 5         # max keyword-matched files passed to synthesis
SEMANTIC_KEEP_TOP_PCT = 0.4     # fraction of notes kept by vector score before keyword search
LLM_TIMEOUT = 7200              # seconds — 2 hours for slow CPU inference
MONTHLY_BATCH_CHAR_LIMIT = 12_000  # larger context for monthly synthesis batches

VAULT_PATH = os.environ.get("OBSIDIAN_LLM_VAULT_PATH")
if not VAULT_PATH:
    raise EnvironmentError("OBSIDIAN_LLM_VAULT_PATH is not set. Add it to your .bashrc.")


def _get_windows_host_ip() -> str:
    """Resolve the Windows host IP from WSL2's default route — required to reach Ollama on the Windows side."""
    return subprocess.check_output(
        "ip route show | grep -i default | awk '{ print $3}'",
        shell=True, text=True
    ).strip()


SERVER_API_HOST = f"http://{_get_windows_host_ip()}:11434"
client = ollama.Client(host=SERVER_API_HOST, timeout=LLM_TIMEOUT)