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

---

## 1. Data model

No persisted model changes. One in-memory store field and one view-model type.

```
DeepLinkStore (MobX, src/store/DeepLinkStore.ts)
  pendingMessage: string | null         // (C) chat-link prefill, unchanged
  pendingHubRun: HubRunRequest | null   // (C) parked hub/run link, consumed once

HubRunRequest  (src/services/hubRunLink.ts)      // (C) parsed + validated payload
  repoId: string                         // required; "author/model"
  filename: string                       // required; "*.gguf"
  source: string | undefined             // optional attribution tag, e.g. "hf"
```

Persisted: none.

The sheet's name/size/quant and the download action share one **resolution chain** — the same proven chain `PalStore.createLocalModelFromPHModel` uses. It MUST go through `createSiblingsFromFileDetails` (`src/utils/hf.ts`), not a hand-built `ModelFile`, because that helper is what populates each sibling's `/resolve/` download `url` (via `normalizeModelSiblings` → `addModelFileDownloadUrls`). A hand-built `ModelFile` has no `url` → empty `downloadUrl` → `checkSpaceAndDownload` early-returns → confirm silently no-ops (C: defect path at `ModelStore.ts`).

Canonical resolver (`resolveHFModelForDownload(repoId, filename, authToken?, fallback?)`, `src/utils/hfResolve.ts`, C):
1. `Promise.all([fetchModelInfo({repoId, full, authToken}), fetchModelFilesDetails(repoId, authToken)])`.
2. `createSiblingsFromFileDetails(repoId, fileDetails)` → `ModelFile[]` with `/resolve/` `url` populated.
3. Find the sibling whose `rfilename === filename`. With no `fallback` (deep-link caller): no match → throw (Scenario G / 9i). With `fallback` (PalsHub caller): missing fields fall back to the supplied values.
4. Assemble the full `HuggingFaceModel` with `siblings` and HF_DOMAIN field fallbacks.
5. `hfAsModel(hfModel, modelFile)` → `Model` for display.
6. On confirm: `ModelStore.downloadHFModel(hfModel, modelFile, {enableVision: false})`. The sibling carries a real `url`, so the space-check passes and a real download starts.

`PalStore.createLocalModelFromPHModel` calls this resolver with a `fallback` derived from its `ModelReference` (preserving its prior tolerance to incomplete HF responses); the landing sheet calls it strict (no `fallback`).

**Glossary:**
- **hub/run route** — `pocketpal://hub/run?repo_id=…&filename=…&source=…`, the VIEW deep link.
- **landing sheet** — `HubRunDownloadSheet`; the only place a download can start from this route.
- **pending link** — a `HubRunRequest` parked in `DeepLinkStore` so it survives cold start until the sheet host mounts.
- **attribution UA** — the versioned `PocketPal/<version> (ai.pocketpal)` User-Agent.

### 1b. External shape

**Inbound deep link (wire → internal):**

| Wire param | Required | Maps to | Coercion at boundary |
| --- | --- | --- | --- |
| host `hub`, path `/run` | yes | route selector | `hostname === 'hub'`, normalized `pathname === 'run'`; else `null` (D5) |
| `repo_id` | yes | `HubRunRequest.repoId` | trim; must match `author/model` (one `/`, non-empty halves) |
| `filename` | yes | `HubRunRequest.filename` | trim; non-empty, ends `.gguf` (case-insensitive) |
| `source` | no | `HubRunRequest.source` | passthrough; not validated; default `undefined` |

**Outbound HF requests (internal → wire):** add header `User-Agent: PocketPal/<version> (ai.pocketpal)` where `<version>` = `DeviceInfo.getVersion()` (JS) / `BuildConfig.VERSION_NAME` (Android native). The `(ai.pocketpal)` token is a fixed literal on both platforms (D2). On Android the applicationId is `com.pocketpalai`, but the UA token stays `ai.pocketpal` — it is the HF attribution key, not the appId.

---

## 2. Event flow

