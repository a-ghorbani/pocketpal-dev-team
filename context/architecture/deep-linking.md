# Deep Linking & HF Download Attribution

Cumulative architecture truth for the `pocketpal://` deep-link flow and the versioned Hugging Face (HF) User-Agent wire boundary.

Conventions: `(C)` current (verified from code), `(D)` decision (short rationale). Architecture docs are mostly `(C)`.

Out of scope (not implemented): the `huggingface.js` Local-App registration (external repo) and Universal/App Links (AASA + assetlinks.json).

---

## 0. Delivery reality (C)

- iOS deep-link delivery is via a native `DeepLinkModule` (`ios/PocketPal/DeepLinkModule.swift`) → `DeepLinkService` event emitter (`src/services/DeepLinkService.ts`). The handler receives `DeepLinkParams {url, scheme, host, queryParams}`.
- Android prod has **no native deep-link bridge**. Cross-platform prod delivery for the hub/run route uses RN `Linking` (cold `getInitialURL` + warm `'url'` event), an always-on effect in `useDeepLinking`.
- A separate `__E2E__`-gated `Linking` effect routes the benchmark deep link (`pocketpal://e2e/benchmark`). It is untouched by the hub/run flow; the two never overlap because `parseHubRunURL` returns `null` for benchmark URLs.
- `MainActivity` is `launchMode="singleTask"` and overrides `onNewIntent` to `setIntent(intent)` so RN's warm `'url'` event fires on warm launch (D9).
- **Navigator hosting the targets (C).** Deep-link handlers resolve targets via `navigation.navigate(ROUTES.*)` against flat route names. POC-30 replaced the top-level `@react-navigation/drawer` with a root Stack hosting a bottom-tab navigator (`context/architecture/app-shell.md`); `ROUTES.CHAT` and `ROUTES.BENCHMARK_RUNNER` are now flat sibling routes on that root Stack. The route-name strings and all handler logic are unchanged, so chat (`pocketpal://chat`), hub/run, and benchmark (`pocketpal://e2e/benchmark`) deep links resolve identically to the pre-migration drawer. `BENCHMARK_RUNNER` is registered on the root Stack only in `__E2E__` builds (injected by `App.tsx`).

---

## 1. Data model

No persisted model changes. One in-memory store field and one parsed type.

```
DeepLinkStore (MobX, src/store/DeepLinkStore.ts)
  pendingMessage: string | null         // (C) chat-link prefill, unchanged
  pendingHubRun: HubRunRequest | null   // (C) parked hub/run link, consumed once

HubRunRequest  (src/services/hubRunLink.ts)      // (C) parsed + validated payload
  repoId: string                         // required; "author/model"
  filename: string | undefined           // optional; kept for attribution, NOT load-bearing
  source: string | undefined             // optional attribution tag, e.g. "hf"
```

Persisted: none.

`repoId` is the ONLY param that drives behaviour. `filename` is kept in the parsed shape for future attribution use (D14) but the UI ignores it — no single-file selection, no highlight (D13).

**Repo resolution chain (C).** The host resolves the **full repo** into one `HuggingFaceModel` whose `siblings` each carry a `/resolve/` download `url`. This MUST go through `createSiblingsFromFileDetails` (`src/utils/hf.ts` → `normalizeModelSiblings` → `addModelFileDownloadUrls`), because that helper is what populates each sibling's download `url`. A hand-built sibling has no `url` → empty `downloadUrl` → `checkSpaceAndDownload` early-returns → download silently no-ops (C: defect path at `ModelStore.ts`). The no-silent-download guarantee (I1) applies to whatever file the user taps in `DetailsView`, via `ModelFileCard`'s existing `downloadHFModel` call.

**Repo-level resolver (C), `resolveHFRepo(repoId, authToken?): Promise<HuggingFaceModel>` in `src/utils/hfResolve.ts`:**
1. `Promise.all([fetchModelInfo({repoId, full, authToken}), fetchModelFilesDetails(repoId, authToken)])` — **strict**: a fetch failure throws (no per-call tolerance).
2. `createSiblingsFromFileDetails(repoId, fileDetails)` → `ModelFile[]` with `/resolve/` `url` populated.
3. Assemble the full `HuggingFaceModel` with `siblings` + HF_DOMAIN field fallbacks (via the shared `assembleHFModel` helper).

