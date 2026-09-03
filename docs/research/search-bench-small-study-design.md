# SearchBench-Small — Study Design (DRAFT v0.1)

**Working title:** *Web Search with Small Language Models: A Benchmark of Agentic Search on On-Device-Class LLMs (<8B)*
**Target output:** a living benchmark + leaderboard published on pocketpal.dev, backed by a methodology report (blog post first; arXiv preprint if results warrant).
**Status:** draft for maintainer review — nothing here is committed scope yet.

---

## 1. Research questions

- **RQ1 (models):** How do small open models (0.5B–8B, across families and quantizations) rank at search-grounded question answering, and where is the capability floor for usable agentic search?
- **RQ2 (harness):** How much of the outcome is the *scaffold* rather than the model — agentic tool-loop vs one-shot RAG injection vs framework-decomposed queries? (LiveNewsBench found ±42pp swings from scaffolding on *frontier* models; unknown for small ones.)
- **RQ3 (knobs):** Which pipeline parameters dominate for small models: results-per-search, token budget, turn budget, snippet-vs-page-read, provider?
- **RQ4 (safety/UX):** What are the hallucination-vs-abstention trade-offs, tool-format compliance rates, and latency/energy costs — the dimensions that decide whether on-device search is *shippable*, not just scoreable?

## 2. What exists (and the gap)

| Prior work | Covers | Gap we fill |
| --- | --- | --- |
| LiveNewsBench (arXiv 2602.13543, MIT) | fresh multi-hop news QA, frontier + 8B models, quarterly refresh | nothing below 8B; no quantization; no latency/energy; no harness-knob ablations |
| SimpleQA / FreshQA / BrowseComp | static QA sets, frontier models | contamination (SimpleQA memorizable); staleness; no small models |
| tavily-search-evals | provider comparison on SimpleQA | provider-only; frontier extraction model |
| Vendor benchmarks (Exa/Brave/Parallel/You.com) | their own APIs | vendor-run; not model-centric |

**Positioning:** the *on-device regime* — small models, quantized, tight context budgets, mobile latency — is exactly PocketPal's niche and empirically unstudied.

## 3. Study components

### 3.1 Data generation (component A)
Fresh, contamination-free QA at whatever cadence we choose (prototype already running):

