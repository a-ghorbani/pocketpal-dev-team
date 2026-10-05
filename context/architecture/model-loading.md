# Model Loading

## Purpose

This doc covers how the preset model list comes from device rules, how capabilities (vision, MTP) are read, how a local model is loaded natively (the error lifecycle, Android Hexagon device resolution, speculative decoding), and how a release waits for the running generation. Remote-server capability discovery is in `remote-servers.md`. llama.rn build modes and the shipped native payload are in `release.md`. The benchmark's own native loading is in `benchmark-matrix.md`.

## Code map

| Path | Role |
| --- | --- |
| `src/services/deviceRules/` | `parse.ts` (untrusted-JSON guard), `classify.ts` (device to tier), `signals.ts` (`readDeviceSignals`), `rules.ts` (`fetchRules`), `rulesUrls.ts` (jsDelivr `rules.<platform>.v2.json`), `appVersion.ts` (`toCoreVersion`, `passesMinAppVersion`) |
| `src/store/bundledDeviceRules/rules.{android,ios}.json` | committed offline floor: a copy of the published `rules.<platform>.v2.json`, gates and informational fields included (the parser keeps `min_ram_gb` as `minRamGb`, unconsumed) |
| `src/store/ModelStore.ts` | `initializeStore`, `resolvePresetModels` / `candidateToPair` / `draftToStub`, `reconcilePresets`, `initContext`, `proceedWithInitialization`, `getEffectiveContextInitParams`, `resolveDraftConfig`, `enter/exitBenchmarkMode` |
| `src/store/draftResolution.ts` | pure draft-mode resolution: `resolveDraftCandidate`, `effectiveDraftModeOf`, `draftCacheDefaults` |
| `src/utils/mtp.ts` | `isMTPCapable`, `nEmbdOut`, `isDraftOnlyModel`, `probeRemoteMTPCapability` |
| `src/utils/ggufHeader.ts` | in-repo range-fetching GGUF header reader for the pre-download MTP probe |
| `src/utils/modelCaps.ts` | `resolveModelCaps`, the single capability read-point |
| `src/store/generationLease.ts` | `GenerationSlot` (FIFO lease slot) and the `GenerationLease` type; `ModelStore` composes it (`acquireGeneration`, `tryAcquireGeneration`, `abortActiveGeneration`, `isGenerationBusy`) |
| `patches/llama.rn+0.13.0-rc.5.patch` | native context ownership and the llama abort callback; build and payload contract in `release.md` |
| `src/utils/deviceSelection.ts` | `resolveDeviceSelection`, `getDeviceOptions`, the canonical Hexagon pick |
| `src/utils/index.ts` | `hfAsModel` (HF file to `Model`) |
| `src/utils/contextInitParamsVersions.ts` | persisted `contextInitParams` migrations |
| `src/components/ErrorSnackbar/`, `src/components/ModelErrorReportSheet/` | load-failure surface and **Report** |
| `android/app/src/main/java/com/pocketpalai/MainApplication.kt` | process env for ggml (`GGML_OPENCL_ADRENO_USE_LARGE_BUFFER`), set before `SoLoader.init` |

## How it works

`ModelStore.initializeStore` first applies the bundled rules: `resolvePresets` reads signals, classifies, and runs `resolvePresetModels`. It then either migrates (`mergeModelLists`, when stored `version < MODEL_LIST_VERSION`) or runs `reconcilePresets`. Last, it fires `upgradeToFetchedRules` without awaiting it. The fetched set is reconciled over the floor when it parses, matches the platform, and has at least one model.

`resolvePresetModels` turns each rule candidate into the minimal `(HuggingFaceModel, ModelFile)` pair and calls the existing `hfAsModel` unchanged. The result is an `origin: HF` model identical to an HF-browser add. Multimodal candidates also push their projector stub. Draft candidates push a `modelType: DRAFT` stub and set `defaultDraftModel`.

