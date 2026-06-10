# Issue Tracking & Routing

How this dev team picks up work. The team is **agnostic to the issue tracker**: you hand it a reference, it resolves the source from the reference's *shape*, fetches the issue with the matching tool, then runs the normal pipeline. The orchestrator does not care which tracker the work came from.

> If the tracker ever changes, update **this file** (and the relevant tool script). Nothing else — skills, agents, CLAUDE.md — should hardcode tracker details; they all point here.

## Resolve a reference by its shape

| Reference shape | Source | Fetch with | Visibility |
|---|---|---|---|
| `#123`, `owner/repo#123` | GitHub | `gh issue view <n> --repo <repo> --json title,body,labels,assignees` | **public** |
| `FOU-123` | Linear | `./tools/linear.sh issues`, then match the identifier | internal |
| `POC-123` / `PAL-123` / `ADV-123` | Plane | `plane.sh show <ref>` | internal |
| anything else | — | treat as a free-form description → go straight to the orchestrator | — |

When handing off to the orchestrator, include a `Source:` tag (`github` / `linear` / `plane` / `description`) and the `Tracker ID` (the identifier) so downstream stages can honor the hygiene rule below.

## Trackers

- **GitHub** — tool: `gh`. Public product issues. IDs (`#123`) are public.
- **Linear** — tool: `./tools/linear.sh` (legacy). Prefix `FOU-`. Needs `LINEAR_API_KEY` in `.env`.
- **Plane** — tool: the `plane` skill (`plane` Claude Code plugin; CLI: `plane.sh`). Work-item references look like `POC-123`. Needs `PLANE_TOKEN` in `.env` (secret); the workspace slug + project map live in `~/.config/plane/plane.config`.

## Public-artifact hygiene

Internal tracker IDs — `FOU-*`, `POC-*`, `PAL-*`, `ADV-*` — must **never** appear in public GitHub artifacts (PR title/body/comments, commit messages) or in product source/tests/configs. GitHub `#123` references are public and may be cited freely.
