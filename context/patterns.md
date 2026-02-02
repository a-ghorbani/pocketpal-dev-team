# PocketPal Coding Patterns

Reference patterns for consistent code across the codebase.

---

## Design Principles

Inspired by Don Norman (human-centered design) and Dieter Rams (less but better).

**When designing features, follow these principles:**

| Principle | Guideline | Example |
|-----------|-----------|---------|
| **Visibility** | Show system status clearly | Loading indicators, memory usage, model state |
| **Feedback** | Respond to actions immediately | Haptic on send, progress during download |
| **Simplicity** | Don't add options unless necessary | Sensible defaults over settings screens |
| **Error Prevention** | Validate before actions fail | Check memory before loading model |
| **Recovery** | Help users fix problems | Clear error messages with actionable steps |
| **Accessibility** | Works for everyone | Proper contrast, screen reader support, touch targets |

**Questions to ask before adding UI:**
- Can we use a sensible default instead of a setting?
- Is this visible enough without being intrusive?
- What happens when this fails? Is the error helpful?
- Would a non-technical user understand this?

---

## MobX Store Pattern

```typescript
// src/store/ExampleStore.ts
import {makeAutoObservable, runInAction} from 'mobx';

class ExampleStore {
  // Observable state
  items: Item[] = [];
  isLoading = false;
  error: string | null = null;

  constructor() {
    makeAutoObservable(this);
  }

  // Computed values
  get itemCount() {
    return this.items.length;
  }

  get hasError() {
    return this.error !== null;
  }

  // Actions
  setLoading(loading: boolean) {
    this.isLoading = loading;
  }

  // Async actions
  async fetchItems() {
    this.isLoading = true;
    this.error = null;

    try {
      const items = await api.getItems();
      runInAction(() => {
        this.items = items;
        this.isLoading = false;
      });
    } catch (e) {
      runInAction(() => {
        this.error = e.message;
        this.isLoading = false;
      });
    }
  }

  reset() {
    this.items = [];
    this.isLoading = false;
    this.error = null;
  }
}

export const exampleStore = new ExampleStore();
```

---

## Component Pattern

```typescript
// src/components/ExampleComponent/ExampleComponent.tsx
import React from 'react';
import {View, StyleSheet} from 'react-native';
import {Text, Button} from 'react-native-paper';
import {observer} from 'mobx-react';

import {useTheme} from '../../hooks';
import {exampleStore} from '../../store';

interface ExampleComponentProps {
  title: string;
  onPress?: () => void;
}

export const ExampleComponent: React.FC<ExampleComponentProps> = observer(
  ({title, onPress}) => {
    const theme = useTheme();

    const styles = StyleSheet.create({
      container: {
        padding: theme.spacing.md,
        backgroundColor: theme.colors.surface,
      },
      title: {
        color: theme.colors.onSurface,
      },
    });

    return (
      <View style={styles.container} testID="example-component">
        <Text style={styles.title}>{title}</Text>
        {exampleStore.isLoading ? (
          <Text>Loading...</Text>
        ) : (
          <Button onPress={onPress} testID="example-button">
            Action
          </Button>
        )}
      </View>
    );
  },
);
```

---

## Hook Pattern

```typescript
// src/hooks/useExample.ts
import {useState, useCallback, useEffect} from 'react';

interface UseExampleOptions {
  initialValue?: string;
  onSuccess?: (result: string) => void;
}

interface UseExampleReturn {
  value: string;
  isProcessing: boolean;
  error: string | null;
  process: (input: string) => Promise<void>;
  reset: () => void;
}

export const useExample = (options: UseExampleOptions = {}): UseExampleReturn => {
  const {initialValue = '', onSuccess} = options;

  const [value, setValue] = useState(initialValue);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const process = useCallback(async (input: string) => {
    setIsProcessing(true);
    setError(null);

    try {
      const result = await someAsyncOperation(input);
      setValue(result);
      onSuccess?.(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsProcessing(false);
    }
  }, [onSuccess]);

  const reset = useCallback(() => {
    setValue(initialValue);
    setError(null);
    setIsProcessing(false);
  }, [initialValue]);

  return {value, isProcessing, error, process, reset};
};
```

