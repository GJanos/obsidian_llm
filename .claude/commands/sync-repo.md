Run `git diff HEAD` and `git status` to see all staged and unstaged changes.

Based on the diff, write a concise commit message:
- Max 72 characters for the subject line
- Imperative mood ("add", "fix", "remove", "refactor", not "added")
- No period at the end
- If multiple concerns, pick the dominant one — do not write a list

Then run these in order using the Bash tool:
1. `git add -A`
2. `git commit -m "<your message>"`
3. `git push`

After each step, check the exit code. If any step fails, stop and report the error clearly.

If all three succeed, tell the user: the commit message you used, the short commit hash, and that the push was successful.
If anything fails, tell the user exactly which step failed and paste the error output.
