import { useTranslation } from "react-i18next";
import { Label } from "@/shared/ui/label";
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

  const avatarCredentialType = provider
    ? getCredentialTypeForProvider(provider)
    : undefined;

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

      {!value?.avatarModel && (
        <p className="text-xs text-amber-600">
          {t("nodeForms.avatar.missingWarning")}
        </p>
      )}
    </div>
  );
};
