# PalsHub Auth

(**Account deletion is PR #970 only**; the rest describes `main`.)

## Purpose

Signing in to PalsHub (Supabase auth) from the app: email/password, Google, and Sign in with Apple on iOS, the profile row the app reads and writes, sign-out, and in-app account deletion. Not covered: what a signed-in user can do with Pals (`pals-and-talents.md`), purchase binding to an account (`in-app-purchase.md`), the Settings surface that opens the sheet (`settings.md`), and the Google URL scheme (`deep-linking.md`).

## Code map

| Path | Role |
| --- | --- |
| `src/services/palshub/AuthService.ts` | MobX singleton `authService`: every sign-in method, sign-out (optional `scope`), auth listener, profile load, the Apple name write, and the deletion helpers `hasAppleIdentity` / `appleSubject` / `reauthorizeWithApple`. Persists only `profile` |
| `src/services/palshub/supabase.ts` | Supabase client (session in AsyncStorage, `detectSessionInUrl: false`); `null` when `SUPABASE_URL`/`SUPABASE_ANON_KEY` are unset |
| `src/components/PalsHub/AuthSheet/` | The only sign-in surface: email form, Apple button (iOS), Google button. Opened from `PalsScreen` and `SettingsScreen` |
| `src/screens/PalsScreen/components/ProfileSheet/` | Signed-in identity and Sign out |
| `src/services/palshub/accountApi.ts` | The delete request (`POST /api/mobile/account/delete`, own 15 s timeout) and the pure status → outcome mapping |
| `src/services/palshub/accountDeletion.ts` | `deleteAccount()`: Apple step, request, one 401 retry, local clean-up. Not re-exported from `palshub/index.ts` |
| `src/screens/SettingsScreen/AccountCard.tsx` | Settings › Account: Delete account, the confirmation and the outcome alerts |
| `react-native.config.js` | Excludes `@invertase/react-native-apple-authentication` from Android autolinking |
| `ios/PocketPal/PocketPal.entitlements` | `com.apple.developer.applesignin` (shared by all build configs) |
| `__mocks__/external/@invertase/react-native-apple-authentication.ts`, `__mocks__/services/palshub/AuthService.js`, `__mocks__/services/palshub/accountDeletion.js` | Jest mocks of the Apple library, of `authService`, and of `deleteAccount` (global, wired in `jest/setup.ts`) |

## How it works

Each sign-in method gets an id token or credentials from its provider and hands them to Supabase (`signInWithIdToken` for Google and Apple, `signInWithPassword`/`signUp` for email). From there one shared path runs: `onAuthStateChange` sets `session`/`user`/`isAuthenticated` and, on `SIGNED_IN`, `loadUserProfile` reads the caller's `profiles` row. `AuthSheet` closes itself when `isAuthenticated` turns true. Errors land in `authService.error`, which the sheet renders. Methods never throw to the caller.

**Apple (iOS).** `signInWithApple` calls `appleAuth.performRequest` (LOGIN, scopes EMAIL + FULL_NAME, library nonce on), then `signInWithIdToken({provider: 'apple', token: identityToken, nonce})`. On success `storeFirstAppleName` composes the name from the trimmed given and family names. It writes the name only when it is non-empty and the loaded profile for this user has no `full_name`. It runs `auth.updateUser({data: {full_name}})` and a `profiles` UPDATE of `full_name`/`updated_at` side by side, logs any failure, then reloads the profile once.

**Sign-out**: `supabase.auth.signOut()` (global by default; `signOut({scope: 'local'})` passes the scope through) plus a best-effort Google sign-out. The listener's `SIGNED_OUT` clears `profile`. Apple has no client sign-out.

**Account deletion.** `AccountCard` (signed in only) confirms once, awaits `deleteAccount()` and alerts the outcome (none for `cancelled`). `deleteAccount()`: on iOS, for an Apple-identity user, `reauthorizeWithApple()` runs first. No bearer from `getAuthHeaders()` → `sign_in_again` with no request. A 401 gets one `refreshSession()` and one retry with the same body and the fresh token. On `deleted`, in order: `signOut({scope: 'local'})` → `palStore.clearAccountPals()` → `syncService.clearCache()`. The card then disappears with `isAuthenticated`.

## Contracts and invariants

- **The profiles row is created only by the server.** The `handle_new_user` trigger on `auth.users` insert copies `full_name`/`name` from user metadata. The app holds no INSERT grant: its only `profiles` write is the UPDATE in `storeFirstAppleName`, scoped `.eq('id', userId)`. Never upsert or insert.
- **Name writes never fail a sign-in.** Neither write touches `authService.error` or `isAuthenticated`. Both run even when one fails (`Promise.allSettled`).
- **The raw nonce goes to Supabase.** The library sends SHA-256(nonce) to Apple and returns the raw value as `response.nonce`. Supabase hashes it again to compare. Sending the hash, or disabling the nonce, fails sign-in.
- **The Apple provider's Client IDs must include `ai.pocketpal`** (the bundle id is the token audience). No secret is used by the native flow.
- **Single writers.** `profiles.full_name`: `storeFirstAppleName`. `user_metadata.full_name`: `signUpWithEmail` and `storeFirstAppleName`, never both for one sign-in. `session`/`user`/`isAuthenticated`: the auth listener and `checkExistingSession`.
- **Android ships none of Apple.** The library is excluded from Android autolinking, so it is no Gradle subproject and not in `PackageList`. `AuthSheet` renders the Apple button only when `Platform.OS === 'ios' && appleAuth.isSupported`.
- **Apple button prominence.** The native `AppleButton` (App Review 4.8 / HIG) sits directly above Google, full width, 48 high, and uses Paper's button radius (`5 × theme.roundness`). Style is BLACK on light and WHITE on dark.
- **Release gate.** Production Supabase must have the Apple provider live before an iOS build with the button is submitted. Otherwise App Review hits a sign-in error.
- **Deletion: no request without consent.** `fetch` to the delete route runs only after the confirmation's destructive button, and never after an Apple cancel.
- **Deletion: "deleted" only on 200 or 410.** No other status, error or retry path returns `deleted` or runs the clean-up; clean-up failures never change the outcome.
- **Deletion: the support contact comes from the server.** A 409 `creator_contact_support` without a non-empty string `contact` is `failed`; the app hardcodes no address.
- **Deletion: never another person's Apple code.** The code is sent only when `appleUser` equals the account's Apple subject (`identity_data.sub`, else the identity `id`), or when only `app_metadata.providers` names Apple so there is nothing to compare. Otherwise the body is `{}`.
- **Deletion: secrets stay out of logs and UI.** The Apple code, bearer and server bodies are never logged (status and error `name` only).
- **`deleteAccount()` never throws** and never writes `authService.error` or `isLoading` itself, so `AuthSheet` never shows a deletion error.
- **One deletion in flight.** Concurrent calls share the pending promise; the button is disabled meanwhile.

## Traps and decisions

- **Apple sends the name only on the first authorization.** If anything fails between Apple's response and the name write (Supabase error, a write error, the app killed), the name is lost until the user revokes the app under Apple ID › Sign in with Apple. The id token never carries a name, so the trigger creates the row with `full_name` NULL.
- **The empty-name check keys on the user id.** A persisted `profile` can belong to another user when its load failed. Only this user's stored name blocks the write, so a re-authorization never overwrites a name the user edited.
- **Double tap.** The native button has no `disabled` prop. `handleAppleAuth` returns early while `authService.isLoading` is set, reading the live field rather than the render snapshot. It doesn't set the sheet's local `isLoading`, so the Google button doesn't spin during an Apple sign-in.
- **Apple sign-in never shows a raw Supabase or Apple message.** `appleSignInErrorMessage` maps errors by auth-js type guards and status, never by string matching: `isAuthRetryableFetchError` or status ≥ 500 → "Couldn't reach the server"; `isAuthApiError` 4xx (provider off, bad token, nonce) → "isn't available right now"; Apple `'1000'` (UNKNOWN: iOS returns it when the user closes the "Sign in to your Apple Account" prompt on a device with no account) → "Sign in to your Apple Account in Settings"; anything else, including a missing id token → "Sign in with Apple failed". The raw error goes to `console.error` only. The reason: a retryable fetch error's `message` is the serialized `Response`, with headers and the backend URL. The Google path still surfaces `error.message`.
- **Cancel** (`'1001'`) shows "Sign-in was cancelled" (as Google does) and logs with `console.warn`, not `console.error`: it is a user choice, not a fault.
- **No client-side timeout** on the Apple path: an unresponsive auth server leaves the sheet loading until the request itself fails (supabase-js sets no timeout).
- **Account linking is server policy.** Supabase links an Apple identity to an existing user only when both emails match and are verified. A Hide My Email relay address never matches, so it creates a separate user with an empty library and no purchases. The app builds no linking. Observed on a local Supabase: an existing confirmed email-signup user whose email equals the Apple token's verified email is linked (one user, identities `apple` and `email`, existing `full_name` kept); a different Apple email creates a separate user.
- **`ProfileSheet` shows `user_metadata.name` or email,** not `profiles.full_name`. An Apple user therefore sees their email, which is the relay address for Hide My Email.
- **The server revokes the Apple token on deletion** (App Review 5.1.1(v)). The app sends a fresh code only for a matching Apple user on iOS, else `{}`. Revoke failures never block deletion, so every Apple failure except cancel (`'1001'`) sends `{}` and proceeds. Android never prompts Apple.
- **The re-authorization is not `signInWithApple`.** That would sign in again, write the name and set `error`; `reauthorizeWithApple` writes nothing.
- **Status decides, the body only supplies `contact`.** `postAccountDelete` reads JSON only for a 409; `iapApi`'s `request` drops the body and `PalsHubApiService.apiRequest` logs it, so neither is reused. `Retry-After` is ignored.
- **Local sign-out after deletion can keep the session.** auth-js still POSTs `/logout?scope=local`; a transport error returns without removing the session (a 4xx is ignored and the session removed). The outcome stays `deleted`; a kept session clears at its next refresh, which fails non-retryably.
- **A cached `user` may lack a newly linked Apple identity,** so `{}` is sent and the server deletes without revoking. Accepted; a `getUser()` refresh before the decision is deferred.
- **Library choice**: `@invertase/react-native-apple-authentication` (exact pin) hashes the nonce natively, so the app needs no JS crypto. It imports `prop-types` without declaring it, so `prop-types` is a direct dependency to survive hoisting changes.
- **Not Expo, no URL scheme.** The native ASAuthorization flow needs no `Info.plist` scheme and no `AppDelegate` change, unlike Google.

## Verification

- Unit: `src/services/palshub/__tests__/AuthService.test.ts` covers the raw nonce, one test per error-message branch, the name writes (payloads, skip rules, failure isolation, no upsert or insert), sign-out and its scope, and the deletion helpers. Deletion: `accountApi.test.ts` (one case per status; fixtures in `jest/fixtures/accountDeletion.ts` are copied verbatim from the server contract), `accountDeletion.test.ts`, `src/screens/SettingsScreen/__tests__/AccountCard.test.tsx` (exact copy), `src/store/__tests__/PurchaseStore.accountDeletion.test.ts`. `src/components/PalsHub/AuthSheet/__tests__/AuthSheet.test.tsx` covers the Apple button order, Android and unsupported hiding, the loading guard and the Google spinner.
- Android exclusion: `jq '.dependencies["@invertase/react-native-apple-authentication"].platforms.android' android/build/generated/autolinking/autolinking.json` is `null`, and `PackageList.java` has no `AppleAuth`. Removing the `react-native.config.js` entry makes both appear: that is the negative control.
- By hand: a dev build on a real iPhone against a local Supabase (`supabase start` with `[auth.external.apple] enabled = true`, `client_id = "ai.pocketpal"`). Never use QA or prod: QA shares the production database. Check `profiles.full_name` and `auth.users.raw_user_meta_data` after the first sign-in. Deletion: run the server's delete route on the local Supabase only; check the `auth.users` row is gone, a repeat call with the old token answers 410, a creator account gets the 409 contact, and on iOS an Apple cancel sends no request.
