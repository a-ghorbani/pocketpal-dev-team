# Implementation Plan: HF Hub `hub/run` deep-link + versioned HF User-Agent

Executable worklist for `what.md`. Section refs (`§N`, `In`, `Dn`, `9x`, `Scenario X`) point into `what.md`; do not re-derive design here.

---

## Metadata

- **Task ID**: TASK-20260603-2107
- **Worktree**: `./worktrees/TASK-20260603-2107`
- **Branch**: `feature/TASK-20260603-2107`
- **Native Changes**: YES (Android: `DownloadWorker.kt` OkHttp UA, `MainActivity.kt` `onNewIntent`, prod `AndroidManifest.xml` intent-filter)
- **Visual Confirmation**: YES
- **Intent Brief**: `./workflows/stories/TASK-20260603-2107/intent-brief.md`
- **WHAT**: `./workflows/stories/TASK-20260603-2107/what.md`
- **Architecture doc(s)**: `./context/architecture/deep-linking.md` (new — bootstrapped by this WHAT delta)
- **Status**: implemented (awaiting tester + native build verification)

---

## Progress

| Step | Status | Commit | Notes |
| --- | --- | --- | --- |
| Step 1 — shared UA builder | DONE | 6b40e95 | typecheck pass |
| Step 2 — UA on 4 hf.ts sites | DONE | 0ed9eb7 | 4 sites confirmed |
| Step 3 — UA on iOS RNFS download | DONE | 5238dd8 | typecheck pass |
| Step 4 — UA on Android OkHttp download | DONE | 95138a0 | native — needs Android build |
| Step 5 — `resolveHFModelForDownload` shared resolver | DONE | 44a93f3 | PalStore refactored; full suite green |
| Step 6 — `parseHubRunURL` shared parser | DONE | 43f29d9 | typecheck pass |
| Step 7 — `DeepLinkStore.pendingHubRun` | DONE | 348a415 | mock store updated |
| Step 8 — `HubRunDownloadSheet` landing sheet | DONE | 63c8c6d | l10n added; lint clean |
| Step 9 — `useDeepLinking` dispatch + sheet host | DONE | 51b8e06 | benchmark tests updated; full suite green |
| Step 10 — Android `onNewIntent` + prod intent-filter | DONE | 42c8a20 | native — needs Android build |
| Architecture doc created | DONE | (control plane) | bootstrapped context/architecture/deep-linking.md; zero (?) |

---

## Affected files

| Path | Change | Design ref |
| --- | --- | --- |
| `src/utils/hfUserAgent.ts` (new) | add shared UA builder | §1b, §5, D2, D3 |
| `src/api/hf.ts` | UA header at 4 sites (51, 104, 136, 177) | §5, I4, Scenario E |
| `src/services/downloads/DownloadManager.ts` | UA in RNFS headers (~283) | §5, I4, Scenario E |
| `android/app/src/main/java/com/pocketpalai/download/DownloadWorker.kt` | UA via OkHttp `addHeader` (~77–92) | §5, I4, Scenario E |
| `src/store/PalStore.ts` | call extracted resolver | §1 |
| `src/utils/hfResolve.ts` (new) | `resolveHFModelForDownload` | §1, I1, I2 |
| `src/store/DeepLinkStore.ts` | `pendingHubRun` field + setter/clear | §1, §5, I5 |
| `src/services/hubRunLink.ts` (new) | `parseHubRunURL` | §4a, I7, D11 |
| `src/components/HubRunDownloadSheet/` (new) | landing sheet | §3, §4c, D6 |
| `src/hooks/useDeepLinking.ts` | iOS+Android dispatch, drain pending | §4a.2–.4, D1, D7 |
| `App.tsx` | host the sheet inside BottomSheetModalProvider | §2, B drain |
| `android/app/src/main/java/com/pocketpalai/MainActivity.kt` | `onNewIntent` override | D9, 9e |
| `android/app/src/main/AndroidManifest.xml` | scoped VIEW intent-filter | I3, D4 |
| `context/architecture/deep-linking.md` (new) | bootstrap flow doc | whole WHAT |

---

## Steps

Each step is atomic — one logical change, one commit.

### Step 1: Shared HF User-Agent builder

**Implements**: §1b (outbound shape), §5 (single writer), D2, D3.

