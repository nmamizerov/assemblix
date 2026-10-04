import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Switch } from "@/shared/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import {
  CredentialSelect,
  getCredentialTypeForProvider,
} from "@/entities/credential";
import { useGetServerConfigQuery } from "@/entities/config";
import { useGetVoiceProvidersQuery } from "@/entities/voice-model";
import {
  DynamicParamForm,
  useGetLLMProviderSchemaQuery,
  useGetLLMProvidersQuery,
} from "@/entities/llm-provider";
import { brainParamSchema, voiceBrainDefaults } from "../lib/brain-params";
import {
  applyBrainProviderChange,
  BRAIN_PROVIDERS,
  CASCADE_LIMITS,
  LANGUAGE_OPTIONS,
} from "../lib/voice-agent-form";
import type { DraftValidation } from "../lib/voice-agent-form";
import type {
  CascadeBrainConfig,
  CascadeSttConfig,
  CascadeTurnConfig,
  VoiceAgentDraft,
} from "../model/types";
import { ProviderMark } from "./provider-mark";
import { FieldError, Section } from "./section";

interface CascadeSectionProps {
  draft: VoiceAgentDraft;
  errors: DraftValidation["errors"];
  onChange: (draft: VoiceAgentDraft) => void;
}

const useHasSystemKey = () => {
  const { data: serverConfig } = useGetServerConfigQuery();
  return (provider: string) =>
    serverConfig ? Boolean(serverConfig.systemApiKeys[provider]) : true;
};

const toNumber = (value: string) => (value === "" ? Number.NaN : Number(value));

