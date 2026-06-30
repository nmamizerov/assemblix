import { useAppDispatch } from "@/app/store";
import { NodeType, type Workflow } from "@/entities/workflow/model/types";
import { Button } from "@/shared/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip";
import { Panel, useNodes } from "@xyflow/react";
import {
  ChevronLeft,
  Pencil,
  Play,
  Loader2,
  History,
  FileText,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import {
  selectEditorMode,
  setEditorMode,
  resetExecution,
} from "../../model/editor-mode.slice";
import { cn } from "@/shared/lib/utils";
import { WorkflowActions } from "@/entities/workflow/ui/actions";
import { usePublishWorkflowMutation } from "@/entities/workflow";
import { PublishSuccessDialog } from "@/entities/workflow/ui/actions/publish-success-dialog";
import { VersionsDropdown } from "@/entities/workflow/ui/versions-dropdown";
import { AgentCallsDialog } from "@/entities/workflow/ui/agent-calls-dialog";
import { BulkInstructionsDialog } from "@/entities/workflow/ui/bulk-instructions-dialog";
import { useState } from "react";
import { toast } from "sonner";

interface WorkflowEditorHeaderProps {
  workflow: Workflow;
  onRefetch?: () => void;
  onLoadVersion?: (versionId: string) => void;
  isDraft?: boolean;
}

export const WorkflowEditorHeader = ({
  workflow,
  onRefetch,
  onLoadVersion,
  isDraft = true,
}: WorkflowEditorHeaderProps) => {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const dispatch = useAppDispatch();
  const { t } = useTranslation();
  const mode = useSelector(selectEditorMode);
  const [publishWorkflow, { isLoading: isPublishing }] =
    usePublishWorkflowMutation();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [publishedVersion, setPublishedVersion] = useState<number>(1);
  const [isAgentCallsOpen, setIsAgentCallsOpen] = useState(false);
  const [isBulkInstructionsOpen, setIsBulkInstructionsOpen] = useState(false);

  const nodes = useNodes();
  const hasAgents = nodes.some((node) => node.type === NodeType.AGENT);

  const handleNavigateBack = () => {
    navigate(`/projects/${projectId}/workflows`);
  };

  const handleModeChange = (newMode: "EDIT" | "DEBUG") => {
    if (newMode !== mode) {
      dispatch(setEditorMode(newMode));
      if (newMode === "EDIT") {
        dispatch(resetExecution());
      }
    }
  };

  const handlePublish = async () => {
    try {
      const result = await publishWorkflow(workflow.id).unwrap();
      setPublishedVersion(result.version || 1);
      setIsDialogOpen(true);
      if (onRefetch) {
        onRefetch();
      }
    } catch (error) {
      console.error(error);
      toast.error(t("errors.generic"), {
        description: t("workflow.header.publishError"),
      });
    }
  };

  const handleVersionLoad = (versionId: string) => {
    if (onLoadVersion) {
      onLoadVersion(versionId);
    }
  };

  return (
    <Panel position="top-center" className="w-screen px-4 ">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div
            className=" p-1 active:bg-accent/90 cursor-pointer transition-colors hover:bg-accent rounded-lg"
            onClick={handleNavigateBack}
          >
            <ChevronLeft size={20} />
          </div>
          <h1 className="text-xl font-semibold max-w-[300px] truncate">
            {workflow.name}
          </h1>
          {workflow.versions &&
            workflow.versions.length > 0 &&
            onLoadVersion && (
              <VersionsDropdown
                versions={workflow.versions}
                currentWorkflowId={workflow.id}
                onVersionLoad={handleVersionLoad}
                isDraft={isDraft}
              />
            )}
        </div>

        <div className="flex items-center gap-1 border rounded-lg p-1 bg-background">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={mode === "EDIT" ? "secondary" : "ghost"}
                size="icon"
                onClick={() => handleModeChange("EDIT")}
                className={cn("transition-all", mode === "EDIT" && "shadow-sm")}
              >
                <Pencil className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>{t("workflow.header.editMode")}</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant={mode === "DEBUG" ? "secondary" : "ghost"}
                size="icon"
                onClick={() => handleModeChange("DEBUG")}
                className={cn(
                  "transition-all",
                  mode === "DEBUG" && "shadow-sm",
                )}
                data-tour="debug-button"
              >
                <Play className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>{t("workflow.header.workMode")}</p>
            </TooltipContent>
          </Tooltip>
        </div>

        <div className="flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0}>
                <Button
                  variant="ghost"
                  size="icon"
                  disabled={!hasAgents}
                  onClick={() => setIsBulkInstructionsOpen(true)}
                >
                  <FileText className="size-4" />
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              <p>
                {hasAgents
                  ? t("workflow.bulkInstructions.openTooltip")
                  : t("workflow.bulkInstructions.emptyTooltip")}
              </p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsAgentCallsOpen(true)}
              >
                <History className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>{t("workflow.header.agentCalls")}</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size={"sm"}
                onClick={handlePublish}
                disabled={isPublishing}
                data-tour="publish-button"
              >
                {isPublishing ? (
                  <Loader2 className="size-5 animate-spin" />
                ) : (
                  <span className="text-sm">
                    {t("workflow.header.publish")}
                  </span>
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>{t("workflow.header.publish")}</p>
            </TooltipContent>
          </Tooltip>

          <WorkflowActions workflow={workflow} onRefetch={onRefetch} />
        </div>
      </div>

      <PublishSuccessDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        workflowId={workflow.id}
        workflowName={workflow.name}
        version={publishedVersion}
      />

      <AgentCallsDialog
        workflowId={workflow.id}
        open={isAgentCallsOpen}
        onOpenChange={setIsAgentCallsOpen}
      />

      <BulkInstructionsDialog
        open={isBulkInstructionsOpen}
        onOpenChange={setIsBulkInstructionsOpen}
      />
    </Panel>
  );
};
