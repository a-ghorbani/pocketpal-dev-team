# Deep Linking & HF Download Attribution

## Purpose

This doc covers two things: inbound `pocketpal://` links, and the outbound Hugging Face (HF) User-Agent attribution wire. The links are the `hub/run` "Use this model" route, the iOS Shortcuts `chat` route, and the E2E-only routes. The flat routes it navigates to belong to `app-shell.md`. Universal Links, App Links, and the HF Local-App registration (which lives in an external repo) are not implemented.

**Not on `main` yet:** open PR #897 adds the `llama://` pairing route (and `llama` in the iOS scheme allow-list). The previous version of this doc described it (`git show 1ad6ce1:context/architecture/deep-linking.md`); distill it back in when it lands.

## Code map

| Path | Role |
| --- | --- |
| `ios/PocketPal/Info.plist` | `CFBundleURLTypes`: the `com.pocketpalai.deeplink` dict registers `pocketpal`. A separate dict registers the Google Sign-In reversed-client-id scheme. |
| `ios/PocketPal/AppDelegate.swift` | `application(_:open:options:)`: posts `RCTOpenURLNotification` only when `url.scheme == "pocketpal"`, and returns `false` for every other scheme |
| `ios/PocketPal/DeepLinkModule.swift` | native `onDeepLink` emitter; buffers `pendingURL` until JS listens; `getInitialURL` |
| `src/services/DeepLinkService.ts` | iOS-only JS side of that emitter (`DeepLinkParams`) |
| `android/app/src/main/AndroidManifest.xml` | `singleTask` activity; host-scoped VIEW filter `pocketpal`/`hub` |
| `android/app/src/main/java/com/pocketpalai/MainActivity.kt` | `onNewIntent`: `setIntent(intent)` |
| `src/hooks/useDeepLinking.ts` | `handleDeepLink` for the emitter path (E2E automation, `chat`, `hub`); an always-on `Linking` effect for `hub/run`; an `__E2E__` benchmark `Linking` effect; `useHubRunSheet` |
| `src/services/hubRunLink.ts` | `isHubLink`, `parseHubRunURL`, `HubRunRequest` |
| `src/store/DeepLinkStore.ts` | `pendingMessage` (the chat prefill), `pendingHubRun` |
| `src/components/HubRunSheetHost/` | global sheet host, mounted in `App.tsx` inside `BottomSheetModalProvider` |
| `src/utils/hfResolve.ts` | `resolveHFRepo` (strict) and `resolveHFModelForDownload` (tolerant, with a fallback, used by `PalStore`) |
| `src/utils/hf.ts` | `createSiblingsFromFileDetails` → `normalizeModelSiblings` → `addModelFileDownloadUrls` |
| `src/screens/ModelsScreen/HFModelSearch/DetailsView/` | `DetailsView` / `ModelFileCard`, reused unchanged as the landing list |
| `src/utils/hfUserAgent.ts` | `hfUserAgent()` |
| `src/api/hf.ts`, `src/services/downloads/DownloadManager.ts`, `android/app/src/main/java/com/pocketpalai/download/DownloadWorker.kt` | the User-Agent header sites |
| `src/__automation__/deepLink.ts`, `benchmarkRoute.ts` | E2E-only routes: `memory`, `tts`, `iap` (FakeStore commands, `in-app-purchase.md`), the benchmark runner |

## How it works

A raw URL reaches JS by one of two paths:

- **iOS:** `AppDelegate` → `RCTOpenURLNotification` → `DeepLinkModule` → `DeepLinkService` → `handleDeepLink`, which checks `isHubLink(params.url)`.
- **Both platforms:** RN `Linking`, through cold `getInitialURL` and the warm `'url'` event. This is the only path on Android.

Both paths call `handleHubRunLink(url)`. That function runs `parseHubRunURL`, which returns `null` for a missing or malformed `repo_id` and triggers an Alert. A valid result goes to `deepLinkStore.setPendingHubRun(request)`.

`HubRunSheetHost` observes `pendingHubRun` and opens a `Sheet`. It then calls `resolveHFRepo(repoId, token)`, followed by `enrichSiblingsWithStorage`, and renders `<DetailsView hfModel={resolved}/>`. When the user taps a file, `ModelFileCard.handleDownload` calls `modelStore.downloadHFModel(hfModel, file, {enableVision: true})`. Dismissing or cancelling the sheet calls `clearPendingHubRun()`.

Host states:

```
hidden ─request set→ resolving ─ok→ ready (DetailsView) ─dismiss→ hidden
                     resolving ─fail→ error ─retry→ resolving
                                       error ─cancel→ hidden
```

There is no host-level download state. Each `ModelFileCard` owns its own progress, and the sheet stays open after a tap.

## Contracts and invariants