**Files**: `src/utils/hfUserAgent.ts` (new); re-export from `src/utils/index.ts`.

**Approach**: Export `hfUserAgent(): string` returning `` `PocketPal/${DeviceInfo.getVersion()} (ai.pocketpal)` `` (`react-native-device-info`, same import as `src/api/feedback.ts:102`). `(ai.pocketpal)` is a fixed literal (D2). One builder; no per-call interpolation elsewhere.

**Verification**: `yarn tsc --noEmit`; unit test asserts format with `getVersion` mocked `'1.0.0'` → `PocketPal/1.0.0 (ai.pocketpal)`.

---

### Step 2: Apply UA to all 4 `hf.ts` header sites

**Implements**: §5 (UA writer — HF API), I4, Scenario E.

**Files**: `src/api/hf.ts` — `fetchModels` (~51), `fetchModelFilesDetails` (~104), `fetchGGUFSpecs` (~136), `fetchModelInfo` (~177).

**Approach**: At each `headers` init add `'User-Agent': hfUserAgent()`. Keep existing `Authorization` behavior unchanged (I4). All four sites use the one builder — no inline strings.

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/api/hf.ts` (extend per Step-test below); grep confirms 4 call sites.

---

### Step 3: UA on iOS RNFS `/resolve/` download

**Implements**: §5 (UA writer — iOS /resolve/), I4, Scenario E.

**Files**: `src/services/downloads/DownloadManager.ts` (~283 `headers`).

**Approach**: Add `'User-Agent': hfUserAgent()` alongside the existing conditional `Authorization` in the RNFS `headers` object. Unconditional (HF is the only download source — I4).

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/services/downloads/DownloadManager.ts`.

---

### Step 4: UA on Android OkHttp `/resolve/` download (NATIVE)

**Implements**: §5 (UA writer — Android /resolve/), I4, Scenario E, D2/D3.

**Files**: `android/app/src/main/java/com/pocketpalai/download/DownloadWorker.kt` (~77–92 `Request.Builder`).

**Approach**: Add `.addHeader("User-Agent", "PocketPal/${BuildConfig.VERSION_NAME} (ai.pocketpal)")` to the builder (alongside Range/Authorization). `BuildConfig` is `com.pocketpal.BuildConfig` (namespace `com.pocketpal`, build.gradle:88); `VERSION_NAME` matches JS `DeviceInfo.getVersion()`. Literal `(ai.pocketpal)` (D2). Import BuildConfig if not present.

**Verification**: Android release build (native section below); grep confirms `addHeader("User-Agent"`.

---

### Step 5: Extract `resolveHFModelForDownload` shared resolver

**Implements**: §1 (canonical chain), I1, I2, D10, Scenario G/9i.

**Files**: `src/utils/hfResolve.ts` (new); refactor `src/store/PalStore.ts` `createLocalModelFromPHModel` (306–388).

**Approach**: New `resolveHFModelForDownload(repoId, filename, authToken?) → {hfModel: HuggingFaceModel; modelFile: ModelFile}` performing §1 steps 1–4 exactly: `Promise.all([fetchModelInfo, fetchModelFilesDetails])` → `createSiblingsFromFileDetails` → match sibling by `rfilename === filename` (no match → throw, 9i/G) → assemble full `HuggingFaceModel` with PalStore's field fallbacks (334–385). Refactor `createLocalModelFromPHModel` to call it then `hfAsModel(hfModel, modelFile)`, preserving its existing catch-fallback (389–393). Caller (sheet) supplies HF token.

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/store/PalStore.ts src/utils/hfResolve.ts`; new resolver unit test (Step-test below). Confirm returned `modelFile.url` non-empty (I1).

---

### Step 6: `parseHubRunURL` shared pure parser

**Implements**: §4a (single parse point), §1b (inbound shape), I6, I7, D5, D11, 9a/9b/9d.

**Files**: `src/services/hubRunLink.ts` (new); export `HubRunRequest` type (or in `src/utils/types.ts` per existing convention).

**Approach**: `parseHubRunURL(url: string): HubRunRequest | null`. `new URL(url)`; require `hostname === 'hub'` and normalized `pathname` (strip leading `/`) `=== 'run'`; trim+validate `repo_id` (one `/`, non-empty halves), `filename` (non-empty, `.gguf` case-insensitive); `source` passthrough/`undefined`. Any failure → `null` (no throw, no side effects). Do NOT extend `DeepLinkService.parseURL` (I7).

**Verification**: `yarn tsc --noEmit`; dedicated test covering valid, wrong host, wrong path, missing/malformed repo_id, non-`.gguf`, missing filename, source absent/arbitrary (9a/9b/9d, D5).

---

### Step 7: `DeepLinkStore.pendingHubRun`

**Implements**: §1 (data model), §5, §7, I5.

**Files**: `src/store/DeepLinkStore.ts`.

**Approach**: Add observable `pendingHubRun: HubRunRequest | null = null` with `setPendingHubRun` and `clearPendingHubRun` (mirror existing `pendingMessage` setters). Single writer: set by handler, cleared on drain (I5).

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/store/DeepLinkStore.ts`.