`resolveHFModelForDownload(repoId, filename, authToken?, fallback?)` (`src/utils/hfResolve.ts`, C) is the repo+single-filename resolver:
- **Strict path (no `fallback`)** delegates to `resolveHFRepo` (fetch failure throws), then finds the sibling whose `rfilename === filename`; no match → throws.
- **Tolerant path (`fallback` provided, the PalsHub caller)** keeps per-fetch independence: each of `fetchModelInfo` / `fetchModelFilesDetails` is caught individually, so a partial response (e.g. file details succeed, model info fails) still yields real sibling URLs; an unmatched filename or total failure falls back to the supplied `{author, size, downloadUrl}`.

`PalStore.createLocalModelFromPHModel` (`src/store/PalStore.ts`) calls `resolveHFModelForDownload` with a `fallback` derived from its `ModelReference` and catches to `createBasicModelFromReference` (D16). The hub/run host calls `resolveHFRepo` directly (no filename).

**Glossary:**
- **hub/run route** — `pocketpal://hub/run?repo_id=…&filename=…&source=…`, the VIEW deep link.
- **landing host** — `HubRunSheetHost` (`src/components/HubRunSheetHost`); the global host sheet that wraps `DetailsView`; the entry point a download can start from for this route.
- **DetailsView** — `src/screens/ModelsScreen/HFModelSearch/DetailsView/DetailsView.tsx` (C: takes only `hfModel`, no nav, no store read). Reused unchanged.
- **pending link** — a `HubRunRequest` parked in `DeepLinkStore` so it survives cold start until the host mounts.
- **attribution UA** — the versioned `PocketPal/<version> (ai.pocketpal)` User-Agent.

### 1b. External shape

**Inbound deep link (wire → internal):**

| Wire param | Required | Maps to | Coercion at boundary |
| --- | --- | --- | --- |
| host `hub`, path `/run` | yes | route selector | `hostname === 'hub'`, normalized `pathname === 'run'`; else `null` (D5) |
| `repo_id` | **yes** | `HubRunRequest.repoId` | trim; must match `author/model` (one `/`, non-empty halves) |
| `filename` | **no** | `HubRunRequest.filename` | trim; if present accepted as-is; **not** rejected when absent or non-`.gguf` (D13) |
| `source` | no | `HubRunRequest.source` | passthrough; not validated; default `undefined` |

**Outbound HF requests (internal → wire):** add header `User-Agent: PocketPal/<version> (ai.pocketpal)` where `<version>` = `DeviceInfo.getVersion()` (JS) / `BuildConfig.VERSION_NAME` (Android native). The `(ai.pocketpal)` token is a fixed literal on both platforms (D2). Android applicationId is `com.pocketpalai`, but the UA token stays `ai.pocketpal` — it is the HF attribution key, not the appId.

---

## 2. Event flow

```
VIEW intent / scheme open  (pocketpal://hub/run?…)
  raw url string reaches JS via:
    iOS   → DeepLinkService emitter → DeepLinkParams.url (host === 'hub' branch)
    Android prod → Linking getInitialURL / 'url' event (always-on effect)
  parseHubRunURL(url) → HubRunRequest | null              [single parse point, I7]
    null → Alert "invalid link", no nav, no store write
    ok   → deepLinkStore.setPendingHubRun(request)        (only repoId is load-bearing)
  HubRunSheetHost (inside BottomSheetModalProvider, App.tsx) observes pendingHubRun:
    non-null → opens host sheet → resolveHFRepo(repoId, authToken) → HuggingFaceModel
      ready  → <DetailsView hfModel={resolved} />  (full quant list)
                 user taps a file → ModelFileCard.downloadHFModel(hfModel, file, {enableVision:true})
      error  → inline error + Retry/Cancel; no list, no download
    dismiss  → clearPendingHubRun()
```

The store-parked request works identically for warm launch (set then observed) and cold start (set before host mounts, drained on mount). Single writer to set: the `useDeepLinking` handler; single writer to clear: the host on dismiss.

---

## 3. State machine

`HubRunSheetHost` lifecycle (`request` = `deepLinkStore.pendingHubRun`):

```
hidden ─request set→ resolving ─repo ok→ ready(list) ─tap file→ (download via ModelFileCard) ─→ stays open
                      resolving ─repo err→ error ─retry→ resolving
                      ready/error ─dismiss→ hidden
```

| State | User-visible feedback |
| --- | --- |
| `resolving` | spinner; sheet open with repo_id header |
| `ready` | `DetailsView` — author, title, stats, full quant list (each row a `ModelFileCard` with its own download/progress) |
| `error` | inline error + Retry/Cancel; no list, no download started |
| `hidden` | sheet dismissed (`request === null`) |