- **One parse point for `hub/run`.** `parseHubRunURL` is the only place a hub/run URL is parsed and validated, and both delivery paths call it. `DeepLinkService.parseURL` is not extended for this route.
- **Only the exact route reaches the parser.** `isHubLink` passes only host `hub` with path `run`. Other URLs and unknown hub paths are ignored silently, while a malformed payload on the exact route raises an Alert.
- **Validation precedes side effects.** An invalid `repo_id` causes no store write and no navigation. `repo_id` must match `^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$` with no `.` or `..` segments (`hubRunLink.ts`).
- **Only `repo_id` is load-bearing.** `filename` is optional and never gates acceptance, and the UI ignores it. `source` is passed through unvalidated.
- **No silent download.** The route never downloads anything by itself. A download starts only from a tap on a `ModelFileCard`, through the existing `downloadHFModel`.
- **Siblings must carry download URLs.** They must come from `createSiblingsFromFileDetails`, which fills in each `/resolve/` `url`. A hand-built sibling has an empty `downloadUrl`, and `checkSpaceAndDownload` then returns silently (`ModelStore.ts:1596`).
- **The host must enrich siblings.** It must call `enrichSiblingsWithStorage`, or each `ModelFileCard`'s `canFitInStorage` download gate stays unset (`ModelFileCard.tsx:69`).
- **Single writer for `pendingHubRun`.** It is set only by `handleHubRunLink` and cleared only by the host. A later link overwrites the parked one. Re-delivering an equal request is idempotent only because the host's resolve effect is keyed on `repoId`, not on the request object; keying it on `pendingHubRun` would re-resolve on every duplicate delivery. A sequence counter in the host drops stale resolves.
- **Android filters are host-scoped.** Every prod Android VIEW filter declares both a scheme and a host. There is no bare-scheme handler.
- **User-Agent wire format.** The header is `User-Agent: PocketPal/<version> (ai.pocketpal)`. `<version>` comes from `DeviceInfo.getVersion()` in JS and `BuildConfig.VERSION_NAME` in Android native code. `ai.pocketpal` is a fixed HF attribution key, not the Android applicationId (`com.pocketpalai`). The header is set at:
  - the four HF API calls in `hf.ts` (`fetchModels`, `fetchModelFilesDetails`, `fetchGGUFSpecs`, `fetchModelInfo`)
  - iOS LLM downloads (`DownloadManager` RNFS `headers`)
  - Android LLM downloads (`DownloadWorker.kt:80`)

  Authorization handling is separate and unchanged.

## Traps and decisions

- **Android prod has no native bridge.** That is why the always-on `Linking` effect exists.
- **iOS delivers links more than once.** A warm iOS link reaches both paths, because `RCTOpenURLNotification` is observed by both `DeepLinkModule` and RN's linking manager. A cold launch can deliver up to three times. This is safe only because re-parking an equal request is idempotent, so keep it that way.
- **`MainActivity.onNewIntent` must call `setIntent`.** Under `singleTask`, `ReactActivity` does not forward a warm intent, so without it the `Linking` `'url'` event never fires.
- **The E2E `iap` host works only on iOS.** Android's `Linking` listener routes only the benchmark URL, so Android specs script the FakeStore through the hidden `IapAdapter` instead.
- **`chat` works only on iOS.** It is selected by host alone, arrives only through the native emitter, and has no Android intent filter.
- **iOS scheme registration has two sites.** The `Info.plist` dict is enough for a cold launch, which is forwarded unfiltered. The warm path also needs the `AppDelegate` check. That check must stay an exact match and never a wildcard: Google Sign-In depends on the `return false` for its own scheme.
- **The parsers are not scheme-gated.** `isHubLink` and `parseHubRunURL` test only hostname and path, and `handleDeepLink` doesn't reject unknown schemes. This is safe only while `pocketpal` is the only scheme the app routes, yet an iOS cold launch already passes any registered scheme, including Google's, to `getInitialURL`. Before registering a second scheme, scheme-gate the dispatcher and every route parser. The raw `Linking` path never goes through the dispatcher.
- **The host is global.** It is mounted once inside `BottomSheetModalProvider`, parks a request without navigating, and survives a cold start. Don't move it into a screen.
- **The sheet lands on the full quant list.** The HF link carries no quant, so the product lets the user pick.
- **Keep the two resolvers separate.** `resolveHFRepo` is strict: any fetch failure throws. `resolveHFModelForDownload` catches each fetch independently and falls back to a caller-supplied `{author, size, downloadUrl}`, which `PalStore.createLocalModelFromPHModel` needs.
- **Log only `e.message` from resolve errors.** Axios errors can carry the HF bearer token in `config.headers`.
- **The User-Agent is missing at several HF request sites.** TTS engine model downloads (`RNFS.downloadFile` in `src/services/tts/engines/*`) and GGUF header range reads (`src/utils/ggufHeader.ts:93`) send no attribution User-Agent. HF attribution misses those bytes.

## Verification

- Unit tests: `src/hooks/__tests__/useDeepLinking.test.ts`, `useDeepLinking.hubRun.test.ts`, `src/services/__tests__/hubRunLink.test.ts`, `src/utils/__tests__/hfResolve.test.ts`, `src/components/HubRunSheetHost/__tests__/`, `src/api/__tests__/hfUserAgent.test.ts`.
- E2E: `e2e/specs/features/hub-run.spec.ts` covers a valid link through download, load and chat, plus the missing-`repo_id` rejection.
- By hand:
  - **Open a link.** On Android, run `adb shell am start -a android.intent.action.VIEW -d "pocketpal://hub/run?repo_id=<org>/<repo>"`, both cold and warm. On iOS, run `xcrun simctl openurl booted "<url>"`.
  - **User-Agent.** Check it on the wire through a proxy.
