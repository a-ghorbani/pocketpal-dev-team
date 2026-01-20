# PocketPal Architecture Standards

Reference document for architectural decisions and standards in PocketPal AI.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | React Native |
| State Management | MobX |
| UI Components | React Native Paper |
| Navigation | React Navigation (Drawer + Stack) |
| Database | WatermelonDB |
| LLM Runtime | llama.rn (llama.cpp bindings) |
| Testing | Jest + React Native Testing Library |
| Build | Metro, Gradle (Android), Xcode (iOS) |

---

## Project Structure

```
pocketpal-ai/
├── src/
│   ├── components/       # Reusable UI components
│   ├── screens/          # Screen-level components
│   ├── store/            # MobX stores
│   ├── hooks/            # Custom React hooks
│   ├── services/         # Business logic services
│   ├── utils/            # Utility functions
│   ├── api/              # API clients
│   ├── types/            # TypeScript types
│   └── config/           # App configuration
├── ios/                  # iOS native code
├── android/              # Android native code
├── jest/                 # Test infrastructure
├── __mocks__/            # Mock implementations
└── e2e/                  # End-to-end tests
```

---

## State Management (MobX)

### Store Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Root Store                         │
├─────────────┬─────────────┬─────────────┬──────────────┤
│ ModelStore  │ChatSession  │  UIStore    │  PalStore    │
│             │   Store     │             │              │
├─────────────┼─────────────┼─────────────┼──────────────┤
│ - models    │ - sessions  │ - language  │ - pals       │
│ - active    │ - messages  │ - theme     │ - favorites  │
│ - loading   │ - current   │ - settings  │ - syncing    │
└─────────────┴─────────────┴─────────────┴──────────────┘
```

### Store Responsibilities

| Store | Responsibility |
|-------|----------------|
| `ModelStore` | Model lifecycle, loading, inference context |
| `ChatSessionStore` | Chat sessions, message history, active conversation |
| `UIStore` | UI state, language, theme, user preferences |
| `PalStore` | Pal configurations, system prompts |
| `DownloadStore` | Model downloads, progress tracking |

### Store Rules

1. **Single source of truth**: Each domain has ONE store
2. **Singleton pattern**: Export instance, not class
3. **Observable state**: All state properties observable
4. **Actions for mutations**: No direct state modification
5. **Async = runInAction**: Wrap async state updates

```typescript
// CORRECT store pattern
class ExampleStore {
  items: Item[] = [];
  isLoading = false;

  constructor() {
    makeAutoObservable(this);
  }

  async fetchItems() {
    this.isLoading = true;
    try {
      const items = await api.getItems();
      runInAction(() => {
        this.items = items;
        this.isLoading = false;
      });
    } catch (e) {
      runInAction(() => {
        this.isLoading = false;
      });
    }
  }
}

export const exampleStore = new ExampleStore();
```

---

## Component Architecture

### Component Types

| Type | Location | Purpose |
|------|----------|---------|
| Screen | `src/screens/` | Full-screen views, navigation targets |
| Component | `src/components/` | Reusable UI building blocks |
| Sheet | `src/components/*Sheet/` | Bottom sheet modals |

### Component Structure

```typescript
// Functional component with observer HOC
export const MyComponent: React.FC<Props> = observer(({prop1, prop2}) => {
  const theme = useTheme();

  // Styles inside component (theme-aware)
  const styles = StyleSheet.create({
    container: {
      padding: theme.spacing.md,
      backgroundColor: theme.colors.surface,
    },
  });

  return (
    <View style={styles.container} testID="my-component">
      {/* content */}
    </View>
  );
});
```

### Component Rules

1. **Functional only**: No class components
2. **observer() HOC**: Wrap components that read store state
3. **Theme from hook**: Use `useTheme()`, not hardcoded colors
4. **Styles inside**: StyleSheet.create inside component for theme access
5. **testID required**: All interactive elements need testID

---

## Localization (L10n)

### Structure

```typescript
// src/utils/l10n.ts
export const l10n = {
  en: {
    common: { cancel: 'Cancel', ... },
    settings: { ... },
    chat: { ... },
    models: { ... },
  },
  ja: { /* Japanese translations */ },
  zh: { /* Chinese translations */ },
};
```

### Supported Languages

| Code | Language | Status |
|------|----------|--------|
| `en` | English | Primary |
| `ja` | Japanese | Supported |
| `zh` | Chinese (Simplified) | Supported |

### L10n Rules

1. **No hardcoded strings**: All UI text in l10n.ts
2. **All languages**: New strings in ALL 3 languages
3. **Semantic keys**: `section.descriptiveKey`
4. **Placeholders**: Use `{{variable}}` syntax

```typescript
// Usage in component
import {l10n} from '../utils';
import {uiStore} from '../store';

const text = l10n[uiStore.language].common.cancel;

// With placeholder
const text = l10n[uiStore.language].models.downloadProgress
  .replace('{{progress}}', '45%');
