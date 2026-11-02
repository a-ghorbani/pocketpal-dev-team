# Comments Test

The test cited under Comments in `docs/standards/code-review.md`. Load when writing code that seems to need a comment or reviewing comment load.

A comment is almost always a **symptom**. Find which case and fix *that*:

1. **Bad comment**: restates the code, narrates the change, or records how the answer was reached. → **Delete it.**
2. **Bad code**: prose is needed because the code is unclear. → **Fix the code** (rename, extract, drop the cleverness).
3. **Bad design**: the comment justifies an odd approach. → **Fix the design**; if the oddity is truly forced, put the reasoning in `context/architecture/`, not above the call site.
4. **Genuine "why"**: a fact the code cannot show (external constraint, non-obvious platform behaviour, a trap that looks like a bug and isn't). → **Keep it.** Rare.

Test: *if this line is deleted, what does a competent reader who knows the codebase but not this task lose?* Nothing: case 1. "They would misread the code": case 2 or 3, change the code. "They would repeat a mistake the code cannot warn about": case 4.

Nothing about the task belongs in source (no "we hit X", naming the bug just fixed, round numbers, plan-step restatements, or story anchors); reviewers flag it under Comment load. Source describes the current state; reasoning lives in the story and architecture docs.