---

### Step 8: `HubRunDownloadSheet` landing sheet

**Implements**: §2, §3 (state machine), §4b (I1/I2), §4c, D6, Scenarios A/C/F/G.

**Files**: `src/components/HubRunDownloadSheet/{HubRunDownloadSheet.tsx,styles.ts,index.ts}` (new); export via `src/components/index.ts`.

**Approach**: Reuse VisionDownloadSheet structure (Sheet + Sheet.Actions + `isDownloading`) WITHOUT vision toggle / ProjectionModelSelector (§4c, D6). Props `{request: HubRunRequest | null; onClose}`. On request set → state `resolving`: call `resolveHFModelForDownload(repoId, filename, token)` (token from `HFStore` via existing pipeline; pass through). On success → `ready`: show model name/size/quant via `hfAsModel(hfModel, modelFile)`. Confirm → `downloadHFModel(hfModel, modelFile, {enableVision: false})` then dismiss (I1/I2/D10). Cancel → dismiss, no download (Scenario C). Resolve throw → `error` state + Retry/Cancel (Scenario F/G). No download path other than `downloadHFModel`.

**Verification**: `yarn tsc --noEmit`; component test (Step-test): renders name/size/quant after resolve; confirm calls `downloadHFModel` with `{enableVision:false}`; cancel does not; error state on reject.

---

### Step 9: `useDeepLinking` dispatch (iOS + Android prod) + sheet host

**Implements**: §2, §4a.2–.4, I5, I6, D1, D7, D8, 9e/9f, Scenarios A/B/D.

**Files**: `src/hooks/useDeepLinking.ts`; `App.tsx` (host sheet inside `BottomSheetModalProvider`).

**Approach**:
- iOS branch in `handleDeepLink`: sibling to `host === 'chat'`, `if (params.host === 'hub')` call `parseHubRunURL(params.url)`; `null` → `Alert` "invalid link" (D8); valid + host ready → open sheet, else `setPendingHubRun` (B).
- New ungated prod `Linking` effect (separate from the `__E2E__` benchmark effect, D7): cold `getInitialURL` + warm `'url'` listener → `parseHubRunURL` → same dispatch. Benchmark URLs resolve `null` here, so no overlap.
- Host: move `DeepLinkHandler`/sheet render inside `BottomSheetModalProvider` (App.tsx:89) so the sheet can present; on host mount drain `pendingHubRun` once then `clearPendingHubRun` (I5).
- Validation precedes all store writes/nav (I6).

**Verification**: `yarn tsc --noEmit`; `yarn test --findRelatedTests src/hooks/useDeepLinking.ts` — extend existing test for hub dispatch: valid→sheet/park, null→Alert+no write (Scenario D), pending consumed once (I5). Existing benchmark tests still pass (D7).

---

### Step 10: Android `onNewIntent` override + prod intent-filter (NATIVE)

**Implements**: I3, D4, D9, 9e.

**Files**: `android/app/src/main/java/com/pocketpalai/MainActivity.kt`; `android/app/src/main/AndroidManifest.xml`.

**Approach**:
- `MainActivity.onNewIntent(intent)`: call `super.onNewIntent(intent)` then `setIntent(intent)` so RN `Linking` fires the warm `'url'` event under `launchMode="singleTask"` (D9, 9e).
- Prod manifest: add a VIEW `<intent-filter>` to the existing `.MainActivity` block (35–46; existing intent-filter at 42–45) with `<category DEFAULT/>`, `<category BROWSABLE/>`, `<data android:scheme="pocketpal" android:host="hub"/>` (host-scoped, I3/D4). Mirror the e2e manifest's filter but scoped to `host=hub`; leave the e2e flavor manifest untouched.

