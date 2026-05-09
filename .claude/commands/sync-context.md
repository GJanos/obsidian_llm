You are getting up to speed on the Pulse project at the start of a new work session. Execute these steps in order.

**Step 1 — Read memory**
Read `C:\Users\HP\.claude\projects\d--JanosGorondi-AI-pulse-news\memory\MEMORY.md` (the index), then read every file it references.

**Step 2 — Read the last devlog entries**
Read `devlog.md`. Focus on the last 2–3 entries to understand what was recently worked on and what decisions were made.

**Step 3 — Scan the codebase state**
Read the following files:
- `cron/*`
- `app/*`
- `supabase/*`

**Step 4 — Check package.json for installed dependencies**
Read `package.json` to see what runtime deps are actually installed (vs planned).

**Step 5 — Produce the briefing**
Write a concise briefing with these sections:

```
## Pulse — Session Briefing

### What this project is
<1–2 sentences max>

### Last session recap
<2–4 bullet points from the most recent devlog entry>

### Current standing
<Where exactly in the build sequence are we? What's the next logical task?>

### Suggested next step
<One concrete recommendation for what to work on today>
```

Keep the entire briefing under 15 lines. Be specific, not generic.