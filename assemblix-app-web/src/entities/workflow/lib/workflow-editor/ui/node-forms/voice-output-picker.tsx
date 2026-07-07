import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { Search } from "lucide-react";
import { Label } from "@/shared/ui/label";
import { Input } from "@/shared/ui/input";
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
  useGetCredentialVoicesQuery,
  useGetSystemVoicesQuery,
} from "@/entities/voice-model";
import {
  CredentialSelect,
  getCredentialTypeForProvider,
} from "@/entities/credential";
import { useGetBillingUsageQuery } from "@/entities/billing";
import { useGetServerConfigQuery } from "@/entities/config";
import { selectCurrentProjectId } from "@/entities/organization";
import type { VoiceOutputConfig } from "../../../../model/types";

interface VoiceOutputPickerProps {
  value: VoiceOutputConfig | undefined;
  onChange: (voice: VoiceOutputConfig) => void;
  // Voice route to list: "speech" (buffered) or "realtime" (streaming WS).
  capability: "speech" | "realtime";
}

/**
 * Provider → credential → model → voice cascade for TTS output. Shared by the agent
 * node (realtime) and reusable elsewhere; mirrors the start node's voice-input picker.
 */
export const VoiceOutputPicker = ({
  value,
  onChange,
  capability,
}: VoiceOutputPickerProps) => {
  const { t } = useTranslation();
  const [voiceSearchQuery, setVoiceSearchQuery] = useState("");

  const provider = value?.provider;

  const handleProviderChange = (nextProvider: string) => {
    onChange({ provider: nextProvider, model: "" });
  };
  const handleCredentialChange = (credentialId: string) => {
    onChange({
      provider: value?.provider ?? "",
      model: value?.model ?? "",
      credentialId,
      voiceId: undefined,
    });
  };
  const handleModelChange = (model: string) => {
    onChange({
      provider: value?.provider ?? "",
      model,
      credentialId: value?.credentialId,
      voiceId: value?.voiceId,
    });
  };
  const handleVoiceIdChange = (voiceId: string) => {
    onChange({
      provider: value?.provider ?? "",
      model: value?.model ?? "",
      credentialId: value?.credentialId,
      voiceId,
    });
  };

  const { data: providers = [] } = useGetVoiceProvidersQuery({ capability });
  const { data: models = [], isLoading: isLoadingModels } =
    useGetVoiceProviderModelsQuery(
      { providerName: provider ?? "", capability },
      { skip: !provider },
    );
  const { data: credentialVoices = [], isLoading: isLoadingCredentialVoices } =
    useGetCredentialVoicesQuery(
      { credentialId: value?.credentialId ?? "" },
      { skip: !value?.credentialId },
    );

  const currentProjectId = useSelector(selectCurrentProjectId);
  const { data: billingUsage } = useGetBillingUsageQuery(undefined, {
    skip: !currentProjectId,
  });
  const canUseOwnKeys = billingUsage?.features.canUseOwnKeys ?? false;
  const { data: serverConfig } = useGetServerConfigQuery();
  const voiceCredentialType = provider
    ? getCredentialTypeForProvider(provider)
    : undefined;
  const hasVoiceSystemKey = provider
    ? serverConfig
      ? Boolean(serverConfig.systemApiKeys[provider])
      : true
    : false;

  const usingSystemKey =
    Boolean(provider) && !value?.credentialId && hasVoiceSystemKey;
  const { data: systemVoices = [], isLoading: isLoadingSystemVoices } =
    useGetSystemVoicesQuery(
      { providerName: provider ?? "" },
      { skip: !usingSystemKey },
    );
  const availableVoices = value?.credentialId ? credentialVoices : systemVoices;
  const isLoadingVoices = value?.credentialId
    ? isLoadingCredentialVoices
    : isLoadingSystemVoices;

  const filteredVoices = useMemo(() => {
    if (!voiceSearchQuery.trim()) return availableVoices;
    const query = voiceSearchQuery.toLowerCase();
    return availableVoices.filter((v) => v.name.toLowerCase().includes(query));
  }, [availableVoices, voiceSearchQuery]);

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Label className="text-xs">{t("nodeForms.end.voiceProvider")}</Label>
        <Select value={provider ?? ""} onValueChange={handleProviderChange}>
          <SelectTrigger className="text-xs">
            <SelectValue placeholder={t("nodeForms.end.selectVoiceProvider")} />
          </SelectTrigger>
          <SelectContent>
            {providers.map((p) => (
              <SelectItem key={p.name} value={p.name} className="text-xs">
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {canUseOwnKeys && voiceCredentialType && (
        <div className="space-y-2">
          <Label className="text-xs">{t("nodeForms.end.voiceCredential")}</Label>
          <CredentialSelect
            selectedCredentialId={value?.credentialId}
            onSelect={handleCredentialChange}
            credentialType={voiceCredentialType}
            placeholder={t("nodeForms.end.selectVoiceCredential")}
            showSystemToken={hasVoiceSystemKey}
          />
        </div>
      )}

      <div className="space-y-2">
        <Label className="text-xs">{t("nodeForms.end.voiceModel")}</Label>
        <Select
          value={value?.model ?? ""}
          onValueChange={handleModelChange}
          disabled={isLoadingModels || !provider}
        >
          <SelectTrigger className="text-xs">
            <SelectValue
              placeholder={
                isLoadingModels
                  ? t("nodeForms.end.loadingVoiceModels")
                  : t("nodeForms.end.selectVoiceModel")
              }
            />
          </SelectTrigger>
          <SelectContent position="popper" sideOffset={5} align="end">
            {models.map((m) => (
              <SelectItem key={m.id} value={m.id} className="text-xs">
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {provider && (value?.credentialId || usingSystemKey) && (
        <div className="space-y-2">
          <Label className="text-xs">{t("nodeForms.end.voice")}</Label>
          <Select
            value={value?.voiceId ?? ""}
            onValueChange={handleVoiceIdChange}
            disabled={isLoadingVoices}
            onOpenChange={(open) => {
              if (!open) setVoiceSearchQuery("");
            }}
          >
            <SelectTrigger className="text-xs">
              <SelectValue
                placeholder={
                  isLoadingVoices
                    ? t("nodeForms.end.loadingVoices")
                    : t("nodeForms.end.selectVoice")
                }
              />
            </SelectTrigger>
            <SelectContent
              className="h-[300px] flex flex-col p-0"
              position="popper"
              sideOffset={5}
              align="end"
            >
              {availableVoices.length > 0 && (
                <div className="sticky top-0 z-10 bg-popover p-2 border-b">
                  <div className="relative">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <Input
                      placeholder={t("nodeForms.end.searchVoice")}
                      value={voiceSearchQuery}
                      onChange={(e) => setVoiceSearchQuery(e.target.value)}
                      className="pl-8 h-8 text-xs"
                      onClick={(e) => e.stopPropagation()}
                      onKeyDown={(e) => e.stopPropagation()}
                    />
                  </div>
                </div>
              )}
              <div className="overflow-y-auto flex-1 min-h-0">
                {availableVoices.length === 0 && !isLoadingVoices ? (
                  <div className="px-2 py-1.5 text-xs text-muted-foreground">
                    {t("nodeForms.end.noVoices")}
                  </div>
                ) : filteredVoices.length === 0 ? (
                  <div className="px-2 py-1.5 text-xs text-muted-foreground">
                    {t("nodeForms.end.noVoicesFound")}
                  </div>
                ) : (
                  filteredVoices.map((v) => (
                    <SelectItem key={v.id} value={v.id} className="text-xs">
                      {v.name}
                    </SelectItem>
                  ))
                )}
              </div>
            </SelectContent>
          </Select>
        </div>
      )}

      {!value?.voiceId && (
        <p className="text-xs text-amber-600">
          {t("nodeForms.end.voiceMissingWarning")}
        </p>
      )}
    </div>
  );
};
