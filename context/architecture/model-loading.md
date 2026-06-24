# Model Loading & Device-Rule-Driven Preset List

How PocketPal sources its model list. Code is the source of truth; this keeps only what's hard to recover from it — cross-file contracts, non-obvious *why*s, traps. (Implemented in PR #772; `main` on merge.)

## Sources

Data-driven; no hand-maintained array (`defaultModels.ts` gone), no "suggestions" UI — device rules decide which presets fill the existing list, so the user only notices it differs by device. Two sources, one parser (`deviceRules/parse.ts`) and merge (`ModelStore.resolvePresetModels`/`candidateToPair`): the committed **bundled floor** (`store/bundledDeviceRules/rules.{android,ios}.json`, always present) and the **fetched** jsDelivr `rules.<platform>.json` (online override, fire-and-forget). The floor applies **synchronously of the fetch**, so a hanging network never empties a fresh install.

## Core idea: a candidate is a pre-known HF-browser add

A rule entry is just an HF model whose repo + filename we already know. List-build **synthesizes the minimal `(HuggingFaceModel, ModelFile)` the existing `hfAsModel` (`utils/index.ts`) reads, then calls it verbatim** — no new transform; the result is an `origin: HF` Model identical to an HF-browser add, rendered by the existing `ModelCard`. So the JSON is **thin**; `oid`/`lfs`/chat-template tokens are neither stored nor baked but resolve at download, safely, because:

- the URL is **deterministic** (`huggingface.co/{hf_repo}/resolve/main/{hf_filename}`), set at stub-build so `checkSpaceAndDownload` never early-returns on an empty URL;
- integrity **self-heals** — `checkModelFileIntegrity` sees the missing `lfs` on an `origin: HF` model and calls `fetchAndUpdateModelFileDetails`;
- templates are GGUF-embedded (resolved at load) or default-filled.

Cost vs. baking metadata into the JSON: the first integrity check pays one HF fetch. Fine — download is already online.

## id & migration

- id = `hf_repo/hf_filename` = `author/repo/filename` (what `hfAsModel` builds; the legacy PRESET convention). The candidate's `model` field is a label, **not** the id.
- Reconcile keys on the **full `model.id`** — not `{repo,filename}` (loses cross-author collision-safety), not `id && origin` (loses origin-spanning, which lets a downloaded legacy `origin: PRESET` suppress the duplicate `origin: HF` stub → no double card, no re-download).
- `MODEL_LIST_VERSION` 15 (single 14→15 bump). Migration keeps every downloaded model (any origin); `reconcilePresets` prunes only non-downloaded `isRulePreset` stubs gone from the fresh set (never downloaded/user/LOCAL). Empty resolve (transient signal failure) → **skip the version bump** so it retries next launch, never locking an empty list.

## Vision: explicit projector

`mmproj` names the projector; the app uses it directly and **not** the HF-browser quant-match (`getRecommendedProjectionModel`) — so projector quant is an **authoring** responsibility (pre-merge gate, no app-side check). It is synthesized as an LLM sibling and pushed as its own stub so the download path resolves it; detection is offline (filename-only, `MMProjRegex`); `mmproj.size_bytes` enters the fit check (`min_ram_gb` may exclude the ~1 GB projector). **`mmproj.hf_repo` must equal `hf_repo`** — `hfAsModel` pairs the projector under the LLM repo, so the parser drops cross-repo projectors (out of scope).

## Security (a trap — don't "simplify")

