# PocketPal AI - Codebase Overview

## What is PocketPal?

PocketPal AI is a privacy-first, on-device LLM chat application for iOS and Android. All AI inference runs locally on the device using llama.cpp - no data leaves the device unless the user explicitly shares it.

## Repository

Location: `/Users/aghorbani/codes/pocketpal-ai`

## Technology Stack

| Category | Technology | Version |
|----------|------------|---------|
| Framework | React Native | 0.82.1 |
| Language | TypeScript | 5.0.4 |
| State | MobX | 6.15.0 |
| Navigation | React Navigation | 7.x |
| Database | WatermelonDB | 0.28.0 |
| UI Kit | React Native Paper | 5.14.5 |
| LLM | llama.rn (llama.cpp) | 0.10.0 |
| Testing | Jest + Appium | 29.6.3 |

## Project Structure

```
pocketpal-ai/
├── src/
│   ├── api/           # External API integrations (HuggingFace, feedback)
│   ├── components/    # UI components (63 components)
│   ├── config/        # App configuration
│   ├── database/      # WatermelonDB schema and models
│   ├── hooks/         # Custom React hooks (12 hooks)
│   ├── repositories/  # Data access layer
│   ├── screens/       # Navigation screens (8 screens)
│   ├── services/      # Business logic services
│   ├── store/         # MobX stores (10 stores)
│   ├── types/         # TypeScript definitions
│   └── utils/         # Utility functions
├── android/           # Android native code
├── ios/               # iOS native code
├── e2e/               # End-to-end tests (Appium)
├── __tests__/         # Root-level tests
├── __mocks__/         # Jest mocks
└── ai_docs/           # Implementation documentation
```

## Key Stores (MobX)

| Store | Purpose | Size |
|-------|---------|------|
| `ModelStore` | Model lifecycle, loading, offloading | 76KB |
| `ChatSessionStore` | Chat history, sessions, messages | 25KB |
| `PalStore` | AI personas management | 22KB |
| `HFStore` | HuggingFace integration | 11KB |
| `UIStore` | UI state (theme, navigation) | 3.5KB |
| `BenchmarkStore` | Performance metrics | 1.7KB |

## Key Screens

1. **ModelsScreen** - Model discovery and download
2. **ChatScreen** - Main chat interface
3. **SettingsScreen** - App settings
4. **PalsScreen** - AI persona management
5. **BenchmarkScreen** - Performance testing

## Testing

### Unit Tests
- Framework: Jest + @testing-library/react-native
- Coverage requirement: 60% minimum
- Run: `yarn test`

### E2E Tests
- Framework: Appium + WebDriverIO
- Platforms: iOS simulator, Android emulator, AWS Device Farm
- Run: See `/e2e/README.md`

## CI/CD

GitHub Actions workflows:
- `ci.yml` - Lint, typecheck, tests, build
- `e2e-tests.yml` - End-to-end testing
- `release.yml` - App store deployment

## Coding Standards

### Commits
Conventional commits: `feat|fix|docs|chore(scope): message`

### TypeScript
- Strict mode (with some relaxations)
- Experimental decorators enabled (for MobX)

### Linting
- ESLint with React Native config
- Prettier for formatting

## Key Dependencies

### State Management
```typescript
import {makeAutoObservable} from 'mobx';
import {observer} from 'mobx-react';
```

### Navigation
```typescript
import {useNavigation} from '@react-navigation/native';
import {DrawerNavigationProp} from '@react-navigation/drawer';
```

### UI
```typescript
import {Button, Card, Text} from 'react-native-paper';
import BottomSheet from '@gorhom/bottom-sheet';
```

## Current Priorities

From CLAUDE.md:
1. **P0**: Model loading stability
2. **P1**: TTS feature
3. Ecosystem integration (Palshub)

## Important Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | AI agent guidance, current priorities |
| `CONTRIBUTING.md` | Development workflow |
| `package.json` | Dependencies, scripts |
| `tsconfig.json` | TypeScript config |
| `.eslintrc.js` | Linting rules |
| `.prettierrc.js` | Formatting rules |
