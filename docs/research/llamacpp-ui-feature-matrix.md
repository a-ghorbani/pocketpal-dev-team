# llama.cpp UI apps vs PocketPal — feature matrix (2026-09-03)

**Question:** what do the ggml-org user-facing apps (the `llama-ui` web UI shipped inside `llama-server`, `llama-server` itself, and the *Llama* menu-bar apps for macOS and Windows) offer that PocketPal's llama.cpp integration (via `llama.rn`) does not, and how relevant is each item to a phone?

**Snapshot compared**

| Side | Version | Evidence |
| --- | --- | --- |
| llama.cpp | HEAD `e107984b` (2026-09-03). Web UI now lives at `tools/ui/` ("llama-ui", SvelteKit); `tools/server/webui/` is gone. Unified `llama` binary (`llama serve`, `llama cli`, `llama fit-params`); default port moving 8080 → 9931. | shallow clone; `tools/server/README.md`; discussion #23875 |
| Llama for macOS (ex-LlamaBarn) | 0.42.0 (2026-09-02), pins llama build b10679; router mode on `localhost:9931`; network access + QR pairing landed in 0.42 | `ggml-org/Llama-macOS` tags |
| Llama for Windows | 0.11.0 (2026-08-24), WinUI 3 tray app mirroring the Mac app | `ggml-org/Llama-Windows` |
| PocketPal | 1.17.0 at submodule `8488077a`, `llama.rn` 0.13.0-rc.0 → llama.cpp **b10335**. `origin/main` (1.17.2) is on rc.1 → **b10588**; the two tags have an identical TypeScript API. | `package.json`, llama.rn `src/version.ts` |

Mobile examples in the llama.cpp repo (`examples/llama.swiftui`, `examples/llama.android`) are single-screen demos (raw completion, bench, download list) and are not compared row by row.

**Relevance rating** (how much PocketPal should care, on a phone, given what `llama.rn` already exposes):

| Rating | Meaning |
| --- | --- |
| 5 · Core | Fixes a top on-device pain point; the llama.rn hook exists or is one upstream ask away |
| 4 · High | Clear user value on a phone; moderate work |
| 3 · Medium | Valuable for a segment, or as a remote-server client feature |
| 2 · Low | Marginal on a phone, or heavy for the value |
| 1 · Not for a phone | Desktop / server / browser-shell concept |
| — | Parity, or PocketPal is already ahead |

**Status legend:** Parity · Partial · Missing · PocketPal ahead.

## Headline


- Rows compared: **78** — parity 19, partial 12, missing 42, PocketPal ahead 5.
- PocketPal is ahead on samplers exposed in UI, benchmark + leaderboard, TTS, Pals/persona library, localisation, and the live-camera vision Pal. It is behind on everything that landed in llama.cpp in 2026 around **reasoning budgets, memory auto-fit, KV persistence, DRY, ngram speculation, and desktop-server pairing**.
- The four rating-5 items are each small on the PocketPal side because llama.rn already carries the parameter or the desktop side already does the work: reasoning token budget, memory auto-fit (needs a llama.rn upstream ask), QR pairing with the Llama app, and the remote router load/progress path.

### Shortlist (rating 4–5)