---

## Testing Infrastructure

PocketPal uses a **centralized mocking system**. Understanding this is critical for writing tests.

### Key Files

| File | Purpose |
|------|---------|
| `jest.config.js` | Jest configuration, module name mappings |
| `jest/setup.ts` | Global mocks applied to ALL tests |
| `jest/setupFilesAfterEnv.ts` | Test lifecycle hooks (afterEach cleanup) |
| `jest/test-utils.tsx` | Custom render function with providers |
| `jest/fixtures.ts` | Shared test data (messages, users, etc.) |
| `jest/fixtures/` | Domain-specific fixtures (models, pals, themes) |
| `__mocks__/stores/` | Mock store implementations |
| `__mocks__/external/` | Mocks for external packages (llama.rn, etc.) |
| `__mocks__/services/` | Mock service implementations |

### How Store Mocking Works

**DO NOT mock stores inline in tests.** The stores are globally mocked in `jest/setup.ts`:

```typescript
// jest/setup.ts (simplified)
import {mockUiStore} from '../__mocks__/stores/uiStore';
import {mockModelStore} from '../__mocks__/stores/modelStore';
import {mockChatSessionStore} from '../__mocks__/stores/chatSessionStore';
// ... other mock imports

jest.mock('../src/store', () => ({
  modelStore: mockModelStore,
  uiStore: mockUiStore,
  chatSessionStore: mockChatSessionStore,
  // ... all stores
}));
```

### Mock Store Structure

Mock stores in `__mocks__/stores/` follow this pattern:

```typescript
// __mocks__/stores/modelStore.ts
import {makeAutoObservable} from 'mobx';
import {modelsList} from '../../jest/fixtures/models';

class MockModelStore {
  // Observable state with fixture data
  models = modelsList;
  activeModelId: string | undefined;
  isContextLoading = false;

  // Jest mock functions for methods
  initContext: jest.Mock;
  deleteModel: jest.Mock;
  // ... other methods

  constructor() {
    makeAutoObservable(this, {
      // Exclude mock functions from observability
      initContext: false,
      deleteModel: false,
    });

    // Initialize mock functions
    this.initContext = jest.fn().mockResolvedValue(Promise.resolve());
    this.deleteModel = jest.fn().mockResolvedValue(Promise.resolve());
  }

  // Real actions that modify state
  setActiveModel = (modelId: string) => {
    this.activeModelId = modelId;
  };

  // Computed values
  get activeModel() {
    return this.models.find(model => model.id === this.activeModelId);
  }
}

export const mockModelStore = new MockModelStore();
```

### Writing Component Tests

```typescript
// src/components/MyComponent/__tests__/MyComponent.test.tsx
import React from 'react';
import {runInAction} from 'mobx';

// Use custom render from test-utils (includes providers)
import {fireEvent, render} from '../../../../jest/test-utils';

// Import fixtures
import {textMessage, user} from '../../../../jest/fixtures';

// Import stores - these are already mocked globally
import {modelStore, chatSessionStore} from '../../../store';

import {MyComponent} from '../MyComponent';

// Use fake timers if component uses timers/animations
jest.useFakeTimers();

// Mock child components if needed (inline mocks are OK for components)
jest.mock('../../ChildComponent', () => ({
  ChildComponent: jest.fn(() => null),
}));

describe('MyComponent', () => {
  beforeEach(() => {
    // Reset mock function calls between tests
    jest.clearAllMocks();
  });

  it('renders correctly', () => {
    const {getByTestId} = render(
      <MyComponent />,
      {withNavigation: true, withBottomSheetProvider: true}
    );
    expect(getByTestId('my-component')).toBeTruthy();
  });

  it('responds to store state changes', () => {
    // Modify mock store state using runInAction
    runInAction(() => {
      modelStore.activeModelId = 'test-model-id';
    });

    const {getByText} = render(
      <MyComponent />,
      {withNavigation: true}
    );

    expect(getByText('Model Selected')).toBeTruthy();
  });

  it('calls store methods on user interaction', () => {
    const {getByTestId} = render(
      <MyComponent />,
      {withNavigation: true}
    );

    fireEvent.press(getByTestId('action-button'));

    expect(modelStore.initContext).toHaveBeenCalled();
  });
});
```