**Verification**: Android release build (native section); inspect merged manifest / `adb shell am start -a android.intent.action.VIEW -d 'pocketpal://hub/run?repo_id=a/b&filename=x.gguf'`.

---

### Architecture doc: create `context/architecture/deep-linking.md`

**Implements**: whole WHAT (bootstrap promotion).

**Files**: `context/architecture/deep-linking.md` (new).

**Approach**: Promote `what.md` into the flow doc per `context/architecture/README.md` lifecycle: convert `(P)`→`(C)`, leave `(D)`, confirm zero `(?)`. Capture the as-built route, parser, resolver, UA writers, Android delivery. Same PR as code.

**Verification**: zero `(?)` markers; doc matches landed code paths.

---

## Testable-contract coverage

| Contract item (WHAT §6) | Verified by |
| --- | --- |
| A — valid link, app running | `HubRunDownloadSheet` test (resolve→name/size/quant→confirm→`downloadHFModel`); manual/visual |
| B — valid link, cold start | `useDeepLinking` test (park in `pendingHubRun`, drain once); manual cold-start |
| C — cancel | `HubRunDownloadSheet` test (cancel → no `downloadHFModel`, dismiss) |
| D — missing required param | `parseHubRunURL` + `useDeepLinking` test (`null`→Alert, no store write) |
| E — UA on HF requests | `hf.ts` test (4 sites), `DownloadManager` test, Android build + `adb` header check |
| F — metadata resolve fails | `HubRunDownloadSheet` test (reject → error state, no download) |
| G — filename not in repo | `resolveHFModelForDownload` test (no sibling → throw) + sheet error state |
| I1 no silent download | resolver returns non-empty `modelFile.url`; sheet confirm-only |
| I7 single parse point | grep: only `parseHubRunURL` parses `hub/run`; `DeepLinkService.parseURL` unextended |

---

## Native verification (NATIVE_CHANGES=YES)

```bash
cd "${WORKTREE_PATH}"
cd ios && pod install && cd ..
yarn ios --configuration Release
yarn android --variant=release
# Android deep-link smoke (app installed):
adb shell am start -a android.intent.action.VIEW \
  -d 'pocketpal://hub/run?repo_id=author/model&filename=model.Q4_K_M.gguf&source=hf'
```

Skipping native builds is a blocking review issue.

---

## Visual confirmation (Visual Confirmation=YES)

```json
[
  {"label": "valid hub/run sheet", "prompt": "pocketpal://hub/run?repo_id=author/model&filename=model.Q4_K_M.gguf&source=hf", "look_for": "landing sheet showing model name, size, quant (Q4_K_M), Download + Cancel"},
  {"label": "cancel no download", "prompt": "tap Cancel on the sheet", "look_for": "sheet dismisses, no download started"},
  {"label": "invalid link", "prompt": "pocketpal://hub/run?repo_id=author/model", "look_for": "invalid-link alert, no sheet"}
]
```

---

## Deferred items

- Universal/App Links (AASA + assetlinks.json) — research-only, deferred (WHAT scope note).
- `huggingface.js` Local-App registration PR — external, out of scope.
- Unify iOS native + Android `Linking` delivery into one service — WHAT §5 deferred cleanup.

---

## Review History

| Round | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| — | initial draft | — | — |
| 1 | BLOCKER — Android Kotlin source paths used `com/pocketpal/`; on-disk segment is legacy `com/pocketpalai/` (verified via `find`) | BLOCKER | FIXED — corrected `DownloadWorker.kt` and `MainActivity.kt` paths to `com/pocketpalai/` in Affected-files table and Steps 4 & 10. Kept `package`/`BuildConfig = com.pocketpal` reasoning (Step 4) unchanged — namespace is correct. |
| 1 | SUGGESTION — Step 10 cited prod `.MainActivity` block at lines 40–46 | SUGGESTION | FIXED — refreshed to "(35–46; existing intent-filter at 42–45)" matching current manifest (verified via `grep`). |
