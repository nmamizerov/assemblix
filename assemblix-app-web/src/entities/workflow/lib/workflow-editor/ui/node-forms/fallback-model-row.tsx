import { useTranslation } from "react-i18next";
import { Label } from "@/shared/ui/label";
import { Button } from "@/shared/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { TrashIcon } from "lucide-react";
import {
  CredentialSelect,
  getCredentialTypeForProvider,
} from "@/entities/credential";
import {
  useGetLLMProviderSchemaQuery,
  type ProviderListItem,
} from "@/entities/llm-provider";
import { Provider, type FallbackModelConfig } from "../../../../model/types";

interface FallbackModelRowProps {
  index: number;
  value: FallbackModelConfig;
  providerList: ProviderListItem[];
  canUseOwnKeys: boolean;
  hasSystemKeyForProvider: (provider: Provider) => boolean;
  onChange: (next: FallbackModelConfig) => void;
  onRemove: () => void;
}

/** One fallback-model entry: provider, model and credential stacked vertically
 *  (mirrors the main agent form). Each row fetches its own provider schema because
 *  hooks cannot run in a loop, so the row is its own component. */
export const FallbackModelRow = ({
  index,
  value,
  providerList,
  canUseOwnKeys,
  hasSystemKeyForProvider,
  onChange,
  onRemove,
}: FallbackModelRowProps) => {
  const { t } = useTranslation();
  const { data: providerSchema } = useGetLLMProviderSchemaQuery(
    { providerName: value.provider },
    { skip: !value.provider },
  );
  const models = providerSchema?.models ?? [];
  const credentialType = getCredentialTypeForProvider(value.provider);

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">
          {t("nodeForms.agent.fallbackModelItem", { index: index + 1 })}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={onRemove}
        >
          <TrashIcon className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">{t("nodeForms.agent.provider")}</Label>
        <Select
          value={value.provider}
          onValueChange={(provider) =>
            onChange({
              ...value,
              provider: provider as Provider,
              model: "",
              credentialId: undefined,
            })
          }
        >
          <SelectTrigger className="text-xs">
            <SelectValue placeholder={t("nodeForms.agent.selectProvider")} />
          </SelectTrigger>
          <SelectContent>
            {providerList.map((p) => (
              <SelectItem key={p.name} value={p.name} className="text-xs">
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">{t("nodeForms.agent.model")}</Label>
        <Select
          value={value.model}
          onValueChange={(model) => onChange({ ...value, model })}
        >
          <SelectTrigger className="text-xs">
            <SelectValue placeholder={t("nodeForms.agent.selectModel")} />
          </SelectTrigger>
          <SelectContent>
            {models.map((m) => (
              <SelectItem key={m.id} value={m.id} className="text-xs">
                {m.label || m.id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {canUseOwnKeys && credentialType && (
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs">{t("nodeForms.agent.credential")}</Label>
          <CredentialSelect
            selectedCredentialId={value.credentialId}
            onSelect={(id) => onChange({ ...value, credentialId: id })}
            credentialType={credentialType}
            placeholder={t("nodeForms.agent.selectCredential")}
            showSystemToken={hasSystemKeyForProvider(value.provider)}
          />
        </div>
      )}
    </div>
  );
};
