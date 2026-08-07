import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { AlertTriangle } from "lucide-react";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";
import { Checkbox } from "@/shared/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { cn } from "@/shared/lib/utils";
import {
  useGetVoiceProvidersQuery,
  useGetVoiceProviderModelsQuery,
  useGetSystemVoicesQuery,
} from "@/entities/voice-model";
import {
  CredentialSelect,
  getCredentialTypeForProvider,
} from "@/entities/credential";
import { useGetBillingUsageQuery } from "@/entities/billing";
import { useGetKnowledgeBasesQuery } from "@/entities/knowledge-base";
import { useGetWorkflowsQuery } from "@/entities/workflow";
import { selectCurrentProjectId } from "@/entities/organization";
import { applyProviderChange, LANGUAGE_OPTIONS } from "../lib/voice-agent-form";
import type { DraftValidation } from "../lib/voice-agent-form";
import type { VoiceAgentDraft } from "../model/types";
import { ProviderMark } from "./provider-mark";

// Soft budget for the knowledge base text that gets inlined into the voice
// agent's prompt. There is no backend-enforced cap — this only warns the
// author before the prompt grows large enough to hurt realtime latency.
const KNOWLEDGE_CHAR_WARNING_LIMIT = 8000;

// Radix Select reserves the empty string for "nothing selected", so an explicit
// "no workflow" choice needs its own sentinel value.
const NO_WORKFLOW = "__none__";

interface VoiceAgentFormProps {
  draft: VoiceAgentDraft;
  errors: DraftValidation["errors"];
  onChange: (draft: VoiceAgentDraft) => void;
}

