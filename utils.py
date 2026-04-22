import re
from pathlib import Path

import config

OUTPUT_DIR = Path(__file__).parent / "output"
USER_PROFILE_PATH = Path(__file__).parent / "docs" / "user.md"


def collect_md_files(folder: str) -> list[str]:
    base = Path(folder)
    if not base.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")
    return sorted(
        str(p) for p in base.rglob("*.md")
        if not p.stem.endswith("-summary")
    )


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def query_llm(prompt: str) -> str:
    response = config.client.chat(
        model=config.MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.message.content.strip()
    result = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    config.dbg(f"Response ({len(result)} chars): {result[:200].replace(chr(10), ' ')} ...")
    return result


def read_user_profile() -> str:
    if USER_PROFILE_PATH.exists():
        return USER_PROFILE_PATH.read_text(encoding="utf-8")
    return ""


def write_output(filename: str, content: str) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / filename
    out_path.write_text(content, encoding="utf-8")
    print(content)
    config.log(f"Output written to {out_path}")
