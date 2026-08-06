import { Loader2, Mic, Plus } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  emptyDraft,
  toCreateRequest,
  useCreateVoiceAgentMutation,
  useGetVoiceAgentsQuery,
} from "@/entities/voice-agent";
import { selectCurrentProjectId } from "@/entities/organization";
import { Button } from "@/shared/ui/button";

export const VoiceAgentsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { projectId } = useParams();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const {
    data: voiceAgents = [],
    isLoading,
  } = useGetVoiceAgentsQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId }
  );
  const [createVoiceAgent, { isLoading: isCreating }] =
    useCreateVoiceAgentMutation();

  const handleCreate = async () => {
    if (!currentProjectId) return;

    try {
      const draft = { ...emptyDraft(), name: t("voiceAgents.defaultName") };
      const voiceAgent = await createVoiceAgent(
        toCreateRequest(draft, currentProjectId)
      ).unwrap();
      navigate(`/projects/${projectId}/voice-agents/${voiceAgent.id}`);
    } catch (error) {
      console.error(error);
      toast.error(t("voiceAgents.createError"));
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            {t("voiceAgents.title")}
          </h1>
          <p className="mt-2 text-muted-foreground">{t("voiceAgents.subtitle")}</p>
        </div>
        <Button onClick={handleCreate} disabled={isCreating} size="lg">
          {isCreating ? (
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          ) : (
            <Plus className="mr-2 h-5 w-5" />
          )}
          {t("voiceAgents.create")}
        </Button>
      </div>

      {voiceAgents.length === 0 ? (
        <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <Mic className="h-8 w-8 text-primary" />
          </div>
          <h3 className="mt-4 text-lg font-semibold">{t("voiceAgents.empty")}</h3>
          <p className="mt-2 max-w-sm text-sm text-muted-foreground">
            {t("voiceAgents.emptyDescription")}
          </p>
          <Button onClick={handleCreate} disabled={isCreating} className="mt-6" size="lg">
            <Plus className="mr-2 h-5 w-5" />
            {t("voiceAgents.create")}
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {voiceAgents.map((voiceAgent) => (
            <Link
              key={voiceAgent.id}
              to={`/projects/${projectId}/voice-agents/${voiceAgent.id}`}
              className="group flex items-start gap-4 rounded-lg border border-border bg-card p-6 transition-all duration-200 hover:border-primary/50 hover:shadow-md"
            >
              <div className="rounded-md bg-primary/10 p-2 transition-colors group-hover:bg-primary/20">
                <Mic className="h-5 w-5 text-primary" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="mb-1 truncate font-semibold text-card-foreground">
                  {voiceAgent.name}
                </h3>
                <p className="line-clamp-2 text-sm text-muted-foreground">
                  {voiceAgent.description || t("voiceAgents.noDescription")}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};