export const VoiceAgentForm = ({ draft, errors, onChange }: VoiceAgentFormProps) => {
  const { t } = useTranslation();
  const currentProjectId = useSelector(selectCurrentProjectId);

  const { data: providers = [] } = useGetVoiceProvidersQuery({
    capability: "conversation",
  });
  const { data: models = [], isLoading: isLoadingModels } =
    useGetVoiceProviderModelsQuery(
      { providerName: draft.provider, capability: "conversation" },
      { skip: !draft.provider }
    );
  const { data: knowledgeBases = [] } = useGetKnowledgeBasesQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId }
  );
  const { data: workflows = [] } = useGetWorkflowsQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId }
  );
  const { data: voices = [], isLoading: isLoadingVoices } = useGetSystemVoicesQuery(
    { providerName: draft.provider },
    { skip: !draft.provider }
  );
  const credentialType = getCredentialTypeForProvider(draft.provider);
  // Matches voice-output-picker.tsx: the credential field only makes sense
  // for plans that can actually use their own key — the backend otherwise
  // silently ignores credentialId and falls back to the system key.
  const { data: billingUsage } = useGetBillingUsageQuery(undefined, {
    skip: !currentProjectId,
  });
  const canUseOwnKeys = billingUsage?.features.canUseOwnKeys ?? false;

  const handleField = <K extends keyof VoiceAgentDraft>(
    field: K,
    value: VoiceAgentDraft[K]
  ) => {
    onChange({ ...draft, [field]: value });
  };

  const handleProviderChange = (provider: string) => {
    onChange(applyProviderChange(draft, provider));
  };

  const handleCredentialChange = (credentialId: string) => {
    handleField("credentialId", credentialId || null);
  };

  const handleWorkflowChange = (
    field: "turnWorkflowId" | "finalWorkflowId",
    value: string
  ) => {
    handleField(field, value === NO_WORKFLOW ? "" : value);
  };

  const handleKnowledgeBaseToggle = (knowledgeBaseId: string, checked: boolean) => {
    const knowledgeBaseIds = checked
      ? [...draft.knowledgeBaseIds, knowledgeBaseId]
      : draft.knowledgeBaseIds.filter((id) => id !== knowledgeBaseId);
    handleField("knowledgeBaseIds", knowledgeBaseIds);
  };

  const selectedKnowledgeBases = knowledgeBases.filter((kb) =>
    draft.knowledgeBaseIds.includes(kb.id)
  );
  const knowledgeCharCount = selectedKnowledgeBases.reduce(
    (sum, kb) => sum + kb.totalCharacters,
    0
  );
  const isOverKnowledgeLimit = knowledgeCharCount > KNOWLEDGE_CHAR_WARNING_LIMIT;

  return (
    <div className="divide-y divide-border">
      <Section title={t("voiceAgents.sections.agent")} hint={t("voiceAgents.sections.agentHint")}>
        <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="voice-agent-name">{t("voiceAgents.fields.name")}</Label>
          <Input
            id="voice-agent-name"
            value={draft.name}
            onChange={(e) => handleField("name", e.target.value)}
            aria-invalid={Boolean(errors.name)}
          />
          {errors.name && (
            <p className="text-xs text-destructive">{t(errors.name)}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="voice-agent-description">
            {t("voiceAgents.fields.description")}
          </Label>
          <Input
            id="voice-agent-description"
            value={draft.description}
            onChange={(e) => handleField("description", e.target.value)}
          />
        </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="voice-agent-prompt">
            {t("voiceAgents.fields.systemPrompt")}
          </Label>
          <Textarea
            id="voice-agent-prompt"
            className="min-h-32"
            value={draft.systemPrompt}
            onChange={(e) => handleField("systemPrompt", e.target.value)}
            aria-invalid={Boolean(errors.systemPrompt)}
          />
          {errors.systemPrompt && (
            <p className="text-xs text-destructive">{t(errors.systemPrompt)}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="voice-agent-first-message">
            {t("voiceAgents.fields.firstMessage")}
          </Label>
          <Textarea
            id="voice-agent-first-message"
            value={draft.firstMessage}
            onChange={(e) => handleField("firstMessage", e.target.value)}
          />
        </div>
      </Section>

      <Section title={t("voiceAgents.sections.voice")} hint={t("voiceAgents.sections.voiceHint")}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>{t("voiceAgents.fields.provider")}</Label>
            <Select value={draft.provider} onValueChange={handleProviderChange}>
              <SelectTrigger aria-invalid={Boolean(errors.provider)} className="w-full">
                <SelectValue placeholder={t("voiceAgents.fields.selectProvider")} />
              </SelectTrigger>
              <SelectContent>
                {providers.map((provider) => (
                  <SelectItem key={provider.name} value={provider.name}>
                    <span className="flex items-center gap-2">
                      <ProviderMark provider={provider.name} />
                      {provider.label}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.provider && (
              <p className="text-xs text-destructive">{t(errors.provider)}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label>{t("voiceAgents.fields.model")}</Label>
            <Select
              value={draft.model}
              onValueChange={(value) => handleField("model", value)}
              disabled={!draft.provider || isLoadingModels}
            >
              <SelectTrigger aria-invalid={Boolean(errors.model)} className="w-full">
                <SelectValue
                  placeholder={
                    isLoadingModels
                      ? t("voiceAgents.fields.loadingModels")
                      : t("voiceAgents.fields.selectModel")
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {models.map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    <span className="flex w-full items-center justify-between gap-4">
                      {model.label}
                      {model.costPerMinute != null && (
                        <span className="text-xs tabular-nums text-muted-foreground">
                          {t("voiceAgents.fields.perMinute", {
                            cost: model.costPerMinute.toFixed(2),
                          })}
                        </span>
                      )}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.model && (
              <p className="text-xs text-destructive">{t(errors.model)}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label>{t("voiceAgents.fields.voiceId")}</Label>
            <Select
              value={draft.voiceId}
              onValueChange={(value) => handleField("voiceId", value)}
              disabled={!draft.provider || isLoadingVoices}
            >
              <SelectTrigger className="w-full">
                <SelectValue
                  placeholder={
                    isLoadingVoices
                      ? t("voiceAgents.fields.loadingVoices")
                      : t("voiceAgents.fields.selectVoice")
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {voices.map((voice) => (
                  <SelectItem key={voice.id} value={voice.id}>
                    {voice.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{t("voiceAgents.fields.language")}</Label>
            <Select
              value={draft.language}
              onValueChange={(value) => handleField("language", value)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder={t("voiceAgents.fields.selectLanguage")} />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGE_OPTIONS.map((language) => (
                  <SelectItem key={language.code} value={language.code}>
                    {language.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {canUseOwnKeys && credentialType && (
            <div className="space-y-2 sm:col-span-2">
              <Label>{t("voiceAgents.fields.credential")}</Label>
              <CredentialSelect
                selectedCredentialId={draft.credentialId ?? undefined}
                onSelect={handleCredentialChange}
                credentialType={credentialType}
                placeholder={t("voiceAgents.fields.selectCredential")}
              />
              <p className="text-xs text-muted-foreground">
                {t("voiceAgents.fields.credentialCaption")}
              </p>
            </div>
          )}
        </div>
      </Section>

      <Section title={t("voiceAgents.sections.knowledge")} hint={t("voiceAgents.sections.knowledgeHint")}>
        <div className="space-y-2 rounded-lg border border-border p-3">
          {knowledgeBases.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("voiceAgents.fields.noKnowledgeBases")}
            </p>
          ) : (
            knowledgeBases.map((kb) => (
              <div key={kb.id} className="flex items-center gap-2">
                <Checkbox
                  id={`voice-agent-kb-${kb.id}`}
                  checked={draft.knowledgeBaseIds.includes(kb.id)}
                  onCheckedChange={(checked) =>
                    handleKnowledgeBaseToggle(kb.id, checked === true)
                  }
                />
                <Label
                  htmlFor={`voice-agent-kb-${kb.id}`}
                  className="cursor-pointer font-normal"
                >
                  {kb.name}
                </Label>
              </div>
            ))
          )}
        </div>
        <p
          className={cn(
            "text-xs",
            isOverKnowledgeLimit ? "text-destructive" : "text-muted-foreground"
          )}
        >
          {t("voiceAgents.fields.knowledgeCharCount", {
            count: knowledgeCharCount,
            limit: KNOWLEDGE_CHAR_WARNING_LIMIT,
          })}
        </p>
        {isOverKnowledgeLimit && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{t("voiceAgents.fields.knowledgeCharWarning")}</span>
          </div>
        )}
      </Section>

      <Section title={t("voiceAgents.sections.analysis")} hint={t("voiceAgents.sections.analysisHint")}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>{t("voiceAgents.fields.turnWorkflow")}</Label>
            <Select
              value={draft.turnWorkflowId || NO_WORKFLOW}
              onValueChange={(value) => handleWorkflowChange("turnWorkflowId", value)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder={t("voiceAgents.fields.selectWorkflow")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_WORKFLOW}>
                  {t("voiceAgents.fields.noWorkflow")}
                </SelectItem>
                {workflows.map((workflow) => (
                  <SelectItem key={workflow.id} value={workflow.id}>
                    {workflow.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t("voiceAgents.fields.turnWorkflowCaption")}
            </p>
          </div>
          <div className="space-y-2">
            <Label>{t("voiceAgents.fields.finalWorkflow")}</Label>
            <Select
              value={draft.finalWorkflowId || NO_WORKFLOW}
              onValueChange={(value) => handleWorkflowChange("finalWorkflowId", value)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder={t("voiceAgents.fields.selectWorkflow")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_WORKFLOW}>
                  {t("voiceAgents.fields.noWorkflow")}
                </SelectItem>
                {workflows.map((workflow) => (
                  <SelectItem key={workflow.id} value={workflow.id}>
                    {workflow.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t("voiceAgents.fields.finalWorkflowCaption")}
            </p>
          </div>
        </div>
      </Section>
    </div>
  );
};

interface SectionProps {
  title: string;
  hint: string;
  children: React.ReactNode;
}

/**
 * Section label and its one-line purpose sit in a narrow rail beside the fields.
 * Two effects: the eye gets a stable left edge to scan, and inputs stop
 * stretching to the full width of the page, which is what made this read as a
 * settings dump rather than a considered form.
 */
const Section = ({ title, hint, children }: SectionProps) => (
  <section className="grid gap-x-10 gap-y-4 py-8 first:pt-0 last:pb-0 lg:grid-cols-[13rem_minmax(0,1fr)]">
    <div className="lg:pt-1">
      <h2 className="text-sm font-medium tracking-tight text-foreground">{title}</h2>
      <p className="mt-1 max-w-[24ch] text-xs leading-relaxed text-muted-foreground">
        {hint}
      </p>
    </div>
    <div className="max-w-2xl space-y-4">{children}</div>
  </section>
);