There is no `downloading` host state — per-file download/progress is owned by each `ModelFileCard` (C: `ModelFileCard.tsx`), unchanged. The host stays open after a tap so the user can pick more files.

---

## 4. Contract

### 4a. Route parsing & dispatch (C)

1. **Single parse point (I7).** `parseHubRunURL(url): HubRunRequest | null` (`src/services/hubRunLink.ts`) does host/path gating + validation on a raw URL string. Only parse/validate site for this route; called by BOTH delivery paths. `DeepLinkService.parseURL` (private, iOS-emitter-only) is not extended.
2. **Validation rule.** Require + validate `repo_id` shape (`author/model`). `filename`, if present, is trimmed and stored but never gates acceptance — a link with no `filename` (or a non-`.gguf` one) is a NORMAL success (D13). `source` passthrough.
3. **iOS dispatch.** `useDeepLinking.handleDeepLink` `params.host === 'hub'` branch calls the shared `handleHubRunLink(params.url)`, sibling to the `host === 'chat'` branch.
4. **Android prod dispatch.** An always-on `Linking` effect (cold `getInitialURL` + warm `'url'`) passes its raw url to the same `handleHubRunLink`. The `__E2E__` benchmark `Linking` effect stays separate.
5. Validation happens once, inside `parseHubRunURL`, before any store mutation. `null` → Alert, no navigation, no store write.

### 4b. Hard invariants (C)

- **I1 — No silent download.** This route never auto-downloads. A download starts only when the user taps a file in `DetailsView`, and it starts a real download because every sibling from `resolveHFRepo` carries a non-empty `/resolve/` `url` (via `createSiblingsFromFileDetails`).
- **I2 — Single download entry point.** Downloads go through `ModelStore.downloadHFModel(hfModel, modelFile, {enableVision:true})` — the existing `ModelFileCard.handleDownload`. No new download path; `DetailsView`/`ModelFileCard` are not modified.
- **I3 — Host scoping.** The Android prod intent-filter declares `scheme="pocketpal"` AND `host="hub"`; no bare-scheme prod handler.
- **I4 — UA on every model download.** The attribution UA is set on all HF API calls and on all model downloads on both platforms (HF is the only current download source). Authorization header behavior unchanged.
- **I5 — Pending link consumed once.** `pendingHubRun` is cleared on host dismiss; the host does not re-open after clear.
- **I6 — Validation precedes side effects.** A link whose `repo_id` is missing/malformed produces zero store writes and zero navigation. (`filename` absence is NOT a failure — D13.)
- **I7 — Single parse point.** Exactly one helper (`parseHubRunURL`) parses/validates a hub/run URL; both iOS and Android prod delivery call it.
- **I8 — Reuse, don't fork.** The host presents the existing `DetailsView` (and its `ModelFileCard` rows) with no edits; no bespoke per-file download UI for this route.

### 4c. Component renders

| Component | Renders | Does NOT render |
| --- | --- | --- |
| `HubRunSheetHost` (host) | spinner (resolving) → `<DetailsView hfModel={resolved}/>` (ready) → inline error + Retry/Cancel (error) | per-file rows itself (DetailsView owns those); filename highlight; single-file confirm |
| `DetailsView` (reused, unchanged) | author, title, stats, full quant list via `ModelFileCard` | filename highlight, single-file confirm |
| `ModelFileCard` (reused, unchanged) | per-file size/quant + download/progress/cancel | — |

---

## 5. Single-writer rule

| Field | Single writer |
| --- | --- |
| `DeepLinkStore.pendingHubRun` | `useDeepLinking` handler (set) + `HubRunSheetHost` on dismiss (clear) |
| download start | `ModelStore.downloadHFModel` (via `ModelFileCard`) |
| hub/run URL parse/validate | `parseHubRunURL` helper (I7) |
| HF repo → HuggingFaceModel resolution | `resolveHFRepo` (shared strict core; `resolveHFModelForDownload` builds on it then file-matches) |
| attribution UA header (HF API) | `hfUserAgent()` at all 4 `hf.ts` header sites (`fetchModels`, `fetchModelFilesDetails`, `fetchGGUFSpecs`, `fetchModelInfo`) |
| attribution UA header (iOS /resolve/) | `DownloadManager` RNFS `headers` |
| attribution UA header (Android /resolve/) | `DownloadWorker.kt` OkHttp `addHeader` (`BuildConfig.VERSION_NAME`) |

Cross-store reads: the host reads the HF token via `hfStore.shouldUseToken ? hfStore.hfToken : undefined` for `resolveHFRepo`, and `ModelStore` for converted models (inside `downloadHFModel`). No new write coupling.

