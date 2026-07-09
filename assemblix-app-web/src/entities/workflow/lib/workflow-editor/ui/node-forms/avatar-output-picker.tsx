import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";
import { Label } from "@/shared/ui/label";
import { Input } from "@/shared/ui/input";
import { useDebouncedValue } from "@/shared/lib/use-debounced-value";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import {
  useGetAvatarProvidersQuery,
  useGetAvatarProviderModelsQuery,
  useGetCredentialAvatarsQuery,
  useGetAvatarCredentialVoicesQuery,
  type WorkflowAvatarConfig,
} from "@/entities/avatar-model";
import {
  CredentialSelect,
  getCredentialTypeForProvider,
} from "@/entities/credential";

interface AvatarOutputPickerProps {
  value: WorkflowAvatarConfig | undefined;
  onChange: (avatar: WorkflowAvatarConfig) => void;
}

/**
 * Provider → credential → avatar-model → avatar cascade for the workflow-global
 * avatar persona. BYO-key only (no system-key branch) — mirrors VoiceOutputPicker's
 * cascade shape without the system-voices path.
 */
export const AvatarOutputPicker = ({
  value,
  onChange,
}: AvatarOutputPickerProps) => {
  const { t } = useTranslation();
  const [voiceSearch, setVoiceSearch] = useState("");
  const debouncedVoiceSearch = useDebouncedValue(voiceSearch, 300);

  const provider = value?.provider;

  const handleProviderChange = (nextProvider: string) => {
    onChange({ provider: nextProvider, avatarModel: "" });
  };
  const handleCredentialChange = (credentialId: string) => {
    onChange({
      provider: value?.provider ?? "",
      avatarModel: value?.avatarModel ?? "",
      credentialId,
      avatarId: undefined,
    });
  };
  const handleAvatarModelChange = (avatarModel: string) => {
    onChange({
      provider: value?.provider ?? "",
      avatarModel,
      credentialId: value?.credentialId,
      avatarId: value?.avatarId,
      voiceId: value?.voiceId,
    });
  };
  const handleAvatarIdChange = (avatarId: string) => {
    onChange({
      provider: value?.provider ?? "",
      avatarModel: value?.avatarModel ?? "",
      credentialId: value?.credentialId,
      avatarId,
      voiceId: value?.voiceId,
    });
  };
  const handleVoiceIdChange = (voiceId: string, voiceName?: string) => {
    onChange({
      provider: value?.provider ?? "",
      avatarModel: value?.avatarModel ?? "",
      credentialId: value?.credentialId,
      avatarId: value?.avatarId,
      voiceId,
      voiceName,
    });
  };

  const { data: providers = [] } = useGetAvatarProvidersQuery();
  const { data: models = [], isLoading: isLoadingModels } =
    useGetAvatarProviderModelsQuery(
      { providerName: provider ?? "" },
      { skip: !provider },
    );
  const { data: avatars = [], isLoading: isLoadingAvatars } =
    useGetCredentialAvatarsQuery(
      { credentialId: value?.credentialId ?? "" },
      { skip: !value?.credentialId },
    );
  const { data: voices = [], isLoading: isLoadingVoices } =
    useGetAvatarCredentialVoicesQuery(
      {
        credentialId: value?.credentialId ?? "",
        search: debouncedVoiceSearch.trim() || undefined,
      },
      { skip: !value?.credentialId },
    );

  const avatarCredentialType = provider
    ? getCredentialTypeForProvider(provider)
    : undefined;

  // Keep the selected voice renderable even when it isn't in the current
  // (searched/paginated) results, so the trigger doesn't blank out and the
  // selection isn't lost. Uses the stored voiceName for its label.
  const displayedVoices =
    value?.voiceId && !voices.some((v) => v.id === value.voiceId)
      ? [{ id: value.voiceId, name: value.voiceName ?? value.voiceId }, ...voices]
      : voices;

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Label className="text-xs">{t("nodeForms.avatar.provider")}</Label>
        <Select value={provider ?? ""} onValueChange={handleProviderChange}>
          <SelectTrigger className="text-xs">
            <SelectValue placeholder={t("nodeForms.avatar.selectProvider")} />
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

      {avatarCredentialType && (
        <div className="space-y-2">
          <Label className="text-xs">{t("nodeForms.avatar.credential")}</Label>
          <CredentialSelect
            selectedCredentialId={value?.credentialId}
            onSelect={handleCredentialChange}
            credentialType={avatarCredentialType}
            placeholder={t("nodeForms.avatar.selectCredential")}
            showSystemToken={false}
          />
        </div>
      )}

      {provider && (
        <div className="space-y-2">
          <Label className="text-xs">{t("nodeForms.avatar.model")}</Label>
          <Select
            value={value?.avatarModel ?? ""}
            onValueChange={handleAvatarModelChange}
            disabled={isLoadingModels}
          >
            <SelectTrigger className="text-xs">
              <SelectValue
                placeholder={
                  isLoadingModels
                    ? t("nodeForms.avatar.loadingModels")
                    : t("nodeForms.avatar.selectModel")
                }
              />
            </SelectTrigger>
            <SelectContent position="popper" sideOffset={5} align="end">
              {models.map((m) => (
                <SelectItem
                  key={m.id}
                  value={m.avatarModel}
                  className="text-xs"
                >
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {value?.credentialId && (
        <div className="space-y-2">
          <Label className="text-xs">{t("nodeForms.avatar.avatar")}</Label>
          <Select
            value={value?.avatarId ?? ""}
            onValueChange={handleAvatarIdChange}
            disabled={isLoadingAvatars}
          >
            <SelectTrigger className="text-xs">
              <SelectValue
                placeholder={
                  isLoadingAvatars
                    ? t("nodeForms.avatar.loadingAvatars")
                    : t("nodeForms.avatar.selectAvatar")
                }
              />
            </SelectTrigger>
            <SelectContent position="popper" sideOffset={5} align="end">
              {avatars.length === 0 && !isLoadingAvatars ? (
                <div className="px-2 py-1.5 text-xs text-muted-foreground">
                  {t("nodeForms.avatar.noAvatars")}
                </div>
              ) : (
                avatars.map((a) => (
                  <SelectItem key={a.id} value={a.id} className="text-xs">
                    {a.name}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>
      )}

      {value?.credentialId && (
        <div className="space-y-2">
          <Label className="text-xs">{t("nodeForms.avatar.voice")}</Label>
          <Select
            value={value?.voiceId ?? ""}
            onValueChange={(id) =>
              handleVoiceIdChange(
                id,
                displayedVoices.find((v) => v.id === id)?.name,
              )
            }
            onOpenChange={(open) => {
              if (!open) setVoiceSearch("");
            }}
          >
            <SelectTrigger className="text-xs">
              <SelectValue placeholder={t("nodeForms.avatar.selectVoice")} />
            </SelectTrigger>
            <SelectContent
              className="h-[300px] flex flex-col p-0"
              position="popper"
              sideOffset={5}
              align="end"
            >
              <div className="sticky top-0 z-10 bg-popover p-2 border-b">
                <div className="relative">
                  <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <Input
                    placeholder={t("nodeForms.avatar.searchVoice")}
                    value={voiceSearch}
                    onChange={(e) => setVoiceSearch(e.target.value)}
                    className="pl-8 h-8 text-xs"
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.stopPropagation()}
                  />
                </div>
              </div>
              <div className="overflow-y-auto flex-1 min-h-0">
                {isLoadingVoices ? (
                  <div className="px-2 py-1.5 text-xs text-muted-foreground">
                    {t("nodeForms.avatar.loadingVoices")}
                  </div>
                ) : displayedVoices.length === 0 ? (
                  <div className="px-2 py-1.5 text-xs text-muted-foreground">
                    {t("nodeForms.avatar.noVoices")}
                  </div>
                ) : (
                  displayedVoices.map((v) => (
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

      {(!value?.avatarId || !value?.voiceId) && (
        <p className="text-xs text-amber-600">
          {t("nodeForms.avatar.missingWarning")}
        </p>
      )}
    </div>
  );
};