```

---

## Navigation

### Structure

```
DrawerNavigator (Root)
├── ChatScreen (default)
├── ModelsScreen
├── PalsScreen
├── BenchmarkScreen
├── SettingsScreen
└── AboutScreen
```

### Navigation Patterns

```typescript
import {useNavigation} from '@react-navigation/native';
import {DrawerNavigationProp} from '@react-navigation/drawer';

type NavigationProp = DrawerNavigationProp<RootDrawerParamList>;

const navigation = useNavigation<NavigationProp>();
navigation.navigate('ScreenName', {param: 'value'});
```

---

## Native Integration (llama.rn)

### Model Lifecycle

```
Download → Load → Initialize Context → Inference → Release
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| Context | llama.cpp inference context, holds model state |
| Completion | Text generation from prompt |
| Tokenization | Converting text to/from tokens |
| GPU Layers | Number of layers offloaded to GPU |

### Native Module Access

```typescript
import {initLlama, LlamaContext} from 'llama.rn';

// Initialize context
const context = await initLlama({
  model: modelPath,
  n_ctx: contextSize,
  n_gpu_layers: gpuLayers,
});

// Run completion
const result = await context.completion({
  prompt: 'Hello',
  n_predict: 100,
});

// Release when done
await context.release();
```

### Platform Considerations

| Platform | GPU Acceleration | Notes |
|----------|------------------|-------|
| iOS | Metal | Requires iOS 18+ for full Metal |
| Android | OpenCL (Adreno) | Experimental, Adreno GPUs only |
| Android | Hexagon NPU | Qualcomm devices only |

---

## Testing Architecture

### Test Infrastructure

```
jest/
├── setup.ts           # Global mocks (stores, modules)
├── setupFilesAfterEnv.ts  # Lifecycle hooks
├── test-utils.tsx     # Custom render with providers
├── fixtures.ts        # Shared test data
└── fixtures/          # Domain-specific fixtures
    ├── models.ts
    ├── pals.ts
    └── theme.ts

__mocks__/
├── stores/            # Mock store implementations
├── external/          # External package mocks
└── services/          # Service mocks
```

### Testing Principles

1. **Centralized mocking**: Stores mocked globally in jest/setup.ts
2. **Custom render**: Use jest/test-utils.tsx, not raw RNTL
3. **Fixtures over inline data**: Import from jest/fixtures
4. **MobX awareness**: Use runInAction for state changes
5. **Provider wrapping**: Use render options for providers

See `context/patterns.md` for detailed testing patterns.

---

## Error Handling

### Error Boundaries

React error boundaries for component-level recovery.

### Store Error State

```typescript
class Store {
  error: string | null = null;

  async doSomething() {
    try {
      // ...
    } catch (e) {
      runInAction(() => {
        this.error = e instanceof Error ? e.message : 'Unknown error';
      });
    }
  }
}
```

### User-Facing Errors

- Use l10n for error messages
- Provide actionable guidance
- Log details for debugging (not sensitive data)

---

## Performance Guidelines

### Component Performance

- Use `observer()` granularly (smaller components)
- Avoid inline object/function creation in render
- Use `useMemo`/`useCallback` appropriately
- FlatList for long lists with `keyExtractor`

### Memory Management

- Release llama contexts when not needed
- Clean up subscriptions in useEffect return
- Avoid holding references to large objects

### Model Performance

- Appropriate context size for device memory
- GPU offloading based on device capability
- Batch size tuning for throughput

---

## Security Guidelines

### Sensitive Data

- No secrets in code (use .env)
- No PII in logs
- Secure storage for tokens

### Input Validation

- Validate user inputs
- Sanitize file paths
- Validate model files before loading

### Network

- HTTPS only
- Validate API responses
- Handle timeouts gracefully

---

## Code Style

### TypeScript

- Strict mode enabled
- Explicit types for function parameters
- Avoid `any` (use `unknown` if needed)
- Interfaces for object shapes

### Naming

| Type | Convention | Example |
|------|------------|---------|
| Components | PascalCase | `ChatInput.tsx` |
| Hooks | camelCase + use | `useMemoryCheck.ts` |
| Stores | PascalCase + Store | `ModelStore.ts` |
| Utils | camelCase | `formatters.ts` |
| Constants | SCREAMING_SNAKE | `MAX_CONTEXT_SIZE` |

### Imports

```typescript
// Order: external → internal → relative
import React from 'react';
import {View} from 'react-native';
import {observer} from 'mobx-react';

import {useTheme} from '../../hooks';
import {modelStore} from '../../store';

import {ChildComponent} from './ChildComponent';
```

---

## Git Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `chore/description` - Maintenance

### Commit Messages

**Format**: `type(scope): subject`

**Types**: `feat`, `fix`, `docs`, `chore` (only these 4)

**Example**:
```
feat(chat): add voice input button
fix(model): prevent crash on context release
chore(deps): upgrade llama.rn to 0.11.0
```

### PR Requirements

- Descriptive title and body
- Tests for new code
- L10n for new strings (all languages)
- Native builds verified (if applicable)
