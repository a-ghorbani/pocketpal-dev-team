# PocketPal Coding Patterns

Reference patterns for consistent code across the codebase.

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

## Test Pattern (Component)

```typescript
// src/components/ExampleComponent/ExampleComponent.test.tsx
import React from 'react';
import {render, fireEvent, waitFor} from '@testing-library/react-native';
import {ExampleComponent} from './ExampleComponent';
import {exampleStore} from '../../store';

// Mock the store
jest.mock('../../store', () => ({
  exampleStore: {
    isLoading: false,
    items: [],
    fetchItems: jest.fn(),
  },
}));

describe('ExampleComponent', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders correctly with title', () => {
    const {getByText} = render(<ExampleComponent title="Test Title" />);
    expect(getByText('Test Title')).toBeTruthy();
  });

  it('calls onPress when button is pressed', () => {
    const onPress = jest.fn();
    const {getByTestId} = render(
      <ExampleComponent title="Test" onPress={onPress} />,
    );

    fireEvent.press(getByTestId('example-button'));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('shows loading state', () => {
    (exampleStore as any).isLoading = true;
    const {getByText} = render(<ExampleComponent title="Test" />);
    expect(getByText('Loading...')).toBeTruthy();
  });
});
```

## Test Pattern (Store)

```typescript
// src/store/__tests__/ExampleStore.test.ts
import {ExampleStore} from '../ExampleStore';

// Mock external dependencies
jest.mock('../../api', () => ({
  getItems: jest.fn(),
}));

import {getItems} from '../../api';

describe('ExampleStore', () => {
  let store: ExampleStore;

  beforeEach(() => {
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

## Error Handling Pattern

```typescript
// Consistent error handling
try {
  const result = await riskyOperation();
  return result;
} catch (error) {
  // Log error with context
  console.error('[ModuleName] Operation failed:', error);

  // User-friendly error message
  if (error instanceof NetworkError) {
    throw new Error('Unable to connect. Please check your connection.');
  }

  if (error instanceof ValidationError) {
    throw new Error(`Invalid input: ${error.message}`);
  }

  // Generic fallback
  throw new Error('An unexpected error occurred. Please try again.');
}
```

## File Organization

```
src/components/
  ExampleComponent/
    ExampleComponent.tsx      # Main component
    ExampleComponent.test.tsx # Tests
    index.ts                  # Re-export

src/store/
  ExampleStore.ts             # Store class
  __tests__/
    ExampleStore.test.ts      # Store tests

src/hooks/
  useExample.ts               # Hook
  useExample.test.ts          # Hook tests (co-located)
  index.ts                    # Re-exports all hooks
```
