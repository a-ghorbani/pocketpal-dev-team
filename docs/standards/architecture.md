# PocketPal Architecture Standards

Architectural rules for PocketPal AI. Stack, project layout, and the store list: `context/pocketpal-overview.md`. Code patterns (store, component, hook, tests, navigation, file layout): `context/patterns.md`. Per-flow contracts: `context/architecture/`.

## State management (MobX)

Stores are singleton instances, independently instantiated (no root store). `ServerStore` keeps credentials in the keychain; `TTSStore` covers the Kitten, Kokoro, and Supertonic engines.

1. **Single source of truth**: each domain has one store.
2. **Singleton**: export the instance, not the class.
3. **Observable state**: all state properties observable.
4. **Actions for mutations**: no direct state modification.
5. **Async = `runInAction`**: wrap state updates after an `await`.

An error a store surfaces lives in its own `error: string | null`, set in `runInAction` (`e instanceof Error ? e.message : "Unknown error"`).

## Components

| Type | Location | Purpose |
| --- | --- | --- |
| Screen | `src/screens/` | Full-screen views, navigation targets |
| Component | `src/components/` | Reusable UI building blocks |
| Sheet | `src/components/*Sheet/` | Bottom sheet modals |

1. **Functional only**: no class components.
2. **`observer()`**: wrap components that read store state.
3. **Theme from `useTheme()`**, never hardcoded colors.
4. **Styles**: per `context/patterns.md`, Component Pattern (`styles.ts` with `createStyles({theme})`).
5. **`testID`** on every interactive element.

Errors: React error boundaries for component-level recovery.

## Localization (l10n)

`src/locales/` holds per-language JSON files and a TypeScript loader:

```
src/locales/
├── index.ts        # languageRegistry, lazy l10n object, t() helper, initLocale
├── types.ts        # Translations type derived from `typeof enData`
├── en.json         # Source of truth — only this file is hand-edited
└── <code>.json     # Other languages, managed by translators on Weblate
```

Non-English translations are lazy-loaded on first access through getters (Metro bundles them; `require()` runs when the property is read). `languageRegistry` in `src/locales/index.ts` is the single source of truth for keys, display names, and `supportedLanguages`. Non-English files fall back to English via `_.merge({}, enData, langData)` (overlay).

1. **No hardcoded strings**: all UI text lives in `src/locales/en.json`.
2. **Edit only `en.json`**: other languages sync from Weblate; never hand-edit them.
3. **Semantic keys**: `section.descriptiveKey`.
4. **Placeholders**: `{{variable}}` with the `t()` helper, not manual `.replace()`.
5. **Adding a language**: update `languageRegistry`, `requireLanguageData()`, the getter on the `l10n` object, the `dayjs` locale require in `initLocale`, and the related test/E2E lists (`tools/context search l10n`).

```typescript
import { l10n, t } from "../../locales";
import { uiStore } from "../../store";

const cancel = l10n[uiStore.language].common.cancel;
const progressText = t(l10n[uiStore.language].models.downloadProgress, { progress: "45%" });
```

## Navigation

```
DrawerNavigator (Root)
├── ChatScreen (default)
├── ModelsScreen
├── PalsScreen
├── BenchmarkScreen
├── SettingsScreen
├── AboutScreen
└── DevToolsScreen (debug only)
```

Typed `useNavigation<DrawerNavigationProp<RootDrawerParamList>>()`; example in `context/patterns.md`, Navigation Pattern.

## Native integration (llama.rn)

Model lifecycle: Download → Load → Initialize Context → Inference → Release.

| Concept | Description |
| --- | --- |
| Context | llama.cpp inference context, holds model state |
| Completion | Text generation from prompt |
| Tokenization | Converting text to/from tokens |
| GPU Layers | Number of layers offloaded to GPU |

```typescript
import { initLlama } from "llama.rn";

const context = await initLlama({ model: modelPath, n_ctx: contextSize, n_gpu_layers: gpuLayers });
const result = await context.completion({ prompt: "Hello", n_predict: 100 });
await context.release();
```

| Platform | GPU acceleration | Notes |
| --- | --- | --- |
| iOS | Metal | Requires iOS 18+ for full Metal |
| Android | OpenCL (Adreno) | Experimental, Adreno GPUs only |
| Android | Hexagon NPU | Qualcomm devices only |

## Testing

Centralized mocking (stores mocked globally in `jest/setup.ts`), custom render from `jest/test-utils.tsx` (not raw RNTL) with its provider options, fixtures from `jest/fixtures`, `runInAction` for state changes: `context/patterns.md`, Testing Infrastructure.

## Errors, performance, security

- **User-facing errors**: l10n messages with actionable guidance; log details for debugging, never sensitive data.
- **Components**: granular `observer()` (smaller components); no inline object/function creation in render; `useMemo`/`useCallback` where they help; `FlatList` with `keyExtractor` for long lists.
- **Memory**: release llama contexts when not needed; clean up subscriptions in the `useEffect` return; don't hold references to large objects.
- **Models**: context size fits device memory; GPU offload by device capability; tune batch size for throughput.
- **Sensitive data**: no secrets in code (use `.env`); no PII in logs; secure storage for tokens.
- **Input**: validate user inputs; sanitize file paths; validate model files before loading.
- **Network**: HTTPS only; validate API responses; handle timeouts gracefully.

## Code style

- **TypeScript**: strict mode; explicit parameter types; no `any` (use `unknown`); interfaces for object shapes.
- **Imports**: external, then internal, then relative, each group separated by a blank line.

| Type | Convention | Example |
| --- | --- | --- |
| Components | PascalCase | `ChatInput.tsx` |
| Hooks | camelCase + use | `useMemoryCheck.ts` |
| Stores | PascalCase + Store | `ModelStore.ts` |
| Utils | camelCase | `formatters.ts` |
| Constants | SCREAMING_SNAKE | `MAX_CONTEXT_SIZE` |

## Git

- **Branches**: `AGENTS.md`, Worktrees and naming.
- **Commits**: `type(scope): subject`, type only `feat`, `fix`, `docs`, or `chore` (`commitlint.config.js`), e.g. `fix(model): prevent crash on context release`.
- **PRs**: descriptive title and body; tests for new code; new strings in `en.json` only; native builds verified when applicable (`AGENTS.md`, Native changes).