```
VIEW intent / scheme open  (pocketpal://hub/run?…)
  raw url string reaches JS via:
    iOS   → DeepLinkService emitter → DeepLinkParams.url (host === 'hub' branch)
    Android prod → Linking getInitialURL / 'url' event (always-on effect)
  parseHubRunURL(url) → HubRunRequest | null              [single parse point]
    null → Alert "invalid link", no nav, no store write
    ok   → deepLinkStore.setPendingHubRun(request)
  HubRunSheetHost (inside BottomSheetModalProvider) observes pendingHubRun:
    non-null → opens HubRunDownloadSheet → resolution chain (§1) → name/size/quant
      confirm → downloadHFModel(hfModel, modelFile, {enableVision:false}) → dismiss
      cancel / dismiss → clearPendingHubRun()
```

The store-parked request works identically for warm launch (set then immediately observed) and cold start (set before the host mounts, drained on mount). The single writer to set is the `useDeepLinking` handler; the single writer to clear is the sheet host on dismiss.

---

## 3. State machine

`HubRunDownloadSheet` lifecycle (`request` prop = `deepLinkStore.pendingHubRun`):

```
hidden ─request set→ resolving ─chain ok→ ready ─confirm→ downloading ─started→ hidden
                      resolving ─chain err→ error ─retry→ resolving
                      ready/error ─cancel→ hidden
```

| State | User-visible feedback |
| --- | --- |
| `resolving` | spinner; repo_id header + filename (resolution chain running) |
| `ready` | filename, size, quant, Download + Cancel |
| `downloading` | Download button loading; buttons disabled |
| `error` | inline error + Retry/Cancel; no download started |
| `hidden` | sheet dismissed (`request === null`) |

---

## 4. Contract

### 4a. Route parsing & dispatch (C)

1. **Single parse point.** `parseHubRunURL(url): HubRunRequest | null` (`src/services/hubRunLink.ts`) does host/path gating + validation on a raw URL string. It is the only parse/validate site for this route and is called by BOTH delivery paths. `DeepLinkService.parseURL` (private, iOS-emitter-only) is not extended.
2. **iOS dispatch:** `useDeepLinking.handleDeepLink` has a `params.host === 'hub'` branch that calls the shared `handleHubRunLink(params.url)`, sibling to the `host === 'chat'` branch.
3. **Android prod dispatch:** an always-on `Linking` effect (cold `getInitialURL` + warm `'url'`) passes its raw url to the same `handleHubRunLink`. The `__E2E__` benchmark `Linking` effect stays separate.
4. Validation happens once, inside `parseHubRunURL`, before any sheet/store mutation. `null` → Alert, no navigation, no store write.

### 4b. Hard invariants (C)

- **No silent download.** This route never starts a download without an explicit confirm tap; on confirm a real download starts because the resolved `modelFile` carries a non-empty `/resolve/` `url`.
- **Single download entry point.** Confirm calls `ModelStore.downloadHFModel(hfModel, modelFile, {enableVision:false})` only. `checkSpaceAndDownload(id)` alone is insufficient (early-returns for models not in the store or with no `downloadUrl`).
- **Host scoping.** The Android prod intent-filter declares `scheme="pocketpal"` AND `host="hub"`; no bare-scheme prod handler.
- **UA on every model download.** The attribution UA is set on all HF API calls and on all model downloads on both platforms (HF is the only current download source). Authorization header behavior is unchanged.
- **Pending link consumed once.** `pendingHubRun` is cleared on sheet dismiss; the host does not re-open after clear.
- **Validation precedes side effects.** A malformed link produces zero store writes and zero navigation.
- **Single parse point.** Exactly one helper (`parseHubRunURL`) parses/validates a hub/run URL.

### 4c. Component renders

| Component | Renders | Does NOT render |
| --- | --- | --- |
| `HubRunDownloadSheet` | repo_id, filename, size, quant, Download/Cancel (Retry on error) | vision toggle, projection selector |
| `VisionDownloadSheet` | unchanged | — (pattern source only; not modified) |

---

## 5. Single-writer rule

| Field | Single writer |
| --- | --- |
| `DeepLinkStore.pendingHubRun` | `useDeepLinking` handler (set) + `HubRunSheetHost` on dismiss (clear) |
| download start | `ModelStore.downloadHFModel` |
| hub/run URL parse/validate | `parseHubRunURL` helper |
| HF→Model resolution | `resolveHFModelForDownload` (shared by sheet + PalStore) |
| attribution UA header (HF API) | `hfUserAgent()` consumed at all 4 `hf.ts` header sites (`fetchModels`, `fetchModelFilesDetails`, `fetchGGUFSpecs`, `fetchModelInfo`) |
| attribution UA header (iOS /resolve/) | `DownloadManager` RNFS `headers` (`hfUserAgent()`) |
| attribution UA header (Android /resolve/) | `DownloadWorker.kt` OkHttp `addHeader` (`BuildConfig.VERSION_NAME`) |