**Deferred cleanups:** (1) unify iOS native + Android `Linking` delivery into one service; (2) Universal/App Links.

---

## 6. Canonical scenarios

### A. Valid link, app already running
```
pocketpal://hub/run?repo_id=author/model&source=hf
→ setPendingHubRun → host sheet opens → resolveHFRepo → DetailsView shows full quant list
  → user taps a file → ModelFileCard.downloadHFModel({enableVision:true}) → real download starts
```

### B. Valid link, no filename (happy path)
```
pocketpal://hub/run?repo_id=author/model          (no filename param)
→ parseHubRunURL returns a valid request (filename undefined) → host opens → full quant list (then as A)
```

### C. Cold start
```
app not running → URL launches app → getInitialURL → setPendingHubRun
→ host mounts → observes pendingHubRun → sheet opens → (then as A)
```

### D. Dismiss without downloading
```
valid URL → list shown → user dismisses sheet
→ no downloadHFModel call → pendingHubRun cleared
```

### E. Missing / malformed repo_id
```
pocketpal://hub/run?filename=x.gguf      OR      ?repo_id=notavalidid
→ parseHubRunURL returns null → Alert "invalid link" → no sheet, no store write
```

### F. UA on HF requests
```
each of: /resolve/ download (iOS RNFS, Android OkHttp) + all 4 hf.ts header sites
→ request carries User-Agent: PocketPal/<version> (ai.pocketpal)
```

### G. Repo resolve fails
```
valid URL → fetchModelInfo / fetchModelFilesDetails throws (network/404/private)
→ host shows error state + Retry/Cancel; no list, no download
```

---

## 7. State signals

| Signal | Set by | Read by | True when |
| --- | --- | --- | --- |
| `pendingHubRun` | `useDeepLinking` handler | `HubRunSheetHost` | a valid link is awaiting / showing the sheet |

---

## 8. Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D1 | Always-on prod `Linking` cold+warm path for hub/run (covers Android) | Android prod has no native deep-link bridge |
| D2 | UA token literal is `ai.pocketpal` on both platforms | HF attribution key, not Android appId |
| D3 | Version from `DeviceInfo.getVersion()` (JS) / `BuildConfig.VERSION_NAME` (Android) | Already available; match each other |
| D4 | Route path = `hub/run` (host `hub`, path `run`) | Host-scoped for security |
| D5 | Unknown host/path silently ignored (no error) | Avoid noisy errors on future scheme routes |
| D7 | Keep `__E2E__` benchmark Linking effect separate; prod path is its own effect | Avoid regressing benchmark E2E routing |
| D9 | `MainActivity.onNewIntent` override (setIntent) | `ReactActivity` doesn't forward warm-launch intent under singleTask |
| D11 | One shared `parseHubRunURL` for both platforms | Avoids divergent validators; honours I7 |
| D12 | Park request in `DeepLinkStore`; observer host opens/clears | Survives cold start; host lives inside BottomSheetModalProvider |
| D13 | Land on full `DetailsView` list; `filename` not required, not highlighted | HF deeplink has no quant; product chose list, not single file |
| D14 | Keep `filename` optional in `HubRunRequest`, unused by UI | Preserve for future attribution without re-parsing |
| D15 | Reuse `DetailsView`/`ModelFileCard` unchanged for the list | Existing card already does vision/progress/download correctly |
| D16 | Split `resolveHFRepo` strict core; keep `resolveHFModelForDownload` for PalStore | PalStore needs file-match + per-fetch tolerance + fallback; don't regress it |

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | Missing/malformed `repo_id` | `null` → Alert; no side effects (I6, E) |
| 9b | `filename` absent | NORMAL success; list shown (D13, Scenario B) |
| 9c | `filename` present but non-`.gguf` or not in repo | accepted by parser, ignored by UI; user picks from list (D13) |
| 9d | Already-downloaded file tapped | `ModelFileCard` shows "already downloaded" alert (C) — unchanged |
| 9e | `source` absent or arbitrary | accepted; passthrough; no validation |
| 9f | Warm-launch on Android (singleTask) | `onNewIntent` forwards intent → `Linking` 'url' fires → host opens (D9) |
| 9g | Two rapid links | later `setPendingHubRun` overwrites the parked request (I5) |
| 9h | Private/gated repo metadata | `resolveHFRepo` uses HF token; failure → error state (G) |
| 9i | iOS scheme registration | `CFBundleURLTypes` already present; no iOS native change |
| 9j | Vision repo | `DetailsView` already renders the vision tag + LLM-file filtering (C) — unchanged |