| Rating | Feature | Area | Why |
| --- | --- | --- | --- |
| 5 | Memory-aware auto-fit of context and GPU layers | Model & memory management | Load-time OOM is the top crash class on phones. Ask llama.rn to expose llama.cpp's params-fit, then auto-clamp instead of only warning. |
| 5 | Reasoning token budget | Reasoning controls | Runaway thinking is the number-one on-device complaint: minutes of tokens, battery, then context-full. llama.rn exposes thinking_budget_tokens; wire the effort selector to it. |
| 5 | Pair with a desktop server by QR code | PocketPal as a client of llama-server | The desktop side already prints the QR. A 'Scan to add server' button makes PocketPal the default phone client for every Llama-app user; a day of work. |
| 4 | Continue generation (assistant prefill) | Chat & conversations | Small models stop on n_predict or a bad EOS often. llama.rn already has prefill_text on completion(); cheap to add as a footer action. |
| 4 | Conversation search | Chat & conversations | Sessions live in WatermelonDB/SQLite; a LIKE query over message text is enough for v1. Frequently requested for long-lived local history. |
| 4 | Context usage gauge | Chat & conversations | Mobile n_ctx is small (2048 default). A persistent used/total gauge beats a threshold banner, and the current 'used' count under-reports on cache reuse. |
| 4 | Speculative decoding: model-free ngram drafts | Context, KV cache, performance | ngram drafting costs zero extra memory and helps exactly the repetitive, template-heavy outputs phones produce. llama.rn's spec_type field should accept it; verify, then offer it as the default when no draft exists. |
| 4 | Prompt-cache / KV state persistence across reloads | Context, KV cache, performance | After auto-release or an app kill the whole conversation is re-prefilled on the next message: the slowest thing a phone does. Save the session on release, restore on load. |
| 4 | Audio input to audio-capable models | Attachments & input modalities | Voice is a top mobile ask. Two routes: mtmd audio through llama.rn (one model, audio-native) or whisper.rn (any model). Decide once; do not build both. |
| 4 | Context tier picker with memory cost per tier | Model & memory management | Add the KV-cache byte cost next to each preset; the estimator already knows n_layers, n_embd, heads, cache type. |
| 4 | Downloads: pause/resume, sharded GGUF, sidecar resolution, disk preflight | Model & memory management | Mobile networks drop. Resume (HTTP Range) and SHA-256 from HF metadata are cheap. Sharded GGUF unlocks several current releases. |
| 4 | Router model load/unload with live progress | PocketPal as a client of llama-server | Let the phone load an unloaded model on the desktop and show the progress bar instead of a spinner-until-timeout. |
| 4 | Forward the full sampling set to llama-server | PocketPal as a client of llama-server | The controls exist and are silently ignored for llama.cpp servers. Forward them when server type is llama.cpp (and vLLM where accepted). |
| 4 | LaTeX / KaTeX math | Rendering | Small models emit LaTeX constantly for homework-style prompts and it renders as garbage. A WebView-backed KaTeX block, like the existing HTML preview, is the pragmatic route. |
| 4 | DRY repetition sampler | Sampling & generation parameters | Repetition loops are the second most common small-model failure after runaway thinking. llama.rn has the dry_* fields; add one 'Anti-repetition' control with sane defaults (0.8 / 1.75 / 2). |

## Matrix

Surface tags on the llama.cpp column: **UI** = llama-ui web UI, **SRV** = llama-server, **APP** = Llama macOS/Windows app.

### Chat & conversations

