import os
import subprocess
from datetime import datetime
import ollama

DEBUG: bool = False


def dbg(msg: str) -> None:
    if DEBUG:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[DEBUG {ts}] {msg}")

MODEL_NAME = "qwen3:14b"
LLM_TIMEOUT = 7200          # seconds — 2 hours for slow CPU inference
BATCH_TOKEN_LIMIT = 32_000  # tokens per batch (gemma3 128k context)
BATCH_CHAR_LIMIT = BATCH_TOKEN_LIMIT * 4  # ~128,000 chars (1 token ≈ 4 chars)
MONTHLY_BATCH_CHAR_LIMIT = 12_000  # larger context for monthly synthesis batches
PER_FILE_YEARLY_LIMIT = 2_000  # max chars per file for yearly summary

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