1. Wikipedia Current Events (daily pages) → event bullets + their **cited source articles** (fetched via reader, no search API in curation).
2. QA generation with local LLMs using LiveNewsBench's curation prompts (MIT) adapted; short-answer factual, self-contained questions.
3. **Three filter gates:** self-consistency (independent re-answer from article must match); strong-model verification pass; **no-search contamination gate** (question answerable without search by the weakest AND strongest eval model → dropped).
4. Human verification on a sample (target: ≥100 questions human-checked per release; report annotator agreement like LiveNewsBench's 92%).
5. Release format: JSONL {id, question, gold, sourceUrl, eventDate, category}; dated releases.

**Methodological contribution — frozen retrieval snapshots:** for every question we pre-execute a set of canonical queries per provider on release day and archive the returned results. This enables:
- a **fixed-retrieval track** (all models see identical retrieval → isolates grounding/synthesis ability from query-formulation skill; fully reproducible offline; zero credits to re-run),
- a **live/agentic track** (model formulates its own queries; cached per (query, provider, day) to bound cost),
and lets others reproduce our numbers exactly — which no live-search benchmark currently allows.

### 3.2 Harness study (component B)
Survey then select 3–4 representative scaffolds (all runnable against the same llama.cpp server):

| Scaffold | Represents | Source |
| --- | --- | --- |
| PocketPal talent loop (web_search+read_url, budgeted, forced-final-answer) | model-driven mobile agentic loop | ours (validated in PR #808 work) |
| ReAct 5-search+5-visit | the LiveNewsBench/smolagents standard | LiveNewsBench evals/ (MIT) |
| One-shot RAG injection | Open WebUI-style: search once, inject, answer | trivial to implement |
| Framework-decomposed queries | gpt-researcher/Perplexica-style: LLM generates 1–3 queries up front, passive answering | small adapter |

Fixed judge + datasets across all; the harness is the treatment.

### 3.3 Model evaluation (component C)
Ladder (all runnable on the existing llama-swap server; extend as needed):
- **Families:** Qwen 3.x (0.6B/1.7B/2B/4B/8B), Gemma 3/4 (1B/2B/4B), Llama 3.2 (1B/3B), Phi-4-mini, Ministral-3B, SmolLM3 — final list per server availability.
- **Quantization axis** (novel): Q4_K_M vs Q8_0 for 2–3 pivotal models — does quantization degrade tool-call fidelity/grounding? Directly decides what PocketPal should recommend on-device.
- **Anchors:** one ≥27B local model as ceiling reference; optionally one frontier API for context (clearly marked non-local).

### 3.4 Dimensions & metrics (component D)
Knobs (ablated on a subset, not full cartesian): results-per-search {3,5,10} · turn budget {1,3,5,7} · snippet-only vs read-enabled · provider {Tavily, Brave, +Exa} · format {labeled blocks vs JSON}.
Metrics per cell: accuracy (judge = strong model w/ SimpleQA prompt; judge validated against human labels on a sample) · hallucination rate (INCORRECT) · abstention (NOT_ATTEMPTED) · tool-format compliance (parse-failure rate) · mean tool calls · wall-clock latency · **generated+prompt tokens as energy proxy** (mobile-relevant).

## 4. Rigor requirements (what makes it publishable)

- n ≥ 100–200 questions per headline cell (round-3's n=15 was a smoke test); report Wilson CIs; paired comparisons on identical question sets; McNemar for config deltas.
- Fixed seeds/temps; all prompts, configs, traces, and frozen retrieval snapshots released (MIT), matching LiveNewsBench's openness.
- Judge validity: human-agreement study on ≥100 judged answers.
- Contamination: no-search baseline reported per model (their Table-6 method).
- Cost/infra transparency: credits, wall-clock, hardware documented.

## 5. Deliverables

1. **pocketpal.dev/benchmark** (or /search-bench): leaderboard (model × harness), methodology page, downloadable data.
2. **Report:** blog post with the headline findings; arXiv preprint if the harness/quantization findings are strong.
3. **Repo:** standalone open-source (bench generator + harnesses + traces), separate from the app.
4. **Feedback into product:** the winning config per model size ships as PocketPal defaults (already happening — PR #808).

## 6. Phasing

- **P0 (done/running):** harness prototype, round-3 SimpleQA/FreshQA smoke, live-news generator prototype (running now).
- **P1 — pilot (≈1 wk):** freeze v0 question set (n≈150, human-verify 50), frozen-retrieval snapshots, 4 harnesses implemented, 5–6 models, headline table. Decide: is the signal interesting enough to publish?
- **P2 — full matrix (≈2–3 wks):** full model ladder + quantization axis + knob ablations, stats, writeup, leaderboard page.
- **P3 — living benchmark:** automated weekly/monthly refresh + CI-style re-runs for new models; community submissions.

## 7. Decisions (maintainer)

**Resolved 2026-07-08:**
- **Name:** **SearchBench-Small**.
- **Search-credit strategy:** Brave (key provisioned in `dev-team/.env` as `BRAVE_API_KEY`) for the live track, + Tavily (existing) as a second provider for the provider-comparison axis, + frozen-snapshot caching to bound cost.
- **P1 model scope:** **Qwen ladder only** — qwen3-0.6b / qwen3-1.7b / qwen35-2b / qwen35-4b (single-family, cleanest size signal; expand families + quantization axis in P2).
- **P1 dataset:** **our fresh daily-news set** — scale the live-news generator to ~150 questions (SearchBench-Small v0), human-verify ~50.

**Still open:**
- Compute: 192.168.0.92 server only, or recruit a second machine for parallel cells in P2?
- Human verification: maintainer verifies the v0 sample via the generated `verify.html`; crowdsource in a later release?

## 8. P1 execution status (live)
- **v0 generation** (running): ~150 fresh Qs, 10-day window, self-consistency + 27B contamination gate, checkpointed → `datasets/searchbench-small-v0.json` + `verify.html` worksheet.
- **Provider comparison** (running): old vs ecosystem config × Tavily vs Brave on qwen35-4b over the 20-Q 2026-07-06 set → informs which provider(s) the ladder eval uses.
- **Next:** human-verify v0 → run the Qwen ladder × {old, ecosystem} config on the verified set with the chosen provider(s) → SearchBench-Small pilot leaderboard.

---
*Draft written 2026-07-06. Prototype artifacts: `worktrees/TASK-20260625-1135/experiments/web-search/` (harness, round-3 results, live-news generator in progress).*
