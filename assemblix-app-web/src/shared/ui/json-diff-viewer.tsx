import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Plus, Minus, Pencil, ArrowRight } from "lucide-react";
import { cn } from "@/shared/lib/utils";

interface JsonDiffViewerProps {
  before: unknown;
  after: unknown;
  className?: string;
}

type ChangeKind = "added" | "removed" | "changed";

interface DiffEntry {
  path: string;
  kind: ChangeKind;
  before?: string;
  after?: string;
}

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

// Flatten an arbitrary JSON value into a map of leaf-path → compact JSON string.
// Arrays use bracket notation (a[0]), nested objects use dot notation (a.b.c).
const flatten = (
  value: unknown,
  prefix = "",
  acc: Map<string, string> = new Map(),
): Map<string, string> => {
  if (isPlainObject(value)) {
    const keys = Object.keys(value);
    if (keys.length === 0 && prefix) {
      acc.set(prefix, "{}");
      return acc;
    }
    for (const key of keys) {
      const path = prefix ? `${prefix}.${key}` : key;
      flatten(value[key], path, acc);
    }
    return acc;
  }

  if (Array.isArray(value)) {
    if (value.length === 0 && prefix) {
      acc.set(prefix, "[]");
      return acc;
    }
    value.forEach((item, index) => {
      flatten(item, `${prefix}[${index}]`, acc);
    });
    return acc;
  }

  acc.set(prefix, JSON.stringify(value));
  return acc;
};

const computeDiff = (before: unknown, after: unknown): DiffEntry[] => {
  const beforeMap = flatten(before);
  const afterMap = flatten(after);
  const entries: DiffEntry[] = [];

  for (const [path, beforeValue] of beforeMap) {
    if (!afterMap.has(path)) {
      entries.push({ path, kind: "removed", before: beforeValue });
    } else if (afterMap.get(path) !== beforeValue) {
      entries.push({
        path,
        kind: "changed",
        before: beforeValue,
        after: afterMap.get(path),
      });
    }
  }

  for (const [path, afterValue] of afterMap) {
    if (!beforeMap.has(path)) {
      entries.push({ path, kind: "added", after: afterValue });
    }
  }

  return entries.sort((a, b) => a.path.localeCompare(b.path));
};

const KIND_STYLES: Record<
  ChangeKind,
  { row: string; icon: typeof Plus; iconColor: string }
> = {
  added: {
    row: "border-green-200 dark:border-green-900 bg-green-50 dark:bg-green-950/30",
    icon: Plus,
    iconColor: "text-green-600 dark:text-green-400",
  },
  removed: {
    row: "border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30",
    icon: Minus,
    iconColor: "text-red-600 dark:text-red-400",
  },
  changed: {
    row: "border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/30",
    icon: Pencil,
    iconColor: "text-amber-600 dark:text-amber-400",
  },
};

export const JsonDiffViewer = ({
  before,
  after,
  className,
}: JsonDiffViewerProps) => {
  const { t } = useTranslation();
  const entries = useMemo(() => computeDiff(before, after), [before, after]);

  if (entries.length === 0) {
    return (
      <div
        className={cn(
          "rounded-md border border-border bg-muted/30 px-3 py-4 text-center text-sm text-muted-foreground",
          className,
        )}
      >
        {t("executionViewer.noChanges")}
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {entries.map((entry) => {
        const style = KIND_STYLES[entry.kind];
        const Icon = style.icon;
        return (
          <div
            key={`${entry.kind}:${entry.path}`}
            className={cn("rounded-md border p-2.5", style.row)}
          >
            <div className="flex items-center gap-2">
              <Icon className={cn("h-3.5 w-3.5 shrink-0", style.iconColor)} />
              <code className="break-all text-xs font-medium text-foreground">
                {entry.path}
              </code>
            </div>
            <div className="mt-1.5 pl-[22px] text-xs">
              {entry.kind === "changed" ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <code className="break-all rounded bg-background px-1.5 py-0.5 text-red-600 line-through dark:text-red-400">
                    {entry.before}
                  </code>
                  <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                  <code className="break-all rounded bg-background px-1.5 py-0.5 text-green-600 dark:text-green-400">
                    {entry.after}
                  </code>
                </div>
              ) : (
                <code className="break-all rounded bg-background px-1.5 py-0.5 text-muted-foreground">
                  {entry.kind === "added" ? entry.after : entry.before}
                </code>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