Cross-store reads: the sheet reads the HF token via `hfStore.shouldUseToken ? hfStore.hfToken : undefined` and `ModelStore` for the converted model. No new write coupling.

**Deferred cleanups:** (1) unify iOS native + Android `Linking` delivery into one service; (2) Universal/App Links.

---

## 6. Canonical scenarios

### A. Valid link, app already running
```
pocketpal://hub/run?repo_id=author/model&filename=model.Q4_K_M.gguf&source=hf
→ setPendingHubRun → sheet opens → resolution chain (matched sibling with /resolve/ url)
  → filename, size, quant Q4_K_M shown → confirm → downloadHFModel({enableVision:false})
  → real download starts → sheet dismisses → pendingHubRun cleared
```

### B. Valid link, cold start
```
app not running → same URL launches app → getInitialURL → setPendingHubRun
→ host mounts → observes pendingHubRun → sheet opens → (then as A)
```

### C. Cancel
```
valid URL → sheet ready → Cancel → dismiss; downloadHFModel NOT called; pendingHubRun cleared
```

### D. Missing required param
```
pocketpal://hub/run?repo_id=author/model  (no filename)
→ parseHubRunURL returns null → Alert "invalid link" → no sheet, no store write
```

### E. UA on HF requests
```
each of: /resolve/ download (iOS RNFS, Android OkHttp) + all 4 hf.ts header sites
→ request carries User-Agent: PocketPal/<version> (ai.pocketpal)
```

### F. Metadata resolve fails
```
valid URL → fetchModelInfo / fetchModelFilesDetails throws → sheet error state + Retry/Cancel; no download
```

### G. Filename not in repo
```
valid URL, .gguf-shaped filename, but no sibling matches rfilename
→ resolver (strict, no fallback) throws → sheet error state + Retry/Cancel; no download
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
| D6 | Dedicated `HubRunDownloadSheet`, not reuse of VisionDownloadSheet | Different fields (no vision toggle); pattern only |
| D7 | Keep `__E2E__` benchmark Linking effect separate; prod path is its own effect | Avoid regressing benchmark E2E routing |
| D8 | Required-param failure surfaces an Alert | Silent drop confuses the tapper |
| D9 | `MainActivity.onNewIntent` override (setIntent) | `ReactActivity` doesn't forward warm-launch intent under singleTask |
| D10 | Confirm calls `downloadHFModel`, not `checkSpaceAndDownload` | Deep-linked model isn't in the store; latter early-returns |
| D11 | One shared `parseHubRunURL` for both platforms | Avoids divergent validators |
| D12 | Park request in `DeepLinkStore`; observer host opens/clears | Survives cold start; single set/clear writers; sheet lives inside BottomSheetModalProvider |

---

## 9. Edge cases

| ID | Edge case | Behaviour |
| --- | --- | --- |
| 9a | Missing `repo_id` or `filename` | `null` → Alert; no side effects |
| 9b | Malformed `repo_id` (no `/`) or non-`.gguf` filename | `null` → Alert |
| 9c | Already-downloaded model | confirm → `downloadHFModel`→`addHFModel` returns existing model; inner `checkSpaceAndDownload` no-ops on downloaded/local |
| 9d | `source` absent or arbitrary | accepted; passthrough; no validation |
| 9e | Warm-launch on Android (singleTask) | `onNewIntent` forwards intent → `Linking` 'url' fires → sheet opens |
| 9f | Two rapid links | later `setPendingHubRun` overwrites the parked request |
| 9g | Private/gated repo metadata | uses HF token via the resolver `authToken`; failure → error state (F) |
| 9h | iOS scheme registration | `CFBundleURLTypes` already present; no iOS native change |
| 9i | Filename not present in repo tree | strict resolver throws → error state; no download (distinct from non-`.gguf` reject 9b) |