Load path:
- `selectModel` sends a local model to `initContext`.
- Phase 1 runs outside the mutex: `resolveMultimodalConfig`, `resolveDraftConfig`, and the `checkMemoryAndConfirm` alert, then a last-one-wins `pendingModelId` check.
- Phase 2 runs inside the mutex in `proceedWithInitialization`: release the old context, `getEffectiveContextInitParams(filePath, draftConfig)`, a single `initLlama`, and a verify-and-write of `isMultimodalActive`.

Generation lease: a chat run holds one for its whole `runAgent` run; a VideoPal frame and a Pal-sheet prompt generation each take one with `tryAcquireGeneration` (busy, never waits); the generation ends when its sheet closes. `acquireGeneration` waits for earlier leases, then the context-op mutex tail, then grants on the current engine (null if none or releasing). Every release (`_releaseContextInternal`) aborts the lease and awaits `end()` before `releaseMultimodal` and `context.release()`. Native release flags the context, unregisters it, and destroys it once sole owner.

## Contracts and invariants

- **The floor is applied before any network.** A hanging or failed fetch never empties a fresh install. `fetchRules` returns `null` (keep the floor) on network error, non-2xx, parse throw (including schema major ≠ 2), platform mismatch, or zero models across tiers (including every candidate gated out).
- **Parse is the security boundary, not the host check.** Untrusted CDN JSON drives download paths and, through the URL, the HF token. `parse.ts` requires `hf_repo` to be exactly two non-empty parts, `isSafePathSegment` on author, repo and filename, and `.gguf`. Only then does it derive the URL from a hard-coded `huggingface.co` template, so `isHuggingFaceUrl` on it is tautological. `DownloadManager` separately sends the Bearer token only to `huggingface.co`.
- **A bad `mmproj` drops the whole candidate; a bad `draft` drops only the draft.** The `mmproj.hf_repo` must equal `hf_repo` and the filename must match `MMProjRegex`, because `hfAsModel` pairs projectors as same-repo siblings. Drafts are usually cross-repo, so `parseDraft` skips those two checks but keeps the path guard.
- **Only schema major 2 parses.** `parseDeviceRules` throws unless `schema_version` is `x.y.z` (optional `-`/`+` suffix) with major 2, so an off-major doc ends at the floor. The app fetches only `rules.<platform>.v2.json`, never the v1 file, which stays frozen for pre-v2 clients whose parser ignores unknown fields.
- **`min_app_version` gates fail closed, with the mmproj/draft asymmetry.** The field is optional on a candidate, its `mmproj` and its `draft`, and must be strict `x.y.z`. Absent passes; unmet or malformed (including `null`) drops the candidate for a candidate or `mmproj` gate, and only the draft for a `draft` gate. An `mmproj` gate counts only when `multimodal: true`.
- **The app version is injected, and only the parser gates.** `parseDeviceRules(raw, appVersion)` and `fetchRules(appVersion, platform)` require it; `resolvePresets` and `upgradeToFetchedRules` pass `DeviceInfo.getVersion()`. The suffix after `-` or `+` is stripped; an unparseable version fails every present gate. Consumers downstream of parse never see the field.
- **Every bundled gate is met by the shipped version** (`package.json` `version`, which fastlane propagates to both native versions), so the floor parses to its full list on every real build. An unparseable app version drops only the candidate-gated entries, every tier keeps an ungated candidate, and the floor has no `mmproj`/`draft` gate (`bundledRules.test.ts`, plus the store-level unknown-version test in `ModelStore.test.ts`).
- **Model id is `author/repo/filename`.** Rule `model` is a label. Dedupe and reconcile key on the full id, which spans origins: a downloaded legacy `origin: PRESET` suppresses the matching `origin: HF` stub, so there is no double card and no re-download. Keying on `{repo, filename}` would merge different authors' files.
- **The purchase model step** (`PalModelStep/modelOffer.ts`) picks by `hasEnoughMemory`, loads only through `selectModel`, and never rewrites the Pal's `defaultModel`.
- **`reconcilePresets` prunes only non-downloaded `isRulePreset` stubs** absent from the fresh set. It never prunes downloaded, user-added HF, or LOCAL models. The `MODEL_LIST_VERSION` bump is skipped when presets resolve empty, so a transient signal failure retries next launch.
- **Rule JSON is thin.** `oid`, `lfs` and template tokens are not stored. The URL is deterministic, so downloads never early-return. `checkModelFileIntegrity` sees the missing `lfs` on an `origin: HF` model and calls `fetchAndUpdateModelFileDetails`. Templates come from the GGUF or defaults.
- **`resolveModelCaps` is the only place a capability question branches on `model.origin`.** Remote models use probe-then-list data (`remote-servers.md`). Local models use `isMultimodalActive`. `visionActive` and `effectiveContextLength` come only from probed state and only for the active model. A card never borrows another model's load state, and derived or list data can never enable attach, the image gate, the camera, or a context banner.
- **`isMultimodalActive` is a maintained observable.** It is written by `proceedWithInitialization` (after `ctx.isMultimodalEnabled()`) and cleared on release. No reader re-verifies natively or repairs it.
- **One load entry, one writer.** `initContext` is the sole local load entry. `proceedWithInitialization` is the sole writer of `context` / `engine` / active model / `modelLoadError`. `initContext` rejects while `benchmarkActive`.
- **Crash-loop guard.** A failed load sets `modelLoadError` once and rethrows. There is no auto-retry and no snackbar Retry; retry is user-initiated only, through `selectModel`. Pre-load warnings (storage, memory, multimodal, integrity) are inline advisories and never a snackbar. Hard failures surface on `ErrorSnackbar` with **Report**, which opens `ModelErrorReportSheet`.
- **Hexagon resolution (Android).** When the effective `devices` contain any `HTP*` entry, `resolveDeviceSelection` replaces them with the first discovered nonempty, wildcard-free `HTP` runtime name, in native enumeration order. This covers legacy `['HTP*']`, stale names, multi-session and mixed lists. Settings (`getDeviceOptions`) and the benchmark use the same `selectHexagonDevice`. No discovered device resolves to explicit `devices: ['CPU']`, `n_gpu_layers: 0`; leaving them undefined would permit auto-offload. The device list is copied before discovery. Nothing is persisted, so HTP intent survives a CPU fallback.
- **Speculative mode is derived, never persisted.** `resolveDraftCandidate` decides it:
  - **off** when `speculativeEnabled` is false;
  - **paired** when the resolved draft is downloaded, MTP-capable, and `nEmbdOut(draft) === target n_embd`. The draft is the per-target `defaultDraftModel` first, then the global `selectedDraftModelId`, never the target itself;
  - otherwise **embedded** when the target is MTP-capable, else **off**.
  `spec_type='draft-mtp'` is emitted only for paired or embedded.