| Feature | llama.cpp | PocketPal | Status | Relevance | Notes |
| --- | --- | --- | --- | --- | --- |
| Streaming, stop, regenerate (also with another model) | Yes `UI` | Yes | Parity | — | Parity. PocketPal regenerate-with-another-model reloads the model; llama-ui switches in router mode. |
| Edit any message (user, assistant, system) | Edits fork a branch; assistant and system turns editable `UI` | User turns only | Partial | 3 | Editing an assistant turn is how people steer a small model. Data model already stores turns; needs UI + re-send from that point. |
| Message branching / tree conversations | Parent/children tree, branch nav, full tree exported `UI` | Whole-session duplicate only | Missing | 3 | Regenerate today discards the previous answer. A minimal 'previous / next answer' pager on the assistant turn gets most of the value without a tree UI. |
| Continue generation (assistant prefill) | Experimental Continue button; APPEND_TEXT / NEXT_TURN intents `UI` | No | Missing | 4 | Small models stop on n_predict or a bad EOS often. llama.rn already has prefill_text on completion(); cheap to add as a footer action. |
| Conversation search | Cmd/Ctrl+K search route over IndexedDB `UI` | No (HF model search only) | Missing | 4 | Sessions live in WatermelonDB/SQLite; a LIKE query over message text is enough for v1. Frequently requested for long-lived local history. |
| LLM-generated conversation titles | Optional; prompt template; first-line fallback `UI` | First message truncated to 40 chars | Missing | 3 | One short extra generation per new session. Fine on-device if run after the first reply and cancellable; must never block the first token. |
| Pinned conversations | Yes (2026-06) `UI` | Yes | Parity | — | Parity. |
| Per-message stats (tok/s, tokens, duration) | Default on; per agentic turn too `UI` | tok/s, ms/token, TTFT, draft tokens | Partial | 3 | PocketPal omits prompt tokens and prompt-eval speed. On phones prompt processing is the slow half; show it. |
| Context usage gauge | Live gauge in the composer (2026-07) `UI` | 80% warning banner + context-full banner | Partial | 4 | Mobile n_ctx is small (2048 default). A persistent used/total gauge beats a threshold banner, and the current 'used' count under-reports on cache reuse. |
| Export / import | JSON, JSONL (llama.app producer), ZIP; auto-detected; full tree `UI` | JSON + Markdown export; JSON import | Parity | — | Parity for the mobile case. Reading llama.app JSONL would let a desktop history move to the phone: low value, low cost. |
| Resumable streams | X-Conversation-Id + GET /v1/stream reattach; retries while model loads `SRV` | No | Missing | 3 | Only for remote servers, but it is exactly the mobile failure: iOS drops the socket on backgrounding. Local inference is unaffected. |
| Conversation tabs, bulk select, marquee selection | Yes `UI` | No | Missing | 1 | Desktop window idioms; nothing to port. |
| Slash commands (/model, /cwd, /prompt) | Yes `UI` | No | Missing | 1 | Keyboard-first; the phone has a model picker already. |
| Draft persistence per conversation | Unsent text + files kept `UI` | Not verified | Missing | 2 | Nice on mobile (app killed in background); verify whether ChatInput already restores drafts before scoping. |

### Attachments & input modalities

| Feature | llama.cpp | PocketPal | Status | Relevance | Notes |
| --- | --- | --- | --- | --- | --- |
| Image attachments (vision) | JPEG/PNG/GIF/WebP/SVG/HEIC; EXIF fix; max-megapixel downscale `UI` | Camera + library; mmproj auto-pairing; per-model vision toggle | Parity | — | Parity. Check HEIC from iOS camera roll is converted before hitting mtmd (image-picker usually does). |
| Audio input to audio-capable models | MP3/WAV/OGG upload + microphone recording (MediaRecorder) `UI` | No; ASR design (asr.md) is whisper-based and not on main | Missing | 4 | Voice is a top mobile ask. Two routes: mtmd audio through llama.rn (one model, audio-native) or whisper.rn (any model). Decide once; do not build both. |
| PDF attachments (text extract, or as images with fallback) | pdfjs extraction; 'parse as image'; passthrough (2026-09) `UI` | No | Missing | 3 | Students and field users share PDFs. Text extraction in RN is doable; page-as-image needs a rasteriser. Budget-aware chunking is the hard part on a 2k–8k context. |
| Text / code file attachments (~40 types, long paste to file) | Yes `UI` | No | Missing | 3 | Cheap: read file as text, inject as a fenced block with a size cap tied to n_ctx. |
| Video input | MP4/OGG to video models; --video-fps `UI` | Real-time video Pal (1 fps frame capture to a VLM) | Parity | — | Different mechanism, same job. PocketPal's live camera loop is the better mobile shape. |
| Modality validation from model capabilities | Blocks unsupported media using /props modalities `UI` | Gated by activeModelCaps.visionActive | Parity | — | Parity. |

### Reasoning controls

