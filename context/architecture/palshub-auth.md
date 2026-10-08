# PalsHub Auth

(**unmerged PR only**: Sign in with Apple is not on `main` yet; the rest describes `main`.)

## Purpose

Signing in to PalsHub (Supabase auth) from the app: email/password, Google, and Sign in with Apple on iOS, the profile row the app reads and writes, and sign-out. Not covered: what a signed-in user can do with Pals (`pals-and-talents.md`), purchase binding to an account (`in-app-purchase.md`), the Settings surface that opens the sheet (`settings.md`), and the Google URL scheme (`deep-linking.md`).

## Code map

| Path | Role |
| --- | --- |
| `src/services/palshub/AuthService.ts` | MobX singleton `authService`: every sign-in method, sign-out, auth listener, profile load and the Apple name write. Persists only `profile` |
| `src/services/palshub/supabase.ts` | Supabase client (session in AsyncStorage, `detectSessionInUrl: false`); `null` when `SUPABASE_URL`/`SUPABASE_ANON_KEY` are unset |
| `src/components/PalsHub/AuthSheet/` | The only sign-in surface: email form, Apple button (iOS), Google button. Opened from `PalsScreen` and `SettingsScreen` |
| `src/screens/PalsScreen/components/ProfileSheet/` | Signed-in identity and Sign out |
| `react-native.config.js` | Excludes `@invertase/react-native-apple-authentication` from Android autolinking |
| `ios/PocketPal/PocketPal.entitlements` | `com.apple.developer.applesignin` (shared by all build configs) |
| `__mocks__/external/@invertase/react-native-apple-authentication.ts`, `__mocks__/services/palshub/AuthService.js` | Jest mocks of the Apple library and of `authService` |

## How it works

Each sign-in method gets an id token or credentials from its provider and hands them to Supabase (`signInWithIdToken` for Google and Apple, `signInWithPassword`/`signUp` for email). From there one shared path runs: `onAuthStateChange` sets `session`/`user`/`isAuthenticated` and, on `SIGNED_IN`, `loadUserProfile` reads the caller's `profiles` row. `AuthSheet` closes itself when `isAuthenticated` turns true. Errors land in `authService.error`, which the sheet renders. Methods never throw to the caller.

**Apple (iOS).** `signInWithApple` calls `appleAuth.performRequest` (LOGIN, scopes EMAIL + FULL_NAME, library nonce on), then `signInWithIdToken({provider: 'apple', token: identityToken, nonce})`. On success `storeFirstAppleName` composes the name from the trimmed given and family names. It writes the name only when it is non-empty and the loaded profile for this user has no `full_name`. It runs `auth.updateUser({data: {full_name}})` and a `profiles` UPDATE of `full_name`/`updated_at` side by side, logs any failure, then reloads the profile once.

**Sign-out**: `supabase.auth.signOut()` plus a best-effort Google sign-out. The listener's `SIGNED_OUT` clears `profile`. Apple has no client sign-out.

## Contracts and invariants

- **The profiles row is created only by the server.** The `handle_new_user` trigger on `auth.users` insert copies `full_name`/`name` from user metadata. The app holds no INSERT grant: its only `profiles` write is the UPDATE in `storeFirstAppleName`, scoped `.eq('id', userId)`. Never upsert or insert.
- **Name writes never fail a sign-in.** Neither write touches `authService.error` or `isAuthenticated`. Both run even when one fails (`Promise.allSettled`).
- **The raw nonce goes to Supabase.** The library sends SHA-256(nonce) to Apple and returns the raw value as `response.nonce`. Supabase hashes it again to compare. Sending the hash, or disabling the nonce, fails sign-in.
- **The Apple provider's Client IDs must include `ai.pocketpal`** (the bundle id is the token audience). No secret is used by the native flow.
- **Single writers.** `profiles.full_name`: `storeFirstAppleName`. `user_metadata.full_name`: `signUpWithEmail` and `storeFirstAppleName`, never both for one sign-in. `session`/`user`/`isAuthenticated`: the auth listener and `checkExistingSession`.
- **Android ships none of Apple.** The library is excluded from Android autolinking, so it is no Gradle subproject and not in `PackageList`. `AuthSheet` renders the Apple button only when `Platform.OS === 'ios' && appleAuth.isSupported`.
- **Apple button prominence.** The native `AppleButton` (App Review 4.8 / HIG) sits directly above Google, full width, 48 high, and uses Paper's button radius (`5 × theme.roundness`). Style is BLACK on light and WHITE on dark.
- **Release gate.** Production Supabase must have the Apple provider live before an iOS build with the button is submitted. Otherwise App Review hits a sign-in error.

## Traps and decisions

- **Apple sends the name only on the first authorization.** If anything fails between Apple's response and the name write (Supabase error, a write error, the app killed), the name is lost until the user revokes the app under Apple ID › Sign in with Apple. The id token never carries a name, so the trigger creates the row with `full_name` NULL.
- **The empty-name check keys on the user id.** A persisted `profile` can belong to another user when its load failed. Only this user's stored name blocks the write, so a re-authorization never overwrites a name the user edited.
- **Double tap.** The native button has no `disabled` prop. `handleAppleAuth` returns early while `authService.isLoading` is set, reading the live field rather than the render snapshot. It doesn't set the sheet's local `isLoading`, so the Google button doesn't spin during an Apple sign-in.
- **Cancel shows a message**: code `'1001'` → "Sign-in was cancelled", the same as Google.
- **Account linking is server policy.** Supabase links an Apple identity to an existing user only when both emails match and are verified. A Hide My Email relay address never matches, so it creates a separate user with an empty library and no purchases. The app builds no linking.
- **`ProfileSheet` shows `user_metadata.name` or email,** not `profiles.full_name`. An Apple user therefore sees their email, which is the relay address for Hide My Email.
- **Apple token revocation on account deletion** (App Review 5.1.1(v)) is the PalsHub backend's duty, not the app's.
- **Library choice**: `@invertase/react-native-apple-authentication` (exact pin) hashes the nonce natively, so the app needs no JS crypto. It imports `prop-types` without declaring it, so `prop-types` is a direct dependency to survive hoisting changes.
- **Not Expo, no URL scheme.** The native ASAuthorization flow needs no `Info.plist` scheme and no `AppDelegate` change, unlike Google.

## Verification

- Unit: `src/services/palshub/__tests__/AuthService.test.ts` covers the raw nonce, cancel and failure mapping, the name writes (payloads, skip rules, failure isolation, no upsert or insert) and sign-out. `src/components/PalsHub/AuthSheet/__tests__/AuthSheet.test.tsx` covers the Apple button order, Android and unsupported hiding, the loading guard and the Google spinner.
- Android exclusion: `jq '.dependencies["@invertase/react-native-apple-authentication"].platforms.android' android/build/generated/autolinking/autolinking.json` is `null`, and `PackageList.java` has no `AppleAuth`. Removing the `react-native.config.js` entry makes both appear: that is the negative control.
- By hand: a dev build on a real iPhone against a local Supabase (`supabase start` with `[auth.external.apple] enabled = true`, `client_id = "ai.pocketpal"`). Never use QA or prod: QA shares the production database. Check `profiles.full_name` and `auth.users.raw_user_meta_data` after the first sign-in.
