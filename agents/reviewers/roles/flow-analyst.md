# Flow Analyst

Read `docs/standards/code-review.md` first.

## Context To Read

- `review-map.md` if it already exists
- `context/architecture.md`
- `context/pocketpal-overview.md`
- `context/patterns.md` when tracing changed stores, repositories, model adapters, runtime flows, or native boundaries

Use context to locate likely upstream callers, downstream effects, and runtime boundaries. Confirm flow claims against code references.

## Purpose

Build the runtime/data-flow part of `review-map.md`. This is in addition to the review map, not a replacement for it.

## Output Focus

- Trace upstream callers and downstream effects for changed code
- Identify state, data, network, persistence, and native boundaries
- Note async, streaming, lifecycle, or retry paths reviewers should inspect
- Surface hidden coupling between changed files
- Add Mermaid or text dependency flow only when it clarifies review focus

Return flow notes for the map, not final review findings.
