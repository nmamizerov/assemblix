import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BaseForm } from "./base-form";
import { useNodeDataChange } from "./useNodeDataChange";
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
  useGetVoiceProvidersQuery,
  useGetVoiceProviderModelsQuery,
} from "@/entities/voice-model";
import {
  CredentialSelect,
  getCredentialTypeForProvider,
} from "@/entities/credential";
import { useGetBillingUsageQuery } from "@/entities/billing";
import { useGetServerConfigQuery } from "@/entities/config";
import { useSelector } from "react-redux";
import { selectCurrentProjectId } from "@/entities/organization";
import type { VoiceModelConfig } from "@/entities/workflow/model/types";

type TranscribeNodeConfig = {
  voiceModel?: VoiceModelConfig;
  saveAsUserMessage?: boolean;
};

interface TranscribeNodeFormProps {
  nodeId: string;
  config?: TranscribeNodeConfig;
  projectId?: string;
}

const defaultConfig: TranscribeNodeConfig = {
  voiceModel: { provider: "openai", model: "whisper-1" },
  saveAsUserMessage: true,
};

/**
 * Config form for the "transcribe" node: audio -> text.
 *
 * voiceModel is required by the backend; the provider/model/credential picker
 * here mirrors the transcription-scoped picker that used to live on the START
 * node (transcription moved from START to this dedicated node).
 */
export const TranscribeNodeForm = ({
  nodeId,
  config,
  projectId,
}: TranscribeNodeFormProps) => {
  const { t } = useTranslation();
  const handleDataChange = useNodeDataChange(nodeId);
  const [formData, setFormData] = useState<TranscribeNodeConfig>({
    voiceModel: config?.voiceModel ?? defaultConfig.voiceModel,
    saveAsUserMessage: config?.saveAsUserMessage ?? true,
  });

  useEffect(() => {
    handleDataChange(formData);
  }, [formData, handleDataChange]);

  const { data: voiceProviders = [] } = useGetVoiceProvidersQuery();
  const voiceProvider = formData.voiceModel?.provider;
  const { data: voiceModels = [], isLoading: isLoadingVoiceModels } =
    useGetVoiceProviderModelsQuery(
      { providerName: voiceProvider ?? "" },
      { skip: !voiceProvider }
    );

  const handleVoiceProviderChange = (value: string) =>
    setFormData((prev) => ({
      ...prev,
      // Reset model + credential when the provider changes (same as the agent node).
      voiceModel: { provider: value, model: "", credentialId: "" },
    }));

  const handleVoiceModelChange = (value: string) =>
    setFormData((prev) => ({
      ...prev,
      voiceModel: {
        provider: prev.voiceModel?.provider ?? "openai",
        model: value,
        credentialId: prev.voiceModel?.credentialId,
      },
    }));

  const handleVoiceCredentialChange = (credentialId: string) =>
    setFormData((prev) => ({
      ...prev,
      voiceModel: {
        provider: prev.voiceModel?.provider ?? "openai",
        model: prev.voiceModel?.model ?? "",
        credentialId,
      },
    }));

  const handleSaveAsUserMessageChange = (checked: boolean) =>
    setFormData((prev) => ({ ...prev, saveAsUserMessage: checked }));

  const currentProjectId = useSelector(selectCurrentProjectId);
  const { data: billingUsage } = useGetBillingUsageQuery(undefined, {
    skip: !currentProjectId,
  });
  const canUseOwnKeys = billingUsage?.features.canUseOwnKeys ?? false;
  const { data: serverConfig } = useGetServerConfigQuery();
  const voiceCredentialType = voiceProvider
    ? getCredentialTypeForProvider(voiceProvider)
    : undefined;
  const hasVoiceSystemKey = voiceProvider
    ? serverConfig
      ? Boolean(serverConfig.systemApiKeys[voiceProvider])
      : true
    : false;

  return (
    <BaseForm
      nodeType="transcribe"
      label={t("nodeForms.transcribe.title")}
      projectId={projectId}
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between items-center gap-2">
            <Label htmlFor="transcribe-voice-provider" className="shrink-0">
              {t("nodeForms.transcribe.voiceProvider")}
            </Label>
            <Select
              value={formData.voiceModel?.provider}
              onValueChange={handleVoiceProviderChange}
            >
              <SelectTrigger
                id="transcribe-voice-provider"
                className="border-none shadow-none ring-0! text-xs"
              >
                <SelectValue
                  placeholder={t("nodeForms.transcribe.selectVoiceProvider")}
                />
              </SelectTrigger>
              <SelectContent>
                {voiceProviders.map((p) => (
                  <SelectItem key={p.name} value={p.name} className="text-xs">
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {canUseOwnKeys && voiceCredentialType && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="transcribe-voice-credential" className="text-xs">
                {t("nodeForms.transcribe.voiceCredential")}
              </Label>
              <CredentialSelect
                selectedCredentialId={formData.voiceModel?.credentialId}
                onSelect={handleVoiceCredentialChange}
                credentialType={voiceCredentialType}
                placeholder={t("nodeForms.transcribe.selectVoiceCredential")}
                showSystemToken={hasVoiceSystemKey}
              />
            </div>
          )}
          <div className="flex justify-between items-center gap-2">
            <Label htmlFor="transcribe-voice-model" className="shrink-0">
              {t("nodeForms.transcribe.voiceModel")}
            </Label>
            <Select
              value={formData.voiceModel?.model}
              onValueChange={handleVoiceModelChange}
              disabled={isLoadingVoiceModels || !formData.voiceModel?.provider}
            >
              <SelectTrigger
                id="transcribe-voice-model"
                className="border-none shadow-none ring-0! text-xs"
              >
                <SelectValue
                  placeholder={
                    isLoadingVoiceModels
                      ? t("nodeForms.transcribe.loadingVoiceModels")
                      : t("nodeForms.transcribe.selectVoiceModel")
                  }
                />
              </SelectTrigger>
              <SelectContent position="popper" sideOffset={5} align="end">
                {voiceModels.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex justify-between gap-4 items-center">
          <Label htmlFor="transcribe-save-as-user-message">
            {t("nodeForms.transcribe.saveAsUserMessage")}
          </Label>
          <Switch
            id="transcribe-save-as-user-message"
            checked={formData.saveAsUserMessage ?? true}
            onCheckedChange={handleSaveAsUserMessageChange}
            showIcons={false}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          {t("nodeForms.transcribe.saveAsUserMessageHint")}
        </p>
      </div>
    </BaseForm>
  );
};
