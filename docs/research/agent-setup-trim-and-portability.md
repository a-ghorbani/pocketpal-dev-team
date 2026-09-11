# Agent setup: trim, freedom, portability

Audit of the dev-team control plane (2026-09-11). Three goals: fewer and sharper directives without losing the pipeline's guarantees; more latitude for capable models on work the pipeline doesn't cover; run cleanly under Claude Code, Codex, and opencode.

## 1. Where the words go

| Surface | Words | Loaded |
| --- | --- | --- |
| `AGENTS.md` (+ `CLAUDE.md`) | 1,740 | every turn, every agent |
| 9 pipeline stage agents | 11,400 | per stage |
| 12 role reviewers (shared `agents/reviewers/`) | 2,400 | per review |
| `pipeline.md` + `start-task` | 1,800 | orchestrator |
| `context/architecture/*.md` | **119,000** | intake reads *all* of it |
| `README.md` | 2,000 | humans |

About 3,000 of the 11,400 stage-agent words are three boilerplate kinds (measured by section):

- **Pre-flight bash** (676 words, 7 agents) re-checks worktree/branch/files. The guard hooks already enforce the worktree and branch rules, so the script repeats an enforced invariant.
- **Routing blocks** (822 words) in the form "Use pocketpal-X … WORKTREE: … BRANCH: …". `pipeline.md` says the top-level session owns routing, yet every stage also hand-writes the next stage's prompt. This is also the main Claude-only phrasing.
- **NEVER/Anti-pattern/Rules lists** (1,062 words) mostly restate the body as prohibitions.

## 2. Trim opportunities (accuracy-preserving)

Ranked by payoff ÷ risk.

### T1. Intake stops reading the whole architecture library
Intake's context-loading says "read every file" in `context/architecture/`. That is about 119k words (~160k tokens) before it writes a brief of a few hundred words. Replace it with: read `context/architecture/README.md` (make it a real index: one line per flow + the code dirs it covers), then open only the flows whose code the request touches. Fix the index itself too: it lists `persistence.md` and `vision.md`, which don't exist, and omits 11 of the 16 real docs.

### T2. Stages return a verdict; the orchestrator routes
Delete every stage's "Routing to X" / "On LGTM, route to" / "Hand off" block. Define one **handoff envelope** in `pipeline.md` (the `WORKTREE / BRANCH / TASK_ID / STORY_DIR / NATIVE_CHANGES / ARCHITECTURE_DOCS` keys, with the story dir as the durable carrier), and have each stage end with `VERDICT: <token>` plus its artifact path. The orchestrator already maps verdict to next stage in `pipeline.md`. This removes ~800 words and the PR-fix path-reconstruction bug class (intake already warns "never reconstruct paths from TASK_ID"), and it takes out the harness-specific "Use pocketpal-X" phrasing.

### T3. One pre-flight, stated once
Replace the 7 bash pre-flight blocks with one line in `AGENTS.md` ("confirm you're in the worktree you were given, on its non-main branch; the inputs your stage reads exist, else stop with `BLOCKED: <what>`"). Hooks remain the hard guarantee.

### T4. Single source of truth for repeated tables
| Meaning | Currently in | Keep in |
| --- | --- | --- |
| complexity matrix | pipeline.md, intake, README | pipeline.md |
| naming/layout table | AGENTS.md, intake, README | AGENTS.md |
| stage/output table + diagram | pipeline.md, README, start-task | pipeline.md (README links) |
| public-artifact hygiene | AGENTS.md, issue-tracking, implementer, tester, pipeline-reviewer | AGENTS.md (one para) |
| 60% coverage floor | tester, pipeline-reviewer, code-review | code-review.md |
| jest/MobX test rules (~600 words) | tester **and** patterns.md | patterns.md; tester points to it |
| native-change detection + commands | AGENTS.md, intake, implementer, pipeline-reviewer, code-review | AGENTS.md (trigger) + one `tools/verify-native.sh` |
| disambiguation of similar agent names | pipeline.md, architect-critic, plan-critic | agent `description:` fields only |

