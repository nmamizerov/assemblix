import { useState } from "react";
import { Loader2, Phone, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  emptyDraft,
  toCreateRequest,
  useDeleteVoiceAgentMutation,
  useGetVoiceAgentQuery,
  useUpdateVoiceAgentMutation,
  validateDraft,
  VoiceAgentForm,
} from "@/entities/voice-agent";
import type { VoiceAgent, VoiceAgentDraft } from "@/entities/voice-agent";
import { Button } from "@/shared/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/shared/ui/tooltip";

const draftFromVoiceAgent = (voiceAgent: VoiceAgent): VoiceAgentDraft => {
  const { config } = voiceAgent;
  const systemPrompt =
    config.instructions.find((instruction) => instruction.role === "system")
      ?.content ?? "";

  return {
    ...emptyDraft(),
    name: voiceAgent.name,
    description: voiceAgent.description ?? "",
    systemPrompt,
    firstMessage: config.firstMessage ?? "",
    language: config.language,
    provider: config.voice.provider,
    model: config.voice.model,
    voiceId: config.voice.voiceId ?? "",
    knowledgeBaseIds: config.knowledgeBaseIds,
    turnWorkflowId: config.turnWorkflowId ?? "",
    finalWorkflowId: config.finalWorkflowId ?? "",
  };
};

export const VoiceAgentDetailsPage = () => {
  const { agentId } = useParams();

  const { data: voiceAgent, isLoading } = useGetVoiceAgentQuery(agentId!, {
    skip: !agentId,
  });

  if (isLoading || !voiceAgent) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Keyed on the agent id so navigating between agents (or a full reload of
  // the loaded record) re-mounts with a fresh draft instead of syncing state
  // from an effect.
  return <VoiceAgentEditor key={voiceAgent.id} voiceAgent={voiceAgent} />;
};

interface VoiceAgentEditorProps {
  voiceAgent: VoiceAgent;
}

const VoiceAgentEditor = ({ voiceAgent }: VoiceAgentEditorProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { projectId } = useParams();

  const [updateVoiceAgent, { isLoading: isSaving }] =
    useUpdateVoiceAgentMutation();
  const [deleteVoiceAgent, { isLoading: isDeleting }] =
    useDeleteVoiceAgentMutation();

  const [draft, setDraft] = useState<VoiceAgentDraft>(() =>
    draftFromVoiceAgent(voiceAgent)
  );

  const errors = validateDraft(draft).errors;

  const handleSave = async () => {
    const { isValid } = validateDraft(draft);
    if (!isValid) {
      toast.error(t("voiceAgents.errors.formInvalid"));
      return;
    }

    try {
      const { name, description, config } = toCreateRequest(
        draft,
        voiceAgent.projectId
      );
      await updateVoiceAgent({ id: voiceAgent.id, name, description, config }).unwrap();
      toast.success(t("voiceAgents.saveSuccess"));
    } catch (error) {
      console.error(error);
      toast.error(t("voiceAgents.saveError"));
    }
  };

  const handleDelete = async () => {
    try {
      await deleteVoiceAgent(voiceAgent.id).unwrap();
      toast.success(t("voiceAgents.deleteSuccess"));
      navigate(`/projects/${projectId}/voice-agents`);
    } catch (error) {
      console.error(error);
      toast.error(t("voiceAgents.deleteError"));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            {voiceAgent.name}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("voiceAgents.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="mr-2 h-4 w-4" />
            )}
            {t("voiceAgents.delete")}
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t("voiceAgents.save")}
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <VoiceAgentForm draft={draft} errors={errors} onChange={setDraft} />
        </div>

        <div className="space-y-3 rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-semibold text-foreground">
            {t("voiceAgents.testCall.title")}
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("voiceAgents.testCall.description")}
          </p>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-block w-full">
                <Button disabled className="w-full">
                  <Phone className="mr-2 h-4 w-4" />
                  {t("voiceAgents.testCall.callButton")}
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              <p>{t("voiceAgents.testCall.disabledTooltip")}</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
    </div>
  );
};