export const CascadeRecognitionSection = ({
  draft,
  onChange,
}: CascadeSectionProps) => {
  const { t } = useTranslation();
  const hasSystemKey = useHasSystemKey();
  const { stt } = draft.cascade;
  const credentialType = getCredentialTypeForProvider(stt.provider);
  const { data: sttProviders = [] } = useGetVoiceProvidersQuery({
    capability: "stt_stream",
  });
  // T-one runs only where the server hosts it; a saved choice stays visible.
  const showTone =
    stt.provider === "tone" || sttProviders.some((p) => p.name === "tone");

  const handleStt = (patch: Partial<CascadeSttConfig>) =>
    onChange({
      ...draft,
      cascade: { ...draft.cascade, stt: { ...stt, ...patch } },
    });

  return (
    <Section
      title={t("voiceAgents.sections.recognition")}
      hint={t("voiceAgents.sections.recognitionHint")}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label>{t("voiceAgents.fields.sttProvider")}</Label>
          <Select
            value={stt.provider}
            onValueChange={(provider) =>
              handleStt({
                provider: provider as CascadeSttConfig["provider"],
                credentialId: null,
              })
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="yandex">
                <span className="flex items-center gap-2">
                  <ProviderMark provider="yandex" />
                  {t("voiceAgents.fields.yandexSpeechKit")}
                </span>
              </SelectItem>
              {showTone && (
                <SelectItem value="tone">
                  {t("voiceAgents.fields.toneSelfHosted")}
                </SelectItem>
              )}
            </SelectContent>
          </Select>
          {stt.provider === "tone" && (
            <p className="text-xs text-muted-foreground">
              {t("voiceAgents.fields.toneCaption")}
            </p>
          )}
        </div>
        <div className="space-y-2">
          <Label>{t("voiceAgents.fields.language")}</Label>
          <Select
            value={draft.language}
            onValueChange={(language) => onChange({ ...draft, language })}
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
        {credentialType && (
          <div className="space-y-2 sm:col-span-2">
            <Label>{t("voiceAgents.fields.credential")}</Label>
            <CredentialSelect
              selectedCredentialId={stt.credentialId ?? undefined}
              onSelect={(id) => handleStt({ credentialId: id || null })}
              credentialType={credentialType}
              placeholder={t("voiceAgents.fields.selectCredential")}
              showSystemToken={hasSystemKey(stt.provider)}
            />
            <p className="text-xs text-muted-foreground">
              {t("voiceAgents.fields.credentialCaption")}
            </p>
          </div>
        )}
      </div>
    </Section>
  );
};

export const CascadeBrainSection = ({
  draft,
  errors,
  onChange,
}: CascadeSectionProps) => {
  const { t } = useTranslation();
  const hasSystemKey = useHasSystemKey();
  const { brain } = draft.cascade;
  const { data: allProviders = [] } = useGetLLMProvidersQuery();
  const providers = allProviders.filter((provider) =>
    BRAIN_PROVIDERS.includes(provider.name)
  );
  const { data: providerSchema, isLoading: isLoadingModels } =
    useGetLLMProviderSchemaQuery(
      { providerName: brain.provider },
      { skip: !brain.provider }
    );
  const models = useMemo(() => providerSchema?.models ?? [], [providerSchema]);
  const paramSchema = useMemo(
    () => brainParamSchema(providerSchema?.paramSchema ?? []),
    [providerSchema]
  );
  const selectedModel = models.find((model) => model.id === brain.model);
  const credentialType = getCredentialTypeForProvider(brain.provider);

  const handleBrain = (patch: Partial<CascadeBrainConfig>) =>
    onChange({
      ...draft,
      cascade: { ...draft.cascade, brain: { ...brain, ...patch } },
    });

  // Params are model-specific, so a new model starts from the voice defaults.
  const handleModel = (modelId: string) => {
    if (modelId === brain.model) return;
    const model = models.find((candidate) => candidate.id === modelId);
    handleBrain({ model: modelId, params: voiceBrainDefaults(paramSchema, model) });
  };

  const handleParam = (name: string, value: unknown) => {
    const params = { ...brain.params };
    if (value === undefined) delete params[name];
    else params[name] = value;
    handleBrain({ params });
  };

  return (
    <Section
      title={t("voiceAgents.sections.brain")}
      hint={t("voiceAgents.sections.brainHint")}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label>{t("voiceAgents.fields.provider")}</Label>
          <Select
            value={brain.provider}
            onValueChange={(provider) =>
              onChange(applyBrainProviderChange(draft, provider))
            }
          >
            <SelectTrigger className="w-full">
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
        </div>
        <div className="space-y-2">
          <Label>{t("voiceAgents.fields.model")}</Label>
          <Select
            value={brain.model}
            onValueChange={handleModel}
            disabled={!brain.provider || isLoadingModels}
          >
            <SelectTrigger
              aria-invalid={Boolean(errors.brainModel)}
              className="w-full"
            >
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
                  {model.label || model.id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldError error={errors.brainModel} />
        </div>
        {credentialType && (
          <div className="space-y-2 sm:col-span-2">
            <Label>{t("voiceAgents.fields.credential")}</Label>
            <CredentialSelect
              selectedCredentialId={brain.credentialId ?? undefined}
              onSelect={(id) => handleBrain({ credentialId: id || null })}
              credentialType={credentialType}
              placeholder={t("voiceAgents.fields.selectCredential")}
              showSystemToken={hasSystemKey(brain.provider)}
            />
          </div>
        )}
        <div className="space-y-2">
          <Label htmlFor="voice-agent-history">
            {t("voiceAgents.fields.historyTurns")}
          </Label>
          <Input
            id="voice-agent-history"
            type="number"
            min={CASCADE_LIMITS.historyTurns.min}
            max={CASCADE_LIMITS.historyTurns.max}
            value={Number.isNaN(brain.historyTurns) ? "" : brain.historyTurns}
            onChange={(e) => handleBrain({ historyTurns: toNumber(e.target.value) })}
            aria-invalid={Boolean(errors.historyTurns)}
          />
          <p className="text-xs text-muted-foreground">
            {t("voiceAgents.fields.historyTurnsCaption")}
          </p>
          <FieldError error={errors.historyTurns} />
        </div>
        {selectedModel && paramSchema.length > 0 && (
          <div className="space-y-2 sm:col-span-2">
            <DynamicParamForm
              paramSchema={paramSchema}
              model={selectedModel}
              values={brain.params}
              onChange={handleParam}
              heading={t("voiceAgents.fields.brainParams")}
              advancedToggleLabel={t("voiceAgents.fields.advancedBrainParams")}
            />
            <p className="text-xs text-muted-foreground">
              {t("voiceAgents.fields.brainParamsCaption")}
            </p>
          </div>
        )}
      </div>
    </Section>
  );
};

export const CascadeTurnSection = ({
  draft,
  errors,
  onChange,
}: CascadeSectionProps) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const { turn } = draft.cascade;
  const hasError = Boolean(
    errors.minSilenceMs ||
      errors.maxSilenceMs ||
      errors.smartTurnThreshold ||
      errors.prerollMs
  );
  // An invalid field must stay visible, or Save fails for no visible reason.
  const isExpanded = isOpen || hasError;

  const handleTurn = (patch: Partial<CascadeTurnConfig>) =>
    onChange({
      ...draft,
      cascade: { ...draft.cascade, turn: { ...turn, ...patch } },
    });

  const numberField = (
    field: "minSilenceMs" | "maxSilenceMs" | "prerollMs",
    labelKey: string
  ) => (
    <div className="space-y-2">
      <Label htmlFor={`voice-agent-turn-${field}`}>{t(labelKey)}</Label>
      <Input
        id={`voice-agent-turn-${field}`}
        type="number"
        min={CASCADE_LIMITS[field].min}
        max={CASCADE_LIMITS[field].max}
        step={10}
        value={Number.isNaN(turn[field]) ? "" : turn[field]}
        onChange={(e) => handleTurn({ [field]: toNumber(e.target.value) })}
        aria-invalid={Boolean(errors[field])}
      />
      <FieldError error={errors[field]} />
    </div>
  );

  return (
    <Section
      title={t("voiceAgents.sections.turn")}
      hint={t("voiceAgents.sections.turnHint")}
    >
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isExpanded}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        {t("voiceAgents.fields.advancedTurn")}
      </button>
      {isExpanded && (
        <div className="grid gap-4 sm:grid-cols-2">
          {numberField("minSilenceMs", "voiceAgents.fields.minSilenceMs")}
          {numberField("maxSilenceMs", "voiceAgents.fields.maxSilenceMs")}
          <div className="space-y-2 sm:col-span-2">
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="voice-agent-smart-turn" className="font-normal">
                {t("voiceAgents.fields.smartTurn")}
              </Label>
              <Switch
                id="voice-agent-smart-turn"
                checked={turn.smartTurn}
                onCheckedChange={(smartTurn) => handleTurn({ smartTurn })}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {t("voiceAgents.fields.smartTurnCaption")}
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="voice-agent-turn-threshold">
              {t("voiceAgents.fields.smartTurnThreshold")}
            </Label>
            <Input
              id="voice-agent-turn-threshold"
              type="number"
              min={0.05}
              max={0.95}
              step={0.05}
              value={
                Number.isNaN(turn.smartTurnThreshold) ? "" : turn.smartTurnThreshold
              }
              onChange={(e) =>
                handleTurn({ smartTurnThreshold: toNumber(e.target.value) })
              }
              disabled={!turn.smartTurn}
              aria-invalid={Boolean(errors.smartTurnThreshold)}
            />
            <FieldError error={errors.smartTurnThreshold} />
          </div>
          {numberField("prerollMs", "voiceAgents.fields.prerollMs")}
        </div>
      )}
    </Section>
  );
};
