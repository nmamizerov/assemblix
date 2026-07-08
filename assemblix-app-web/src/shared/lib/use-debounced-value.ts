import { useEffect, useState } from "react";

// Returns a copy of `value` that only updates after it has stayed unchanged for
// `delayMs`. Useful for debouncing search inputs before firing a query.
export const useDebouncedValue = <T>(value: T, delayMs = 300): T => {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
};
