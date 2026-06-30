import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { Panel } from "@xyflow/react";
import { motion } from "framer-motion";
import { Database, Lock } from "lucide-react";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { useAppDispatch, type RootState } from "@/app/store";
import { selectIsExecuting } from "../../model/editor-mode.slice";
import {
  selectAgentState,
  selectProjectState,
  selectLastUpdateTimestamp,
  selectRecentlyChangedAgentKeys,
  selectRecentlyChangedProjectKeys,
  setAgentValue,
  setProjectValue,
} from "../../model/workflow-runtime-state.slice";
import { selectVariablesByWorkflowId } from "@/entities/workflow/model/variables.slice";
import { selectCurrentProjectId } from "@/entities/organization";
import { useGetProjectQuery } from "@/entities/project";
import type { Workflow } from "@/entities/workflow/model/types";
import { StateVariableRow } from "./state-variable-row";

interface StateManagementSidebarProps {
  workflow: Workflow;
}

export const StateManagementSidebar = ({
  workflow,
}: StateManagementSidebarProps) => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const isExecuting = useSelector(selectIsExecuting);
  const agentState = useSelector(selectAgentState);
  const projectState = useSelector(selectProjectState);
  const lastUpdateTimestamp = useSelector(selectLastUpdateTimestamp);
  const recentlyChangedAgentKeys = useSelector(selectRecentlyChangedAgentKeys);
  const recentlyChangedProjectKeys = useSelector(
    selectRecentlyChangedProjectKeys,
  );
  const currentProjectId = useSelector(selectCurrentProjectId);

  const agentChangedSet = useMemo(
    () => new Set(recentlyChangedAgentKeys),
    [recentlyChangedAgentKeys],
  );
  const projectChangedSet = useMemo(
    () => new Set(recentlyChangedProjectKeys),
    [recentlyChangedProjectKeys],
  );

  const { data: project } = useGetProjectQuery(currentProjectId!, {
    skip: !currentProjectId,
  });

  const agentVariables = useSelector((state: RootState) =>
    selectVariablesByWorkflowId(state, workflow.id),
  );

  const projectVariables = useMemo(
    () => project?.stateSchema || [],
    [project],
  );

  const hasAgentVariables = agentVariables.length > 0;
  const hasProjectVariables = projectVariables.length > 0;
  const hasAnyVariables = hasAgentVariables || hasProjectVariables;

  const handleAgentChange = (key: string, value: unknown) => {
    dispatch(setAgentValue({ key, value }));
  };

  const handleProjectChange = (key: string, value: unknown) => {
    dispatch(setProjectValue({ key, value }));
  };

  return (
    <Panel
      position="top-left"
      className="m-4 mt-20! w-80 bg-panel rounded-xl overflow-hidden flex flex-col max-h-[calc(100%-2rem)]"
    >
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        transition={{ duration: 0.2, ease: "easeInOut" }}
        className="flex flex-col flex-1 min-h-0"
      >
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Database className="size-4 text-primary shrink-0" />
            <h3 className="text-sm font-semibold truncate">
              {t("workflow.stateSidebar.title")}
            </h3>
          </div>
          {isExecuting && (
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="relative flex size-2">
                <span className="absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-75 animate-ping" />
                <span className="relative inline-flex rounded-full size-2 bg-green-500" />
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-green-600 dark:text-green-400">
                {t("workflow.stateSidebar.live")}
              </span>
            </div>
          )}
        </div>

        {/* Read-only hint */}
        {isExecuting && hasAnyVariables && (
          <div className="px-4 py-2 bg-muted/30 border-b border-border flex items-center gap-2 text-[11px] text-muted-foreground">
            <Lock className="size-3 shrink-0" />
            <span>{t("workflow.stateSidebar.readOnlyHint")}</span>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 min-h-0 max-h-[60vh] overflow-auto">
          <ScrollArea className="h-full">
            <div className="p-3 space-y-4">
              {!hasAnyVariables && (
                <div className="text-center py-12 text-muted-foreground text-xs">
                  {t("workflow.stateSidebar.noVariables")}
                </div>
              )}

              {hasAgentVariables && (
                <section className="space-y-2">
                  <div className="flex items-center gap-2 px-1">
                    <div className="w-1 h-3 bg-primary rounded-full" />
                    <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {t("workflow.stateSidebar.agentState")}
                    </h4>
                  </div>
                  <div className="space-y-1.5">
                    {agentVariables.map((variable) => (
                      <StateVariableRow
                        key={variable.name}
                        variable={variable}
                        value={agentState[variable.name]}
                        onChange={(value) =>
                          handleAgentChange(variable.name, value)
                        }
                        readOnly={isExecuting}
                        flashTrigger={
                          isExecuting && agentChangedSet.has(variable.name)
                            ? lastUpdateTimestamp
                            : 0
                        }
                      />
                    ))}
                  </div>
                </section>
              )}

              {hasProjectVariables && (
                <section className="space-y-2">
                  <div className="flex items-center gap-2 px-1">
                    <div className="w-1 h-3 bg-blue-500 rounded-full" />
                    <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {t("workflow.stateSidebar.projectState")}
                    </h4>
                  </div>
                  <div className="space-y-1.5">
                    {projectVariables.map((variable) => (
                      <StateVariableRow
                        key={variable.name}
                        variable={variable}
                        value={projectState[variable.name]}
                        onChange={(value) =>
                          handleProjectChange(variable.name, value)
                        }
                        readOnly={isExecuting}
                        flashTrigger={
                          isExecuting && projectChangedSet.has(variable.name)
                            ? lastUpdateTimestamp
                            : 0
                        }
                      />
                    ))}
                  </div>
                </section>
              )}
            </div>
          </ScrollArea>
        </div>
      </motion.div>
    </Panel>
  );
};
