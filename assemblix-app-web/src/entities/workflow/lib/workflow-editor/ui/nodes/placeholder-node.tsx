import { Handle, Position } from "@xyflow/react";
import { useTranslation } from "react-i18next";
import { Plus } from "lucide-react";

export const PlaceholderNode = () => {
  const { t } = useTranslation();

  return (
    <div
      className="rounded-2xl border-2 border-dashed border-primary/50 bg-card/50 backdrop-blur-sm transition-all p-3 px-5 opacity-100 hover:opacity-100 animate-pulse"
      style={{
        minWidth: "200px",
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="w-2! h-2! border bg-background border-primary/50"
      />

      <div className="flex items-center gap-4">
        <div className="p-2 text-primary rounded-md bg-primary/20">
          <Plus size={20} />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-primary">
            {t("nodes.placeholder.newElement")}
          </span>
          <span className="text-xs text-muted-foreground">
            {t("nodes.placeholder.selectTypeInSidebar")}
          </span>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="w-2! h-2! border bg-background border-primary/50"
      />
    </div>
  );
};