- **Mode defaults never override the user.** `getEffectiveContextInitParams` applies them as `??` fallbacks: paired uses `flash_attn_type 'off'` and draft GPU layers 99; embedded uses `'auto'`. It also coerces `spec_draft_n_max` to at least 1, because llama.rn throws on ≤0.
- **Draft cache type defaults to f16**, except q8_0 when the mode is embedded and `flash_attn_type` is explicitly `'on'` (`draftCacheDefaults`). A quantized draft V is clamped to f16 whenever flash attention is `'off'`.
- **Single writers for draft state.** `speculativeEnabled`, `selectedDraftModelId` and `spec_draft_*` are written only by the `modelStore.set*` setters. The `2.2 → 2.3` params migration sets `speculativeEnabled: false`.
- **Every ggml env var the app sets is one the vendored ggml `getenv`s.** A name nothing reads is a silent no-op that no test catches; the upgrade re-check is in `release.md`, Verification.
- **llama.rn is the app's only ggml-bearing native dependency.** Its ggml is unprefixed, so a second ggml copy would collide at link or bind time. On iOS, `rnllama.framework` hides `ggml_*` / `gguf_*`, so `ios/PocketPal/AppIntents/LlamaContextWrapper.mm` may reference only exported symbols (`common_*`, `llama_*`, `rnllama::`), header inlines included.
- **One lease per `ModelStore`; no chat or VideoPal completion outside a held, unaborted lease; no `context.release()` while one is held.** A stale `end()` cannot clear a newer lease.
- **A lease holder never awaits `contextOperationMutex`:** release holds it while awaiting the drain. Acquirers may.
- **An aborted decode is a stop on every context the completion owns, and no exception leaves a completion begun.** An MTP draft `process` that fails while the abort is requested takes the target's interruption path at the pre-batch `n_past`; any exception out of the JSI token loop calls `endCompletion()` before rethrowing, so "Context is busy" only means a completion is running. The vendored `SPC_ERR … rc=2` lines on an aborted draft are expected.
- **On recurrent or hybrid memory an aborted decode loses live state** (a partial graph leaves layers, and MTP rollback rows, mixed), so `stopAfterAbortedDecode` never trims in place: it restores the longest checkpoint ≤ `n_past` of a placeholder-free prefix, else clears memory and checkpoints. A prefix with media always clears: after a Stop in an image chat the next turn re-encodes and re-prefills, where it used to resume past the image. Accepted, because M-RoPE positions are not token counts and an ingest-time abort clears the media hashes.
- **Natively, a registered context is reachable only through `shared_ptr`**, taken at task start and held until the task returns; slot-manager callbacks hold a `weak_ptr` (the context owns them).
- **A paired draft is resident alongside the target and projector.** The memory check sums all three, with the draft's weights plus its KV cache. `_downloadDraftModelIfNeeded` is best-effort and uses the same draft-selection order.