Untrusted CDN JSON drives download URLs and gates the HF token. The URL is **derived** with a hard-coded host, so `isHuggingFaceUrl` on it is tautological — **not** the boundary. Real guard, at parse: split `hf_repo` on `/`, require **exactly two non-empty parts**, `isSafePathSegment` (no `/`, `\`, `..`) on author/repo/filename, build the URL only then; same for `mmproj`, else drop the candidate whole. `DownloadManager` also strips the Bearer token for non-`huggingface.co` hosts.

## Misc non-obvious

- **Classifier** pure + total (last-resort → `low`). iOS `machine`→chip→class; Android `socModel`→`hardware`(`Build.HARDWARE`)→CPU-heuristic(`features`/`max_freq`); then `ram_bands`→`tier_matrix`. Android keeps `hardware`+`maxFreqMhz` distinct from the coalesced chipset.
- **Cutover:** `defaultModels.ts` gone; Lookie is now `LOOKIE_DEFAULT_MODEL` carrying an `hfModel` (else its download is an undownloadable no-op); `getOriginalModelName`→`getDisplayNameFromFilename`; completion fallback→`defaultCompletionParams`.
- **Schema** (`a-ghorbani/pocketpal-device-rules`, `1.2.0-draft`): required `{model, hf_repo, hf_filename}` (+ `mmproj.{hf_repo,hf_filename,size_bytes}` iff multimodal); optional `display_name/params/size_bytes/min_ram_gb`; ignored `quant/obs_tg/sha256/native_low_bit`. Incompatible/empty hosted doc → floor.
- **Deferred:** cross-repo projector; CI refresh of the bundled floor; background rules refresh; unified native signal read.

## Model load / error / recovery UI states

The list above sources models; this section is the **UI lifecycle** a card (or Chat) walks once the user acts on one. Presentational only — the native lifecycle is owned by `ModelStore` (`initContext` is the sole load entry; `proceedWithInitialization` is the sole writer of `context`/`engine`/active model and of `modelLoadError`).

**States** (per-model card, plus the Chat-side mirror):

- `idle` (downloadable) — primary action **Download**; gear; expand.
- `idle` (downloaded) — primary **Load**; gear + delete.
- `loading` — spinner on primary (`isContextLoading` && `loadingModel.id === model.id`); card non-interactive for load.
- `active` — `● Loaded` badge + **Unload**.
- `downloading` — progress bar + size + **Stop**.
- `warned` — inline DS `Label` (`status-warning` / `status-info`) + advisory copy; primary may be `disabled` (`!storageOk`).
- `error` — `ErrorSnackbar` on whichever screen triggered the load, carrying **Report** (+ Dismiss).

**Warning-vs-failure trigger boundary** (the contract):

- **Pre-load warning** (insufficient storage / low-or-short memory / multimodal mismatch / file-integrity) is a non-blocking advisory shown **before/instead-of** a load attempt. Sourced read-only from `useStorageCheck` / `useMemoryCheck` / `checkModelFileIntegrity`. Renders as an inline `Label` on the card; never a snackbar. Skipped for remote models (no local file).
- **Hard failure** is an `initLlama`/load error caught in `proceedWithInitialization` and surfaced as `modelLoadError` (`context: 'modelInit'`). Renders on the reskinned `ErrorSnackbar` (single action) → **Report** opens `ModelErrorReportSheet` (same submit payload). The existing snackbar-vs-dialog mutual exclusion (download-with-modelId ⇒ `DownloadErrorDialog`, else snackbar) is preserved.

**Crash-loop guard (do not regress).** A failed load sets `modelLoadError` exactly once and **rethrows without auto-retrying**. There is **no** auto-reload on failure and **no** snackbar Retry. Retry is **user-initiated only**: re-tap the card primary `load-button`, or Chat `ModelNotLoadedMessage` Load (both route back through `selectModel` → `initContext`). Metadata/details fetches keep swallowing failures and returning. No UI path may auto-call `selectModel`/`initContext` on failure. (Regression-gated by a `ModelStore` unit test asserting the failure path sets the error once and calls `initLlama` once.)

## Speculative decoding / draft model (MTP)

Speculative decoding is a global, opt-in extension of the model-load contract. It runs through the **same** `initContext` → `proceedWithInitialization` → `initLlama` path; it adds no new native-load entry point. (Consumes the published **llama.rn@0.12.5** — the release that synced llama.cpp to b9769 / merged PR #355 — as a normal prebuilt registry dependency; see the build note below.)

**Two modes, derived (never persisted as an enum):**

- **Embedded / hybrid MTP** — a self-contained model carries draft layers; `model_draft` left unset, speculative just enabled.
- **Separate-draft pairing** — a target + a distinct small draft model loaded together; `model_draft` = the draft file path.

The mode is computed at load by `resolveDraftConfig(model)` (read-only, runs **outside the mutex**, mirrors `resolveMultimodalConfig`). Draft-model selection has two channels with a fixed precedence — **per-target `Model.defaultDraftModel` (device-rules authored) wins; the global user-picked `contextInitParams.selectedDraftModelId` is the fallback**; a global pick is curated for no single target, so it loses to a per-target draft:

- `speculativeEnabled` false → **off**: forward no `spec_draft_*`, no `model_draft`. Identical to pre-feature load.
- a `defaultDraftModel` **or** (if absent) the global `selectedDraftModelId` that resolves to a **downloaded** file → **paired**: `model_draft` = path, `is_model_draft_asset: false`. Both channels resolve to the same paired shape through a single mode-derivation site.
- speculative on, no resolvable paired draft → **embedded** (also the harmless no-op for a non-MTP model). An upgraded record with nothing picked is a no-op: it loads identically to pre-feature.

`getEffectiveContextInitParams(filePath, draftConfig)` applies the mode as `?? user-value` fallbacks over the user's `contextInitParams` — **a mode default never overwrites an explicit user setting**. Paired defaults: `flash_attn_type 'off'`, `spec_draft_cache_type_k/v 'f16'`, `spec_draft_n_gpu_layers 99`. Embedded defaults: `flash_attn_type 'auto'`, `spec_draft_cache_type_k/v 'q8_0'`. The `spec_draft_n_max/n_min/p_min/p_split` tuning passes through verbatim in both speculative modes. Callers that pass no `draftConfig` (e.g. the benchmark runner) are unchanged.

**Graceful degradation, never a hard fail.** A missing/incompatible draft, a draft with `isDownloaded === false`, or a device that can't support MTP drops `model_draft` and loads the target normally — it never blocks the target load and never surfaces `modelLoadError` *for the draft alone*. (The "speculative no-op" half — speculative on, non-MTP model, no draft → no native error — rests on the llama.rn #355 contract and is proven by an on-device verification step, not by unit tests.)

**Draft authoring is cross-repo (NOT mmproj's same-repo pairing).** A draft is usually a *different* HF repo, so it cannot ride `hfAsModel`'s same-repo sibling pairing (which `§Vision` requires `mmproj.hf_repo === hf_repo`). It is authored as an explicit `draft.{hf_repo, hf_filename, size_bytes}` block on a device-rules candidate, parsed by `parseDraft` (mirrors `parseMmproj` but **omits** the same-repo and projector-name checks), and synthesized into its own download stub (`modelType: DRAFT`) with the target's `defaultDraftModel`/`compatibleDraftModels` pointing at it. The **same** parse-time path guard as model/`mmproj` applies (`isSafePathSegment` / two-part repo / `.gguf`) because untrusted device-rules JSON drives the draft download URL too — a malformed draft degrades to no-draft (drop the draft, keep the target).

**State, single-writer, memory.**

- `activeDraftModelId` (runtime only, not persisted) is written **only** by `proceedWithInitialization` (set to the paired draft id) and cleared at **every** context-release reset point in `_releaseContextInternal`, alongside `activeProjectionModelId`. Stale draft state on model-switch is the projection-class bug this mirrors.
- `contextInitParams.speculativeEnabled` / `selectedDraftModelId` / `spec_draft_*` are written **only** by the matching `modelStore.set*` setters (`setSpeculativeEnabled`, `setSelectedDraftModel`, `setSpecDraft*`; mirror `setCacheTypeK`/`setNGPULayers`); persisted with `contextInitParams`. `CURRENT_CONTEXT_INIT_PARAMS_VERSION` is `2.3` — the `2.2 → 2.3` migration sets `speculativeEnabled` false and leaves `selectedDraftModelId`/`spec_draft_*` undefined, so upgraded records keep pre-feature behaviour. `selectedDraftModelId` is optional, so it needs no migration step or version bump.
- A paired draft is resident **alongside** any projection model at load, so the pre-load memory check **sums** target + projection + draft sizes (additive, not max): `getModelMemoryRequirement` and both `useMemoryCheck` chains gain an additive `draftModel?` slot; `checkMemoryAndConfirm` forwards the resolved draft.
- Auto-download mirrors projection: `_downloadDraftModelIfNeeded` is best-effort (swallow-and-continue — a draft download failure never fails the target download), gated on `speculativeEnabled`, and honours the **same per-target → global precedence** as `resolveDraftConfig` (a globally-picked draft auto-downloads on target download). It keeps the `modelType: DRAFT` self-recursion guard.
- A paired draft's pre-load memory estimate counts both its **weights and its own KV cache** (sized by the target `n_ctx` × the draft cache type, default `f16`), summed on top of target + projection.

**Settings.** The global speculative knobs live in the live `SettingsScreen.tsx` Advanced section: a master toggle, a **global draft-model picker** (downloaded non-projection models + a "None" entry, writing `selectedDraftModelId`), a **draft GPU-layers control** (writing `spec_draft_n_gpu_layers`), and draft cache-type menus. The draft cache-type label shows the **effective** resolved default (f16 paired / q8_0 embedded), and the menus are gated to match the runtime — `getEffectiveContextInitParams` forwards the draft cache type whenever speculative is on, independent of the target flash-attn, so the menus are enabled when a separate draft is paired and disabled (with an explanation) for embedded MTP. A **per-target** draft picker inside the Models screen, and draft-compatibility scoring, stay deferred. (`settings.md` notes this control group; no IA change.)

**Build note.** llama.rn is the **published `llama.rn@0.12.5`** registry release (the version that shipped the b9769 / PR #355 MTP + speculative draft-model support with prebuilt assets — iOS xcframework + Android jniLibs). It is consumed as a normal prebuilt dependency on the standard upgrade path from 0.12.4: no from-source build, no committed tarball, no `rnllamaBuildFromSource` flag, no Podfile header-path injection, and no `LlamaContextWrapper` `__has_include` header guard (the prebuilt xcframework resolves the `<rnllama/...>` headers directly). The earlier from-source approach (committed source tarball + `rnllamaBuildFromSource=true`) was superseded once 0.12.5 published; moving to the prebuilt release removed the x86_64-from-source CI risk and the committed-binary supply-chain concern.
