import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Convert snake_case string to camelCase. E.g. "first_phrase" → "firstPhrase". */
export const snakeToCamel = (s: string): string =>
  s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