| Feature | llama.cpp | PocketPal | Status | Relevance | Notes |
| --- | --- | --- | --- | --- | --- |
| Thinking on/off + effort | Default/Off/Low/Medium/High/Max; template-detected `UI` | Toggle + effort selector; per-model override; learned/detected precedence | Parity | — | Parity on the control surface. |
| Reasoning token budget | Effort maps to a hard budget (512/2048/8192/-1) via reasoning_budget_tokens `UI` | Only reasoning_effort in chat_template_kwargs; no token cap | Missing | 5 | Runaway thinking is the number-one on-device complaint: minutes of tokens, battery, then context-full. llama.rn exposes thinking_budget_tokens; wire the effort selector to it. |
| End reasoning now | POST /v1/chat/completions/control reasoning_end (2026-06) `UI` | No | Missing | 3 | 'Answer now' button while the model thinks. Needs a llama.rn/native hook to inject the closing tag mid-stream; ask upstream. |
| Exclude reasoning from context / disable parsing | Both settings `UI` | include_thinking_in_context switch | Parity | — | Parity for the useful half. |
| Reasoning block display, in-progress preview | Collapsible; Markdown; single-line live preview `UI` | ThinkingBubble / ReasoningBlock with duration | Parity | — | Parity. |

### Tools, agents, MCP

| Feature | llama.cpp | PocketPal | Status | Relevance | Notes |
| --- | --- | --- | --- | --- | --- |
| Client-side agentic loop with turn cap | agenticMaxTurns=10; per-turn stats `UI` | AgentRunner + Pal talents | Parity | — | Parity in shape. |
| Built-in tool set | Server: read/write/edit file, grep, glob, shell, get_info. Browser: run_javascript sandbox, symbolic math, get_datetime, read_media `UI SRV` | web_search, read_url, calculate, datetime, render_html | Partial | 3 | Phone tools should be phone-shaped. Worth adding: run_javascript in the existing WebView sandbox; read_media (describe an attached image/audio). File/shell tools are not for a phone. |
| Tool permission model (once / always / deny) | Persisted per tool, per-conversation policy `UI` | None; talents run when the Pal enables them | Missing | 3 | Becomes necessary the moment tools can leave the device (web_search already does) or MCP servers arrive. |
| MCP client | Browser MCP client: servers, prompts, resources, health, timeouts; --ui-mcp-proxy for remote `UI` | No | Missing | 3 | HTTP/SSE MCP servers are reachable from a phone; stdio ones are not. Fits the Pal talents model as 'remote talents'. Do after the permission model. |
| Server-side tools / --agent / stdio MCP on the server | --tools, --tools-runtime docker|podman|ssh, --mcp-servers-config `SRV` | No | Missing | 3 | As a remote client, PocketPal could list GET /tools and let the desktop run them. Cheap way to give the phone a coding-agent backend. |
| @-mentions of files, working directory | Server file_glob_search; x-tool-cwd `UI SRV` | No | Missing | 1 | Desktop filesystem concept. |

### Rendering

| Feature | llama.cpp | PocketPal | Status | Relevance | Notes |
| --- | --- | --- | --- | --- | --- |
| Markdown GFM, tables, code highlighting with copy | Yes `UI` | marked + render-html; tables; syntax-highlighter | Parity | — | Parity. |
| LaTeX / KaTeX math | KaTeX with LaTeX protection `UI` | No | Missing | 4 | Small models emit LaTeX constantly for homework-style prompts and it renders as garbage. A WebView-backed KaTeX block, like the existing HTML preview, is the pragmatic route. |
| Mermaid diagrams with preview | mermaid 11, interactive preview, source toggle `UI` | No (HTML preview exists) | Missing | 2 | Could ride the same WebView bubble; niche on a phone screen. |
| HTML / JS code preview | Dialog preview of code blocks `UI` | render_html talent → HtmlPreviewBubble | Parity | — | PocketPal treats it as a first-class GenUI surface; ahead in intent. |
| Raw output toggle, full-height code | Developer settings `UI` | No | Missing | 2 | Debug aid; low value for end users. |

### Model & memory management

