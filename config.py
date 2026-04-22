import os
import subprocess
from datetime import datetime
import ollama

DEBUG: bool = False


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[LAIWM {ts}] {msg}")


def dbg(msg: str) -> None:
    if DEBUG:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[DEBUG {ts}] {msg}")

MODEL_NAME = "qwen3:14b"
EMBED_MODEL = "nomic-embed-text"
SEMANTIC_RECALL_COUNT = 50      # notes retrieved by vector stage
SEMANTIC_SYNTHESIS_COUNT = 5    # top N notes passed to LLM for answer synthesis
KEYWORD_MATCH_LIMIT = 10        # max keyword-matched files injected into candidate pool
LLM_TIMEOUT = 7200              # seconds — 2 hours for slow CPU inference
BATCH_TOKEN_LIMIT = 32_000      # tokens per batch (qwen3 context)
BATCH_CHAR_LIMIT = BATCH_TOKEN_LIMIT * 4  # ~128,000 chars (1 token ≈ 4 chars)
MONTHLY_BATCH_CHAR_LIMIT = 12_000  # larger context for monthly synthesis batches
PER_FILE_YEARLY_LIMIT = 2_000   # max chars per file for yearly summary

VAULT_PATH = os.environ.get("OBSIDIAN_LLM_VAULT_PATH")
if not VAULT_PATH:
    raise EnvironmentError("OBSIDIAN_LLM_VAULT_PATH is not set. Add it to your .bashrc.")

def _get_windows_host_ip() -> str:
    return subprocess.check_output(
        "ip route show | grep -i default | awk '{ print $3}'",
        shell=True, text=True
    ).strip()

SERVER_API_HOST = f"http://{_get_windows_host_ip()}:11434"
client = ollama.Client(host=SERVER_API_HOST, timeout=LLM_TIMEOUT)
