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