### Custom Render Options

The `render` function from `jest/test-utils.tsx` accepts options:

```typescript
render(<Component />, {
  theme: customTheme,              // Custom theme (default: lightTheme)
  user: customUser,                // User context (default: userFixture)
  withNavigation: true,            // Wrap in NavigationContainer
  withSafeArea: true,              // Wrap in SafeAreaProvider
  withBottomSheetProvider: true,   // Wrap in BottomSheetModalProvider
});
```

### Modifying Mock Store State in Tests

**Use `runInAction` from MobX** to modify mock store state:

```typescript
import {runInAction} from 'mobx';
import {modelStore} from '../../../store';

it('shows loading state', () => {
  runInAction(() => {
    modelStore.isContextLoading = true;
  });

  const {getByText} = render(<MyComponent />);
  expect(getByText('Loading...')).toBeTruthy();
});
```

### Testing Async Store Methods

Mock store methods return jest.fn() - set up return values as needed:

```typescript
it('handles model initialization', async () => {
  // Mock method is already set up with mockResolvedValue
  // To customize return value:
  modelStore.initContext.mockResolvedValueOnce({success: true});

  const {getByTestId} = render(<MyComponent />);
  fireEvent.press(getByTestId('init-button'));

  await waitFor(() => {
    expect(modelStore.initContext).toHaveBeenCalledWith(
      expect.objectContaining({modelId: 'test-id'})
    );
  });
});
```

### Using Fixtures

```typescript
// Import from jest/fixtures.ts (main fixtures)
import {
  textMessage,
  imageMessage,
  fileMessage,
  user,
} from '../../../../jest/fixtures';

// Import from jest/fixtures/ subfolder (domain fixtures)
import {modelsList} from '../../../../jest/fixtures/models';
import {palFixtures} from '../../../../jest/fixtures/pals';
import {themeFixtures} from '../../../../jest/fixtures/theme';
```

### Module Name Mapper (External Mocks)

External packages are mocked via `moduleNameMapper` in `jest.config.js`:

```javascript
moduleNameMapper: {
  'llama.rn': '<rootDir>/__mocks__/external/llama.rn.ts',
  '@nozbe/watermelondb': '<rootDir>/__mocks__/external/@nozbe/watermelondb.js',
  // ... etc
}
```

**DO NOT** try to mock these packages inline - they're handled globally.

---

## Test Pattern (Store Unit Tests)

For testing store logic directly (not through components):

```typescript
// src/store/__tests__/ExampleStore.test.ts
import {ExampleStore} from '../ExampleStore';

// Mock external dependencies this store uses
jest.mock('../../api', () => ({
  getItems: jest.fn(),
}));

import {getItems} from '../../api';

describe('ExampleStore', () => {
  let store: ExampleStore;

  beforeEach(() => {
    // Create fresh store instance for each test
    store = new ExampleStore();
    jest.clearAllMocks();
  });

  describe('initial state', () => {
    it('should have empty items', () => {
      expect(store.items).toEqual([]);
    });

    it('should not be loading', () => {
      expect(store.isLoading).toBe(false);
    });
  });

  describe('computed values', () => {
    it('should compute item count', () => {
      store.items = [{id: '1'}, {id: '2'}];
      expect(store.itemCount).toBe(2);
    });
  });

  describe('fetchItems', () => {
    it('should fetch and set items', async () => {
      const mockItems = [{id: '1', name: 'Item 1'}];
      (getItems as jest.Mock).mockResolvedValue(mockItems);

      await store.fetchItems();

      expect(store.items).toEqual(mockItems);
      expect(store.isLoading).toBe(false);
    });

    it('should handle errors', async () => {
      (getItems as jest.Mock).mockRejectedValue(new Error('API Error'));

      await store.fetchItems();

      expect(store.error).toBe('API Error');
      expect(store.isLoading).toBe(false);
    });
  });
});
```