| Feature | llama.cpp | PocketPal | Status | Relevance | Notes |
| --- | --- | --- | --- | --- | --- |
| Memory-aware auto-fit of context and GPU layers | Server --fit / llama fit-params; Llama app probes fit-params and picks a context tier per model `SRV APP` | Estimator + confirm dialog; no automatic shrink of n_ctx / n_gpu_layers | Partial | 5 | Load-time OOM is the top crash class on phones. Ask llama.rn to expose llama.cpp's params-fit, then auto-clamp instead of only warning. |
| Context tier picker with memory cost per tier | 4k…256k tiers, each showing the RAM it costs `APP` | IncreaseContextSheet offers presets capped at the GGUF context_length, no cost shown | Partial | 4 | Add the KV-cache byte cost next to each preset; the estimator already knows n_layers, n_embd, heads, cache type. |
| Model catalog sized to the device | llama.app catalog; Discover shows families that fit this Mac `APP` | Device-rules tiers, 20 files per platform, jsDelivr override | Parity | — | PocketPal's per-device rules are the richer mechanism. |
| Downloads: pause/resume, sharded GGUF, sidecar resolution, disk preflight | Llama app and server POST /models download resolve shards, mmproj and MTP sidecars like llama.cpp; pause/resume `APP SRV` | Cancel only; no split-GGUF; size-only integrity check; mmproj/draft paired manually (same repo) | Partial | 4 | Mobile networks drop. Resume (HTTP Range) and SHA-256 from HF metadata are cheap. Sharded GGUF unlocks several current releases. |
| One-click load/unload, unload when idle | Menu-bar toggle; 5m/15m/1h idle unload `APP` | Auto-release on background + last-used auto-load | Parity | — | Parity for mobile; the OS handles idle memory pressure. |
| Install deep links (llama://install?repo=&quant=) | Yes; legacy llamabarn:// `APP` | HF hub deep link + hubRunLink | Parity | — | Parity. Consider accepting llama:// too so llama.app catalog links open PocketPal on a phone: tiny cost. |
| Model info (ctx, modalities, slots, parsed quant/param badges) | Dialog + badges `UI APP` | ModelCard shows architecture, context, vision, projector | Parity | — | Parity. |
| Router mode: several models resident, LRU eviction | --models-dir, --models-max, LRU `SRV` | Single model | Missing | 1 | Phone RAM rules it out. |
| Engine update channel | App pins a llama build; staged background updates `APP` | Ships llama.rn 0.13.0-rc.0 (b10335); main has rc.1 (b10588); HEAD is ~b10700 | Partial | 3 | Not a feature to build, but a cadence to keep: PocketPal is 100–350 builds behind, and the 2026 spec-decode and reasoning-budget work lives in that gap. |

### Sampling & generation parameters

| Feature | llama.cpp | PocketPal | Status | Relevance | Notes |
| --- | --- | --- | --- | --- | --- |
| Core samplers (temp, top_k, top_p, min_p, typ_p, XTC, penalties, mirostat, seed) | Exposed (mirostat/seed only via Custom JSON) `UI` | All exposed with ranges; per-session and per-Pal layers | PocketPal ahead | — | PocketPal exposes more than llama-ui does. |
| DRY repetition sampler | dry_multiplier/base/allowed_length/penalty_last_n `UI SRV` | No | Missing | 4 | Repetition loops are the second most common small-model failure after runaway thinking. llama.rn has the dry_* fields; add one 'Anti-repetition' control with sane defaults (0.8 / 1.75 / 2). |
| Server-default sync with Default/Custom indicator | Numeric fields sync to /props default_generation_settings `UI` | Not read from /props | Missing | 3 | Remote-only. Read default_generation_settings and show 'server default' so users stop fighting the server config. |
| top-n-sigma, adaptive-p, dynatemp | Flags and Custom JSON `SRV` | No | Missing | 2 | Marginal on Q4 small models; verify llama.rn exposes them before scoping. |
| Structured output (JSON schema / grammar) in chat | response_format json_schema; Custom JSON `SRV UI` | Code-only (Pal system-prompt generator); dev screen | Missing | 2 | Useful for Pal authors and automation, not chat. Expose behind an advanced Pal setting if at all. |
| logit_bias, ignore_eos, n_probs display, sampler order | Server flags `SRV` | No | Missing | 1 | Power-user CLI knobs. |
| Backend (GPU) sampling | --backend-sampling (2026) `SRV UI` | No | Missing | 2 | Could lift tg on Metal for tiny models; depends on llama.rn exposing it. Measure on a real device first. |

### Context, KV cache, performance

| Feature | llama.cpp | PocketPal | Status | Relevance | Notes |
| --- | --- | --- | --- | --- | --- |
| KV-cache quantisation, flash attention, mmap/mlock, repack | All flags `SRV` | All in Settings (cache types gated on FA; bf16 not offered) | Parity | — | Parity. |
| Speculative decoding: model-free ngram drafts | --spec-type ngram-cache / ngram-simple / ngram-map-k; auto-detect `SRV` | draft-mtp (embedded) and paired draft model only | Partial | 4 | ngram drafting costs zero extra memory and helps exactly the repetitive, template-heavy outputs phones produce. llama.rn's spec_type field should accept it; verify, then offer it as the default when no draft exists. |
| Speculative decoding: EAGLE3 / DFlash / DSpark heads | Yes (2026) `SRV` | No | Missing | 2 | Needs trained heads per model; catalogue is thin for sub-4B models. Watch, don't build. |
| Prompt-cache / KV state persistence across reloads | /slots save|restore|erase; --cache-ram; checkpoints `SRV` | No (llama.rn saveSession/loadSession unused) | Missing | 4 | After auto-release or an app kill the whole conversation is re-prefilled on the next message: the slowest thing a phone does. Save the session on release, restore on load. |
| Context shift | --context-shift (off by default) `SRV` | Off; context-full banner + reload with larger n_ctx | Missing | 3 | PocketPal's explicit banner is the safer UX, but a per-session 'keep going, forget the oldest turns' opt-in via llama.rn ctx_shift would remove a dead end. |
| Pre-fill KV after response | Developer setting `UI` | No | Missing | 2 | Hides the next turn's template prefill; small win on-device, costs battery while idle. |
| CPU-MoE / expert offload, --n-cpu-ffn | Flags `SRV` | No (llama.rn has n_cpu_moe) | Missing | 2 | Only matters if small MoE GGUFs land in the catalogue; then it decides whether GPU offload fits. |
| LoRA adapter hot-swap | GET/POST /lora-adapters `SRV` | No (llama.rn API present) | Missing | 2 | Interesting for Pals as 'personality adapters', but the GGUF-LoRA ecosystem for small models is thin. |
| Embeddings / reranking | /embeddings, /reranking, pooling `SRV` | No (llama.rn API present) | Missing | 3 | Enabler, not a feature: on-device semantic session search and PDF chunk retrieval both need it. |
| Load mode auto|mmap|mlock|dio, lazy mode | --load-mode, --lazy-mode (2026) `SRV` | mmap / mlock switches | Parity | — | Parity for what a phone can use. |
| Built-in benchmark with history and leaderboard | llama-bench CLI; swiftui example prints tok/s `SRV` | Bench screen, presets, pp/tg averages, peak memory, opt-in leaderboard submit | PocketPal ahead | — | PocketPal is ahead here. |

### PocketPal as a client of llama-server

| Feature | llama.cpp | PocketPal | Status | Relevance | Notes |
| --- | --- | --- | --- | --- | --- |
| Pair with a desktop server by QR code | Llama app 0.42.0: Network access Off/Tailscale/LAN, shows a QR 'for phones' `APP` | Manual URL + key entry | Missing | 5 | The desktop side already prints the QR. A 'Scan to add server' button makes PocketPal the default phone client for every Llama-app user; a day of work. |
| /props discovery | default_generation_settings, chat_template_caps, modalities (vision, audio), build_info, model_alias `SRV` | Reads n_ctx and modalities.vision only | Partial | 3 | Also read modalities.audio, the sampling defaults and build_info for the server row. |
| Router model load/unload with live progress | /models/load|unload, /models/sse progress, ?model= `SRV UI` | Lists /v1/models; sends model id | Partial | 4 | Let the phone load an unloaded model on the desktop and show the progress bar instead of a spinner-until-timeout. |
| Forward the full sampling set to llama-server | All completion params accepted `SRV` | Drops top_k, min_p, penalties, seed, XTC, typical_p, mirostat | Missing | 4 | The controls exist and are silently ignored for llama.cpp servers. Forward them when server type is llama.cpp (and vLLM where accepted). |
| Per-request reasoning budget, reasoning_effort:none | Accepted on /v1/chat/completions `SRV` | Only enable_thinking / reasoning_effort kwargs | Partial | 3 | Same fix as the local budget; send reasoning_budget_tokens when the server is llama.cpp. |
| Timings in remote responses | timings.cache_n, usage.cached_tokens, predicted_per_second `SRV` | No tok/s footer for remote turns | Missing | 3 | Data is already in the response; render the same footer as local. |
| Transcriptions API on the server | /v1/audio/transcriptions (2026) `SRV` | No | Missing | 2 | A no-model-on-phone voice path when connected to a desktop; secondary to the on-device decision above. |
| Anthropic /v1/messages, OpenAI /v1/responses, Vertex API | Yes `SRV` | OpenAI chat completions only | Missing | 1 | Chat completions is enough. |

### Desktop / platform-only

| Feature | llama.cpp | PocketPal | Status | Relevance | Notes |
| --- | --- | --- | --- | --- | --- |
| Quick prompt global hotkey / Alt+Space overlay | Spotlight-style panel (macOS 0.40, Windows) `APP` | Apple Shortcuts / App Intents | Parity | — | The mobile analogues are Shortcuts, a share-sheet extension and a home-screen widget; PocketPal has the first. |
| PWA, keyboard shortcuts, custom CSS, admin config file | Yes `UI` | n/a | Missing | 1 | Browser/desktop shell concerns. |
| API request builder (curl / Python / JS snippets) | Yes (0.41) `APP` | No | Missing | 1 | Developer desktop tool. |
| Serve the model to the network (LAN / Tailscale) | Yes (0.42) `APP` | No | Missing | 1 | A phone as an LLM server is a curiosity, not a product. |
| Localised UI | None (no i18n in tools/ui) `UI` | 20+ locales via Weblate | PocketPal ahead | — | PocketPal is ahead. |
| Text-to-speech output | TTS models via mtmd only `SRV` | Kitten / Kokoro / Supertonic / system TTS | PocketPal ahead | — | PocketPal is ahead. |
| Prompt / persona library | System message field only `UI` | Pals with per-Pal model, settings, talents; PalsHub | PocketPal ahead | — | PocketPal is ahead. |

## Method and caveats

- llama.cpp side: shallow clone of `ggml-org/llama.cpp` at HEAD `e107984b`, reading `tools/ui/src` (settings registry, components, services), `tools/server/README.md`, `docs/speculative.md`, and the commit log since 2026-03 for dates; `ggml-org/Llama-macOS` at tag 0.42.0; `ggml-org/Llama-Windows` README. The pinned "server changelog" issue (#9291) has one 2026 entry, so recency came from commits.
- PocketPal side: the read-only submodule at `8488077a` (grep and file reads under `src/`), the `context/architecture/*.md` flow docs, and the llama.rn TypeScript API at tags `v0.13.0-rc.0` and `v0.13.0-rc.1`. `node_modules/llama.rn` on disk is a stale 0.11.5 and was not used.
- "llama.rn exposes X" claims come from `src/types.ts` at those tags. Items marked "verify llama.rn exposes" were not confirmed field by field.
- Ratings are a judgement call made for a phone form factor; effort estimates in the notes are indicative, not plans.