### T5. Move the comments essay out of the always-loaded file
The "Comments: treat the urge…" section is ~450 words paid on every turn by every agent, including the ones that never write code. Move it to `docs/standards/code-review.md` (reviewer imposes it, as the review already does) and leave one line plus a pointer in `AGENTS.md`. Same for "Concurrent lanes": keep the one-sentence rule and move the explanation to `context/architecture/README.md`, since only doc absorbers need it.

### T6. Rewrite prohibitions as targets
Collapse the NEVER lists into the positive statement the body already makes. Keep a prohibition only where it is a hard guardrail with no positive form (e.g. never push `main`), and those are hook-enforced anyway. Per mattpocock's `writing-for-agents`, negations make the forbidden behaviour *more* available.

### T7. Remove sediment
- `orchestrator/README.md` documents `pocketpal-orchestrator` / `pocketpal-reviewer`, which no longer exist. Delete it.
- `tools/guard-submodule-*.sh` error text says "Use pocketpal-orchestrator". Point to `tools/create-worktree.sh` instead.
- `README.md` "Autonomous mode" claims curl is blocked (it isn't in Claude settings) and duplicates pipeline.md. Cut README to what a human needs: setup, `/start-task`, and a link to the runbook.
- `docs/research/comprehensive-analysis.md` (May) describes a superseded setup. Archive or delete it.
- The pipeline-reviewer PR template hardcodes `· Claude Code`, which contradicts the "name the harness" rule.

**Expected result:** stage agents shrink from 11,400 to roughly 5,500 words; `AGENTS.md` from 1,670 to ~800; intake context drops by ~150k tokens per task. No gate, verdict, artifact, or hard rule is removed.

## 3. More freedom for capable models

The pipeline is right for *delivery* (a change landing in pocketpal-ai). The friction comes from it leaking into everything else, and from rules that make stages stop where judgement would do.

- **F1. Say where the process applies.** Add an "Outside the pipeline" paragraph to `AGENTS.md`. Investigations, device/e2e/bench runs, tooling in this repo, docs, triage and research are **objective-driven**: act directly toward the stated goal, bounded only by the non-negotiables (worktree isolation, submodule read-only, secrets, public hygiene). Nothing needs an intent brief unless it will become an app PR.
- **F2. Hard rules vs defaults.** Split `AGENTS.md` into *Guardrails* (hook-enforced or irreversible: the eight bullets that matter) and *Defaults* (the model may deviate when it records why in the story/PR). Today both read as MUST.
- **F3. Implementer deviations.** Current rule: "Do NOT deviate from HOW without surfacing it back to planner first". New rule: deviate when the plan is wrong in a way that doesn't touch a WHAT invariant, and log it in the HOW Progress table. The invariant-stop rule stays. This removes a round-trip the pipeline-reviewer already covers.
- **F4. Critic loops by risk, not tier.** Quick tasks: plan-critic only if the plan touches >1 flow or native. Complex: keep both. "When in doubt classify up" becomes "classify by the riskiest contract touched". Up-classification costs full critic loops.
- **F5. Stage agents may explore.** Drop "Do NOT improve code beyond HOW scope" in favour of "out-of-scope improvements go in the PR body's Follow-ups". The model is allowed to notice things.
- **F6. Codex curl/wget ban.** `.codex/rules/default.rules` forbids `curl`/`wget` outright (Claude has no such ban), which blocks legitimate API/device work under Codex only. Drop it or narrow it to piping into a shell.

## 4. From mattpocock/skills (commit 3cca18b, 2026-09-04)

His repo is a set of small, composable skills. Quoting his README, it is positioned *against* heavy frameworks ("GSD, BMAD, Spec-Kit … take away your control"). It installs via the Claude plugin marketplace or `npx skills@latest add mattpocock/skills`, and it ships an `agents/openai.yaml` beside each skill for Codex. What's worth taking:

| Item | Verdict | Use here |
| --- | --- | --- |
| `writing-for-agents` | **adopt as-is** | The rubric for T1–T7: context pointers, no-op hunting, "environment is the source of truth (docs that restate it are a cache)", negation, sediment. Install it and run it over each agent during the trim. |
| user- vs model-invoked split (`disable-model-invocation`) | adapt | Mark `start-task`, `review-pr`, `bench`, `run-e2e`, `review-l10n` user-invoked so they stop occupying the model's skill-choice budget. Add `agents/openai.yaml` with `allow_implicit_invocation: false` for Codex. |
| harness-neutral cross-refs (his changelog #781 removed tool/agent-type names "so the step is followable on Codex") | adopt the rule | Write "dispatch the X role as a subagent", never `Task(subagent_type=…)` / "Use X". |
| `code-review` two-axis (Standards vs Spec, separate subagents, never merged) | steal idea | Our pipeline-reviewer mixes spec-compliance with standards. Splitting maps cleanly: spec axis = testable-contract compliance; standards axis = code-review.md lenses. |
| `diagnosing-bugs` (build a *red* signal first) | adopt, tailor | Matches the memory notes "prove an app bug before routing it" and fixture provenance. Good default for bug-type intake. |
| `grilling` "frontier" questions with a recommended answer each | steal idea | Improve `NEEDS_INPUT`: each question carries a recommended default, so a human can reply "defaults" and a headless driver can opt in to them. |
| `domain-modeling` ADR test (hard to reverse ∧ surprising ∧ real trade-off) | steal idea | Filter for what earns a `(D)` line in `context/architecture/`. |
| `to-tickets` tracer-bullet slices | steal idea | For complex HOW sequencing. |

**Leave alone:** his human-in-the-loop waits (conflict with the autonomous pipeline), his "no file paths in specs" rule (our HOW is file-level on purpose), `git-guardrails` (blocks all pushes), and `implement-spec` (parallel worktree merge, unproven).

## 5. Harness portability

Tested against a scratch project on Claude Code 2.1.268, Codex CLI 0.153.4, and opencode 1.18.25. **[L]** = verified locally.

### What each harness actually sees today

| Asset | Claude | Codex | opencode |
| --- | --- | --- | --- |
| `AGENTS.md` | via `CLAUDE.md` → `@AGENTS.md` | ✅ native | ✅ native (first-found wins, so `CLAUDE.md` is skipped) |
| skills | `.claude/skills` (8) | `.codex/skills` (5): **no `start-task`, no `figma-implement`** | `.claude/skills` (8), but the `@skills/...` adapter lines are *not* expanded |
| subagents | `.claude/agents/*.md` (21) | **none**: Codex reads only `.codex/agents/*.toml`; our 12 `.md` files are invisible to `spawn_agent` [L] | **none**: opencode doesn't read `.claude/agents` [L] |
| guard hooks | 5 guards | 3 guards + a 622-line Python policy that duplicates them; **secrets-read guard missing** | **none**: opencode has no Claude-style hooks; needs a TS plugin |
| MCP (`figma-local`) | `.mcp.json` | not configured | not configured |
| tracker (Plane) | Claude plugin skill | not discoverable (lives in `~/.claude/plugins/cache/…`) | not discoverable |
| operational memory (25 notes: e2e quirks, device fleet, wire facts) | auto-memory | **invisible** | **invisible** |

So only review subagents and a few skills are "ported" today, and even the Codex reviewers don't load.

### Target layout: one source, generated adapters

```text
AGENTS.md                      # canonical, harness-neutral (no @imports inside)
CLAUDE.md                      # "@AGENTS.md" + Claude-only notes
agents/<name>.md               # canonical role bodies: name, description, access: read-only|write
.agents/skills/<name>/SKILL.md # canonical skills (Agent Skills spec; always set name:)
.claude/skills  -> .agents/skills          (symlink; all three follow symlinks [L])
tools/sync-agents.sh           # generates from agents/*.md:
  .claude/agents/<name>.md       disallowedTools for read-only roles
  .codex/agents/<name>.toml      developer_instructions = body; sandbox read-only for reviewers
  .opencode/agents/<name>.md     mode: subagent; permission.edit: deny for reviewers
tools/hooks/pretool.sh         # one dispatcher over the existing guards (Claude/Codex JSON in, exit 2 = block)
.opencode/plugins/guards.ts    # tool.execute.before → shells out to pretool.sh, throws on exit 2
opencode.json                  # permission block + mcp.figma-local
.codex/config.toml             # + [mcp_servers.figma-local]
```

Rules that make this work, all from the tests above:

- **Agent frontmatter:** keep it to `name` + `description` in the canonical file. Any `tools:` key makes opencode reject the *whole config*, and `model: sonnet` becomes a broken provider id there [L]. Harness-specific keys only live in generated adapters.
- **Skills:** always set `name:`, since opencode silently drops a skill without it [L]. Don't depend on `$ARGUMENTS` (Codex substitution is unverified); write "the target the user passed". Mark user-invoked skills with `disable-model-invocation: true` (Claude) + `agents/openai.yaml` `allow_implicit_invocation: false` (Codex).
- **No `@path` imports** outside `CLAUDE.md`. Codex and opencode show them literally [L]. Write "Read `agents/reviewers/roles/qa.md` first" instead.
- **Hooks:** Codex speaks Claude's hook JSON, but edits arrive as `apply_patch` with the patch text in `tool_input.command` (no `file_path`), and there is no `CLAUDE_PROJECT_DIR`. The dispatcher extracts paths from patch headers and locates the repo with `git rev-parse`. Once the Python policy's unique checks are ported, it retires.
- **Codex trust:** project `config.toml`, hooks and rules load only for a trusted project, and each hook needs a hash approval via `/hooks`. Changing hook commands re-prompts once per machine.
- **Subagent dispatch wording:** `pipeline.md` gets one mapping table: Claude uses the `Agent` tool with the role name, Codex uses `spawn_agent` with the role name, opencode uses the `task` tool / `@role`, and with no subagent support you run the role yourself in a fresh session from `agents/<role>.md`. Everything else says "dispatch the `<role>` role".
- **Tracker:** add `tools/plane` (thin wrapper resolving `plane.sh`) so `context/issue-tracking.md` names a path, not a Claude plugin.
- **Memory:** repo-relevant notes in Claude auto-memory (device fleet, e2e quirks, llama-server wire facts, bundle verification) should graduate into `context/ops/` docs with an `AGENTS.md` pointer. Otherwise Codex/opencode repeat mistakes Claude has already learned.
- **Signature:** the pipeline-reviewer PR template says `· Claude Code`; make it `· <harness>`.
- **Parity check:** `tools/sync-agents.sh --check` in a pre-commit hook fails when adapters drift from `agents/`.

## 6. Suggested order

**Status 2026-09-11:** P1 landed, except the Python-policy retirement and memory graduation. Verified:
- opencode loads all 21 roles and 8 skills.
- A live opencode run had `git worktree prune` blocked by the guard plugin.
- Claude hot-reloaded all 8 skills through the symlinks.
- The Codex TOML agents parse and all 8 skills appear in the prompt. A live `spawn_agent` check is blocked by the account's usage limit until 2026-09-17.

Agents became single files (Claude/opencode symlinks + Codex stubs). Codex permissions now match: a sandbox profile with writable `.git` and caches, `git reset`/`git rebase` prompt, and the curl/wget ban is gone.

**T1 + T7 landed:** flow index in `context/architecture/README.md` and intake reads only matching flows. `orchestrator/README.md` is deleted, guard messages point at `tools/create-worktree.sh`, the research doc is marked historical, and the README is rewritten (2,000 → ~900 words, with a harness table).

1. **P1: portability plumbing (mechanical, low risk).** Canonical `agents/` + `.agents/skills`, generator + `--check`, symlink, hook dispatcher + opencode plugin, MCP/permission parity, `tools/plane`, signature fix. Verify with `codex` (`spawn_agent` lists roles; hooks block an edit under `repos/pocketpal-ai`) and `opencode debug agent` / a blocked edit.
2. **T1 + T7:** intake index-based loading, stale docs out. Biggest token win, no behaviour change.
3. **T2–T6:** rewrite the stage agents in the new format, one at a time, using `writing-for-agents` as the rubric. Diff each against the old file to confirm every gate/verdict/artifact survives.
4. **F1–F6:** the freedom policy. These are judgement calls for the maintainer; land them as one `AGENTS.md` change so they are easy to review or revert.
5. Validate by re-running one past quick task and one standard task end to end under two harnesses. Compare artifacts and verdicts with the originals.