## Traps and decisions

- **A width mismatch is an uncatchable SIGABRT.** `GGML_ASSERT` fires in `init_mtp`. The JS width check is the only guard, so an unknown width means not paired. Sending `spec_type` to a non-MTP target is a native error, not a no-op, which is why the app resolves to off before emitting.
- **MTP capability reads cached `ggufMetadata.nextn_predict_layers`,** and width reads cached `n_embd` / `embedding_length_out`. A model whose metadata is missing resolves as not capable or not paired. For example, e2e pre-seeded files skip metadata fetch, so pairing silently degrades there. A converter that omits the KV false-negatives safely to off.
- **`auto` flash attention resolves per backend after init params are committed.** On Android CPU it resolves off, and llama.cpp refuses a quantized V cache without flash attention, so q8_0-with-`auto` (llama.rn's example) is Apple-safe only.
- **No timeout on the drain or native release:** llama.rn's 5 s wait-then-delete was the crash. A wedged backend (Hexagon Q2_K) hangs release and the next send's "Stopping…"; no watchdog exists.
- **No JS timer on the drain path.** Timers do not fire while the app is backgrounded, where auto-release waits for the drain. Every wait between abort and `lease.end()` resolves on a native event or on the abort itself, and a single `stopCompletion` must land on its own (`agent-runner.md`). Raw `LlamaContext.stopCompletion` returns `undefined` and can throw synchronously. A timer-gated yield there held a background release until the app was reopened.
- **Only CPU honours the abort callback per node** (Android drains in about 1 s). OpenCL, Hexagon and prebuilt iOS stop between decode batches, so stop and release wait one batch. mtmd/clip image encoding has no abort hook, so stop and release during an image or VideoPal frame wait for the whole encode.
- **Acquire chains on the mutex after the drain**, so a send queued during a switch reaches the new model.
- **Test Completion (`__DEV__` only) takes no lease;** native ownership alone keeps release safe for it. Every production completion leases: a second `llamaCompletion` while a chat task is queued re-runs `rewind()` and the param parse on the shared context, clearing that run's stop, grammar and stop words, and remote completions share one `abortController`. App Intents' context is outside the registry.
- **The pre-download probe is tri-state (`capable | not-capable | unknown`) and uses an in-repo reader.** `@huggingface/gguf` needed `TextDecoder`, which Hermes lacks: it threw on device while jest stayed green, and a `catch → false` hid that. `ggufHeader.ts` seeks past values, hand-decodes short keys, and throws to `unknown` on any anomaly. The HF API's `expand[]=gguf` omits the arch-namespaced KVs and tensor names this probe needs.
- **Draft-only artifacts** (arch suffix `assistant` / `mtp`, or the filename convention pre-download) are not chat models. `hfAsModel` does not treat them as vision LLMs even beside an mmproj, and `healDraftVisionClassification` cleans legacy records.
- **Projector quant is an authoring responsibility.** The rule's `mmproj` is used as named, not through `getRecommendedProjectionModel`.
- **With no local target loaded, Settings shows the global pick's mode.** Downloaded and MTP-capable means paired (`effectiveDraftModeOf`). The load path still width-checks.
- **The classifier is pure and total.** Any unclassifiable device gets `low`.
- **Remote-attached images are inlined as `data:` URIs** in `openai.ts`, because a server cannot read device paths.
- **Single-session Hexagon is deliberate.** Requesting several `HTP` sessions engages the multi-session pipeline, whose compute buffers amplify memory. Registry discovery does not prove which sessions execute; the native init arguments and model/compute allocation logs do. CPU, OpenCL and every iOS selection skip the discovery call.
- **llama.rn is the published npm pin in `package.json`, not a git ref.** Speculative needs ≥ 0.12.5 (MTP) and ≥ 0.12.7 (speculative-correct native timings); ≥ 0.13.0-rc.5 is unprefixed ggml. iOS vendors the prebuilt `rnllama.xcframework`; Android compiles from source, which is what silently dropped the Hexagon backend once. The build contract lives in `release.md`.

## Verification

- Unit: `src/services/deviceRules/__tests__/`, `src/store/__tests__/ModelStore.test.ts` (failure sets error once, `initLlama` once), `src/utils/__tests__/{deviceSelection,ggufHeader,mtp,modelCaps}.test.ts`, `src/store/__tests__/{generationLease,ModelStore.generationLease}.test.ts`.
- Release safety is proven only on a device: Home and unload mid-prefill, 1 and 4 threads, ~1,800-token prompt; no crash, about 1 s on Android CPU.
- Stop safety is also device-only: Stop, send, then a greedy cold replay of the same chat. MTP (Qwen3.5-0.8B): repeat until a run logs an aborted draft (`rc=2`); never "Context is busy". Hybrid (LFM2.5-350M): `Decoding interrupted, restored state checkpoint`, less than the full prompt re-processed, warm == cold. Vision-hybrid (Qwen3.5-2B + `mmproj-F32`; a POCO F8 Ultra if the OnePlus 6 runs out of RAM): `… no usable state checkpoint (media)`, warm == cold. Match the full `Decoding interrupted, ` line: `loadPrompt` logs the bare suffixes too. A stop during prompt formatting (Android and iOS): a local-only log in the applied re-apply branch must fire and that run end `interrupted`; a forced stop right after `getFormattedChat` stops with the re-apply and runs on without it. VideoPal: Stop during the encode and during generation, and leaving mid-frame, end the frame after the encode at most. Pal-sheet Generate during a chat reply shows the busy line and leaves the reply running (`pals-and-talents.md`).
- e2e: `e2e/specs/features/speculative.spec.ts`, `speculative-paired.spec.ts`, `speculative-visual.spec.ts`, `download-cancel.spec.ts`.
- **Speculative engagement is provable only by `draft_tokens > 0`.** `AssistantTurnFooter` then renders `message-draft-tokens`. A no-error run proves nothing, because an inert load also succeeds. For the off case, check that the element is absent. For a width-mismatched paired draft, the check is that the process survives and the target loads. Load with an adequate `n_ctx` first, or the increase-context sheet starves generation.
- **The displayed tokens/sec is llama.rn's native timing,** which is speculative-correct in current llama.rn. It shows the rate is reported, not that speculative decoding is faster. That needs one model measured both ways on a physical device.
- **Once the floor equals the published file, a successful fetch and a failed one look the same on device;** prove fetching with a build whose floor predates the published file.
- By hand on Android with Hexagon: select Hexagon and load. The native init log should name a single `HTPn`.
