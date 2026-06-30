import { useEffect, useState } from "react";
import { StateEditor } from "../debug/state-editor";
import type { StateVariable } from "@/entities/workflow/model/types";
import type { StateSchemaVariable } from "@/entities/project/model/types";
import { cn } from "@/shared/lib/utils";

interface StateVariableRowProps {
  variable: StateVariable | StateSchemaVariable;
  value: unknown;
  onChange: (value: unknown) => void;
  readOnly?: boolean;
  /**
   * Триггер flash-анимации. Передавать `lastUpdateTimestamp` из Redux,
   * только если этот ключ есть в recentlyChangedKeys и идёт выполнение.
   * 0 = не подсвечивать.
   */
  flashTrigger?: number;
}

const TYPE_BADGE_COLOR: Record<string, string> = {
  string: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  number: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  boolean: "bg-purple-500/15 text-purple-700 dark:text-purple-300",
  object: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
};

export const StateVariableRow = ({
  variable,
  value,
  onChange,
  readOnly = false,
  flashTrigger = 0,
}: StateVariableRowProps) => {
  const [isFlashing, setIsFlashing] = useState(false);

  useEffect(() => {
    if (!flashTrigger) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- driving CSS animation requires state + timer
    setIsFlashing(true);
    const timer = setTimeout(() => setIsFlashing(false), 1500);
    return () => clearTimeout(timer);
  }, [flashTrigger]);

  const typeBadgeClass =
    TYPE_BADGE_COLOR[variable.type] || "bg-muted text-muted-foreground";

  return (
    <div
      className={cn(
        "rounded-md p-2 transition-colors",
        isFlashing && "animate-state-flash",
      )}
    >
      <div className="flex items-center justify-between mb-1.5 gap-2">
        <span className="text-xs font-medium truncate text-foreground">
          {variable.name}
        </span>
        <span
          className={cn(
            "text-[10px] font-mono uppercase px-1.5 py-0.5 rounded shrink-0",
            typeBadgeClass,
          )}
        >
          {variable.type}
        </span>
      </div>
      <StateEditor
        variable={variable}
        value={value}
        onChange={onChange}
        readOnly={readOnly}
        showLabel={false}
      />
    </div>
  );
};
