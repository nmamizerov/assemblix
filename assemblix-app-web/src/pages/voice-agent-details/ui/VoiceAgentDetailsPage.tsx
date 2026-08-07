import { useState } from "react";
import { AlertCircle, Loader2, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  emptyDraft,
  toCreateRequest,
  useDeleteVoiceAgentMutation,
  useGetVoiceAgentQuery,
  useUpdateVoiceAgentMutation,
  useVoiceCall,
  validateDraft,
  VoiceAgentForm,
  VoiceCallStage,
} from "@/entities/voice-agent";
import type { VoiceAgent, VoiceAgentDraft } from "@/entities/voice-agent";
import { Button } from "@/shared/ui/button";

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
    credentialId: config.voice.credentialId,
    params: config.params,
  };
};

export const VoiceAgentDetailsPage = () => {
  const { t } = useTranslation();
  const { agentId, projectId } = useParams();
  const navigate = useNavigate();

  const {
    data: voiceAgent,
    isLoading,
    isError,
    error,
  } = useGetVoiceAgentQuery(agentId!, { skip: !agentId });

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 text-center px-4">
        <div className="bg-destructive/10 p-4 rounded-full">
          <AlertCircle className="w-10 h-10 text-destructive" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-semibold tracking-tight">
            {t("voiceAgents.loadingError")}
          </h2>
          <p className="text-muted-foreground max-w-[400px]">
            {/* @ts-expect-error error type is unknown */}
            {error?.data?.message || t("voiceAgents.loadingErrorDescription")}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => navigate(`/projects/${projectId}/voice-agents`)}
        >
          {t("voiceAgents.backToList")}
        </Button>
      </div>
    );
  }

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
  const call = useVoiceCall(voiceAgent.id);

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
    <div className="space-y-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs tracking-wide text-muted-foreground uppercase">
            {t("voiceAgents.title")}
          </p>
          <h1 className="mt-1 truncate text-3xl font-semibold tracking-tight text-foreground">
            {voiceAgent.name}
          </h1>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDelete}
            disabled={isDeleting}
            className="text-muted-foreground hover:text-destructive"
          >
            {isDeleting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="mr-2 h-4 w-4" />
            )}
            {t("voiceAgents.delete")}
          </Button>
          <Button size="sm" onClick={handleSave} disabled={isSaving}>
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t("voiceAgents.save")}
          </Button>
        </div>
      </header>

      <div className="grid items-start gap-8 xl:grid-cols-[minmax(0,1fr)_360px]">
        <VoiceAgentForm draft={draft} errors={errors} onChange={setDraft} />

        <div className="xl:sticky xl:top-6 xl:h-[calc(100vh-8rem)]">
          <VoiceCallStage call={call} />
        </div>
      </div>
    </div>
  );
};
