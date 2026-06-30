import { Panel } from "@xyflow/react";
import { Undo2, Redo2 } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { motion } from "framer-motion";

interface UndoRedoPanelProps {
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
}

export const UndoRedoPanel = ({
  onUndo,
  onRedo,
  canUndo,
  canRedo,
}: UndoRedoPanelProps) => {
  return (
    <Panel position="bottom-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 20 }}
        className="flex items-center gap-2 bg-background border border-border rounded-lg shadow-lg p-1"
      >
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onUndo}
          disabled={!canUndo}
          title="Отменить (Ctrl+Z)"
        >
          <Undo2 className="size-4" />
        </Button>
        <div className="w-px h-5 bg-border" />
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onRedo}
          disabled={!canRedo}
          title="Повторить (Ctrl+Shift+Z)"
        >
          <Redo2 className="size-4" />
        </Button>
      </motion.div>
    </Panel>
  );
};
