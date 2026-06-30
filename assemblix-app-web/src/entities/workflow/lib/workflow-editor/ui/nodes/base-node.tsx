import { Handle, Position } from "@xyflow/react";
import { cn } from "@/shared/lib/utils";
import type { ReactNode } from "react";
import { useHandleConnectivity } from "./useHandleConnectivity";
import { generateHandleId } from "../../helpers/utils";
import { AlertTriangle } from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/ui/tooltip";

export interface BaseNodeProps {
  nodeId: string;
  label: string;
  sublabel?: string;
  icon?: ReactNode;
  color: string;
  selected?: boolean;
  handles?: {
    type: "source" | "target";
    position: Position;
    index?: number;
    id?: string;
    style?: React.CSSProperties;
  }[];
  children?: ReactNode;
  warning?: {
    message: string;
  };
}

interface HandleWithConnectivityProps {
  nodeId: string;
  handle: {
    type: "source" | "target";
    position: Position;
    index?: number;
    id?: string;
    style?: React.CSSProperties;
  };
  id: string;
}

const HandleWithConnectivity = ({
  nodeId,
  handle,
  id,
}: HandleWithConnectivityProps) => {
  // Всегда вызываем хук (правило React Hooks), но используем результат только для source handles
  const isSourceConnectable = useHandleConnectivity(nodeId, handle.id);
  const isConnectable = handle.type === "source" ? isSourceConnectable : true;

  return (
    <Handle
      key={id}
      type={handle.type}
      position={handle.position}
      id={id}
      style={handle.style}
      isConnectable={true}
      className={cn(
        "w-2! h-2! border bg-background hover:-translate-x-1   transition-all hover:scale-200 hover:translate-y-1",
        handle.type === "source"
          ? isConnectable
            ? "border-muted-foreground hover:border-primary  "
            : "border-muted-foreground/50 cursor-not-allowed"
          : "border-muted-foreground hover:border-primary  hover:translate-x-1"
      )}
    />
  );
};

export const BaseNode = ({
  nodeId,
  label,
  sublabel,
  icon,
  color,
  selected,
  handles = [],
  children,
  warning,
}: BaseNodeProps) => {
  return (
    <div
      className={cn(
        "rounded-2xl border  bg-card transition-all p-3 px-5 relative",
        warning
          ? "border-yellow-500"
          : selected
          ? "border border-primary"
          : "border-border hover:border-primary/50"
      )}
    >
      {warning && (
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="absolute -right-1 -top-1 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-yellow-500 text-white shadow-md">
              <AlertTriangle className="h-3 w-3" />
            </div>
          </TooltipTrigger>
          <TooltipContent side="top">
            <p>{warning.message}</p>
          </TooltipContent>
        </Tooltip>
      )}

      <div className="flex items-center gap-4 bg-muted/20 ">
        {icon && (
          <div
            className={cn(
              "p-2 text-white rounded-md",
              `bg-${color} opacity-70`
            )}
          >
            {icon}
          </div>
        )}
        <div className="flex flex-col">
          <span className="text-sm font-semibold">{label}</span>
          {sublabel && (
            <span className="text-xs font-semibold text-muted-foreground">
              {sublabel}
            </span>
          )}
        </div>
      </div>

      {children && <div>{children}</div>}

      {handles.map((handle) => (
        <HandleWithConnectivity
          key={generateHandleId(handle.type, nodeId, handle.index || 0)}
          id={generateHandleId(handle.type, nodeId, handle.index || 0)}
          nodeId={nodeId}
          handle={handle}
        />
      ))}
    </div>
  );
};
