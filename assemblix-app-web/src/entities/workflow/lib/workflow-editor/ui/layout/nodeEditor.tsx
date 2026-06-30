import { useState, useCallback, useMemo } from "react";
import { Panel, useOnSelectionChange } from "@xyflow/react";
import type { Node } from "@xyflow/react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import type { Workflow } from "@/entities/workflow/model/types";
import { useGetNodesQuery } from "@/entities/workflow";
import { selectCurrentProjectId } from "@/entities/organization";
import { customWidgets } from "../node-forms/generic/custom-widgets";
import { GenericNodeForm } from "../node-forms/generic/generic-node-form";
import type { NodeDescriptor } from "@/entities/workflow/model/types";

interface WorkflowEditorNodeEditorProps {
  workflow: Workflow;
}

export const WorkflowEditorNodeEditor = ({
  workflow,
}: WorkflowEditorNodeEditorProps) => {
  const [selectedNodes, setSelectedNodes] = useState<Node[]>([]);
  const { t } = useTranslation();
  const currentProjectId = useSelector(selectCurrentProjectId);

  // Fetch node descriptors for descriptor-driven forms
  const { data: descriptors, isLoading: descriptorsLoading } = useGetNodesQuery();

  // Build a type → descriptor lookup for O(1) access
  const descriptorsByType = useMemo<Record<string, NodeDescriptor>>(() => {
    if (!descriptors) return {};
    return Object.fromEntries(descriptors.map((d) => [d.type, d]));
  }, [descriptors]);

  const onChange = useCallback(({ nodes }: { nodes: Node[] }) => {
    setSelectedNodes(nodes);
  }, []);

  useOnSelectionChange({ onChange });

  if (selectedNodes.length === 0 || selectedNodes.length > 1) {
    return null;
  }

  const selectedNode = selectedNodes[0];

  const renderForm = () => {
    const nodeType = selectedNode.type ?? "";
    const config = selectedNode.data as Record<string, unknown>;

    // 1. Check custom-widget registry first
    const CustomWidget = customWidgets[nodeType];
    if (CustomWidget) {
      return (
        <CustomWidget
          key={selectedNode.id}
          nodeId={selectedNode.id}
          config={config}
          workflow={workflow}
          projectId={currentProjectId || undefined}
        />
      );
    }

    // 2. Fall through to GenericNodeForm driven by descriptor
    const descriptor = descriptorsByType[nodeType];

    if (descriptorsLoading) {
      return (
        <div className="p-4">
          <p className="text-xs text-muted-foreground">
            {t("workflow.editor.loadingNodeTypes")}
          </p>
        </div>
      );
    }

    if (!descriptor) {
      return (
        <div className="p-4">
          <h3 className="text-sm font-semibold mb-2">
            {t("workflow.editor.nodeEditor")}
          </h3>
          <p className="text-xs text-muted-foreground">
            {t("workflow.editor.unknownNodeType")}: {nodeType}
          </p>
          <div className="mt-4">
            <p className="text-xs text-muted-foreground">
              {t("workflow.editor.data")}:
            </p>
            <pre className="text-xs bg-background p-2 rounded overflow-auto max-h-40">
              {JSON.stringify(selectedNode.data, null, 2)}
            </pre>
          </div>
        </div>
      );
    }

    return (
      <GenericNodeForm
        key={selectedNode.id}
        nodeId={selectedNode.id}
        descriptor={descriptor}
        config={config}
        projectId={currentProjectId || undefined}
      />
    );
  };

  return (
    <Panel
      position="top-right"
      className="m-4 mt-20! w-80 bg-panel rounded-xl overflow-hidden flex flex-col max-h-[calc(100vh-6rem)]"
    >
      <motion.div
        layout
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 20 }}
        transition={{
          duration: 0.15,
          ease: "easeInOut",
          layout: { duration: 0.15, ease: "easeInOut" },
        }}
        className="flex-1 min-h-0 flex flex-col"
      >
        {renderForm()}
      </motion.div>
    </Panel>
  );
};
