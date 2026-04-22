from calendar import month_name as _MONTH_NAMES
from pathlib import Path

import config
from utils import OUTPUT_DIR, collect_md_files, query_llm, read_file, read_user_profile

_DAY_RULES = (
    "Write ONLY a bullet list (`- item`). 1-3 bullets max. "
    "Facts only — what happened, not what it means. "
    "No intro, no outro, no headers, no opinions, no questions. "
    "Skip routine unless something unusual happened."
)

_BATCH_RULES = (
    "Write ONLY a bullet list (`- item`). Max 10 bullets. "
    "Facts only — what happened, not what it means. "
    "No intro, no outro, no headers, no sections, no emojis, no opinions, no questions. "
    "First person, use name János. Merge similar events. Drop anything minor."
)

_FINAL_RULES = (
    "Write ONLY a bullet list (`- item`). Max 25 bullets. "
    "First person, use name János. "
    "SKIP: anything routine or forgettable — daily habits, food, sleep, commute, "
    "and work tasks that led nowhere. "
    "KEEP: only what actually mattered — major life events, career moves, achievements, "
    "health issues, financial decisions, relationship milestones, travel, important social events, "
    "projects started or finished, skills and tools learned, personal struggles and how they were handled, "
    "meaningful realisations or mindset shifts, and small but notable wins or setbacks. "
    "No intro, no outro, no headers, no sections, no emojis, no opinions, no questions."
)


def _collect_notes(year: int, month: int) -> list[str]:
    month_dir = Path(config.VAULT_PATH) / "Days" / str(year) / f"{month:02d}-{_MONTH_NAMES[month]}"
    return collect_md_files(str(month_dir))


def _presummary_day(stem: str, content: str, user_context: str) -> str:
    prompt = (
        f"{user_context}"
        f"Daily note — {stem}.\n{_DAY_RULES}\n\n"
        f"Note:\n{content}\n\n"
        f"Reminder: {_DAY_RULES} /no_think"
    )
    return f"### {stem}\n{query_llm(prompt)}"


def _make_batches(day_summaries: list[str], effective_limit: int) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for entry in day_summaries:
        entry_chars = len(entry) + 4
        if current and current_chars + entry_chars > effective_limit:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(entry)
        current_chars += entry_chars
    if current:
        batches.append(current)
    return batches


def _synthesize_batch(
    batch: list[str],
    user_context: str,
    previous_summaries: list[str],
    month_label: str,
) -> str:
    prior = (
        "Points already covered — do NOT repeat them:\n" +
        "\n".join(previous_summaries) + "\n\n"
    ) if previous_summaries else ""
    prompt = (
        f"{user_context}"
        f"{prior}"
        f"Pre-summarized daily notes — {month_label}.\n{_BATCH_RULES}\n\n"
        f"Notes:\n{chr(10).join(batch)}\n\n"
        f"Reminder: {_BATCH_RULES} /no_think"
    )
    return query_llm(prompt)


def _consolidate(summaries: list[str], user_context: str, month_label: str) -> str:
    prompt = (
        f"{user_context}"
        f"All batch summaries for {month_label}.\n{_FINAL_RULES}\n\n"
        f"Summaries:\n{chr(10).join(summaries)}\n\n"
        f"Reminder: {_FINAL_RULES} /no_think"
    )
    return query_llm(prompt)


def run(year: int, month: int) -> None:
    month_label = f"{_MONTH_NAMES[month]} {year}"
    notes = _collect_notes(year, month)
    if not notes:
        config.log(f" No notes found for {month_label}")
        return

    user_profile = read_user_profile()
    user_context = f"About me:\n{user_profile}\n\n" if user_profile else ""

    # Pass 1: condense each day independently
    n = len(notes)
    config.log(f" {n} notes → pre-summarizing...")
    day_summaries: list[str] = []
    for idx, path in enumerate(notes, 1):
        stem = Path(path).stem
        print(f"  [{idx}/{n}] {stem} ...", end=" ", flush=True)
        day_summaries.append(_presummary_day(stem, read_file(path), user_context))
        print("done")

    # Pass 2: batch synthesis
    effective_limit = config.MONTHLY_BATCH_CHAR_LIMIT - len(user_profile)
    batches = _make_batches(day_summaries, effective_limit)
    n_batches = len(batches)
    config.dbg(f"Synthesis: {len(day_summaries)} day summaries → {n_batches} batch(es), limit={effective_limit} chars")
    config.log(f" Synthesizing {n_batches} batch(es)...")

    previous_summaries: list[str] = []
    for idx, batch in enumerate(batches, 1):
        stems = [e.split("\n")[0].replace("### ", "") for e in batch]
        print(f"  [{idx}/{n_batches}] {stems[0]} → {stems[-1]} ...", end=" ", flush=True)
        summary = _synthesize_batch(batch, user_context, previous_summaries, month_label)
        previous_summaries.append(summary)
        print("done")

    # Pass 3: final consolidation
    config.log(" Final consolidation ...", end=" ", flush=True)
    final = _consolidate(previous_summaries, user_context, month_label)
    print("done")

    out_path = OUTPUT_DIR / f"monthly_summary_{year}_{month:02d}.md"
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path.write_text(f"# Monthly Summary: {month_label}\n\n{final}\n", encoding="utf-8")
    config.log(f" Output written to {out_path}")