---

## Common Testing Mistakes to Avoid

### 1. Inline Store Mocking

```typescript
// WRONG - stores are globally mocked
jest.mock('../../store', () => ({
  modelStore: { isLoading: false }
}));

// RIGHT - import and modify the global mock
import {modelStore} from '../../store';
runInAction(() => { modelStore.isLoading = true; });
```

### 2. Missing Provider Wrappers

```typescript
// WRONG - component needs providers
render(<ChatView messages={[]} />);

// RIGHT - use test-utils render with options
render(<ChatView messages={[]} />, {
  withNavigation: true,
  withBottomSheetProvider: true
});
```

### 3. Forgetting jest.clearAllMocks()

```typescript
// WRONG - mock calls accumulate across tests
describe('MyComponent', () => {
  it('first test', () => { /* calls mock */ });
  it('second test', () => { /* mock has calls from first test */ });
});

// RIGHT - clear in beforeEach
describe('MyComponent', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });
  // tests...
});
```

### 4. Not Using runInAction for State Changes

```typescript
// WRONG - may not trigger MobX reactions
modelStore.activeModelId = 'test-id';

// RIGHT - ensures MobX reactions fire
runInAction(() => {
  modelStore.activeModelId = 'test-id';
});
```

---

## API Integration Pattern

```typescript
// src/api/example.ts
import {API_BASE_URL} from '../config';

interface ExampleResponse {
  data: Item[];
  total: number;
}

export const fetchExamples = async (params: {
  page: number;
  limit: number;
}): Promise<ExampleResponse> => {
  const {page, limit} = params;

  const response = await fetch(
    `${API_BASE_URL}/examples?page=${page}&limit=${limit}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    },
  );

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }

  return response.json();
};
```

---

## Navigation Pattern

```typescript
// Using navigation in a component
import {useNavigation} from '@react-navigation/native';
import {DrawerNavigationProp} from '@react-navigation/drawer';
import {RootDrawerParamList} from '../types/navigation';

type NavigationProp = DrawerNavigationProp<RootDrawerParamList>;

export const MyComponent = () => {
  const navigation = useNavigation<NavigationProp>();

  const handleNavigate = () => {
    navigation.navigate('ScreenName', {param: 'value'});
  };

  return <Button onPress={handleNavigate}>Go</Button>;
};
```

---

## File Organization

```
src/components/
  ExampleComponent/
    ExampleComponent.tsx       # Main component
    __tests__/
      ExampleComponent.test.tsx  # Tests in __tests__ folder
    index.ts                   # Re-export

src/store/
  ExampleStore.ts              # Store class
  __tests__/
    ExampleStore.test.ts       # Store tests

src/hooks/
  useExample.ts                # Hook
  index.ts                     # Re-exports all hooks

jest/
  setup.ts                     # Global test setup & mocks
  setupFilesAfterEnv.ts        # Lifecycle hooks
  test-utils.tsx               # Custom render with providers
  fixtures.ts                  # Shared test data
  fixtures/                    # Domain-specific fixtures
    models.ts
    pals.ts
    theme.ts

__mocks__/
  stores/                      # Mock store implementations
    modelStore.ts
    chatSessionStore.ts
    uiStore.ts
  external/                    # External package mocks
    llama.rn.ts
    @nozbe/watermelondb.js
  services/                    # Mock services
    downloads.ts
```
