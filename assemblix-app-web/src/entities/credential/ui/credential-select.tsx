import { useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Check, Plus, Zap } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/ui/popover";
import { Button } from "@/shared/ui/button";
import { ScrollArea } from "@/shared/ui/scroll-area";
import { cn } from "@/shared/lib/utils";

import { useGetCredentialsQuery } from "../api/credential.api";
import { openModal } from "../model/credential.slice";
import { CredentialType, type Credential } from "../model/types";
import { CREDENTIAL_TYPE_CONFIG } from "../model/config";
import { selectCurrentProjectId } from "@/entities/organization";

interface CredentialSelectProps {
  selectedCredentialId?: string;
  onSelect: (credentialId: string) => void;
  credentialType?: CredentialType | CredentialType[];
  placeholder?: string;
  /**
   * Whether to offer the "Assemblix system key" option. Hidden when the server
   * has no system API key for the relevant provider. Defaults to true.
   */
  showSystemToken?: boolean;
}

export const CredentialSelect = ({
  selectedCredentialId,
  onSelect,
  credentialType,
  placeholder,
  showSystemToken = true,
}: CredentialSelectProps) => {
  const [open, setOpen] = useState(false);
  const dispatch = useDispatch();
  const { t } = useTranslation();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const { data: credentials, isLoading } = useGetCredentialsQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId }
  );

  const defaultPlaceholder = placeholder || t("credentials.select.placeholder");

  // Фильтруем credentials по типу
  const filteredCredentials = credentials?.filter((cred) => {
    if (!credentialType) return true;
    if (Array.isArray(credentialType)) {
      return credentialType.includes(cred.type);
    }
    return cred.type === credentialType;
  });

  const selectedCredential = filteredCredentials?.find(
    (c) => c.id === selectedCredentialId
  );

  // Проверяем, выбран ли системный токен (пустой credentialId)
  const isSystemTokenSelected =
    showSystemToken && (!selectedCredentialId || selectedCredentialId === "");

  const handleSelect = (credentialId: string) => {
    onSelect(credentialId);
    setOpen(false);
  };

  const handleAddClick = (onCreated: (id: string) => void) => {
    dispatch(openModal(onCreated));
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full flex-1 justify-start text-left font-normal h-auto py-2"
        >
          {selectedCredential ? (
            <CredentialItem credential={selectedCredential} compact />
          ) : isSystemTokenSelected ? (
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary" />
              <span className="text-xs font-medium text-foreground">
                {t("credentials.systemToken.name")}
              </span>
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">
              {defaultPlaceholder}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <div className="flex flex-col">
          <div className="border-b p-3">
            <h4 className="text-sm font-semibold">
              {t("credentials.select.title")}
            </h4>
            <p className="text-xs text-muted-foreground mt-1">
              {t("credentials.select.description")}
            </p>
          </div>
          <ScrollArea className="h-[300px]">
            <div className="p-2 space-y-1">
              {/* Системный токен Assemblix - всегда первым (если доступен) */}
              {showSystemToken && (
                <>
                  <button
                    onClick={() => handleSelect("")}
                    className={cn(
                      "w-full p-2 rounded-md text-left hover:bg-accent transition-colors flex items-center gap-2 border border-dashed",
                      isSystemTokenSelected
                        ? "bg-accent border-primary"
                        : "border-muted-foreground/30"
                    )}
                  >
                    <div className="flex items-center gap-2 flex-1">
                      <div className="flex h-5 w-5 items-center justify-center rounded-sm bg-primary/10">
                        <Zap className="h-3.5 w-3.5 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium">
                          {t("credentials.systemToken.name")}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          {t("credentials.systemToken.description")}
                        </p>
                      </div>
                    </div>
                    {isSystemTokenSelected && (
                      <Check className="h-4 w-4 text-primary shrink-0" />
                    )}
                  </button>

                  {/* Разделитель */}
                  {filteredCredentials && filteredCredentials.length > 0 && (
                    <div className="relative py-2">
                      <div className="absolute inset-0 flex items-center">
                        <div className="w-full border-t border-border" />
                      </div>
                      <div className="relative flex justify-center">
                        <span className="bg-popover px-2 text-[10px] text-muted-foreground uppercase">
                          {t("common.or") || "или"}
                        </span>
                      </div>
                    </div>
                  )}
                </>
              )}

              {isLoading ? (
                <div className="p-4">
                  <p className="text-xs text-muted-foreground text-center">
                    {t("common.loading")}
                  </p>
                </div>
              ) : filteredCredentials && filteredCredentials.length === 0 ? (
                <div className="p-4">
                  <p className="text-xs text-muted-foreground text-center">
                    {t("credentials.select.noKeys")}
                  </p>
                </div>
              ) : (
                filteredCredentials?.map((credential) => {
                  const isSelected = credential.id === selectedCredentialId;
                  return (
                    <button
                      key={credential.id}
                      onClick={() => handleSelect(credential.id)}
                      className={cn(
                        "w-full p-2 rounded-md text-left hover:bg-accent transition-colors flex items-center gap-2",
                        isSelected && "bg-accent"
                      )}
                    >
                      <div className="flex-1">
                        <CredentialItem credential={credential} />
                      </div>
                      {isSelected && (
                        <Check className="h-4 w-4 text-primary shrink-0" />
                      )}
                    </button>
                  );
                })
              )}

              {/* Кнопка добавления нового ключа */}
              <button
                className="w-full p-2 rounded-md text-left hover:bg-accent transition-colors flex items-center gap-2 border border-dashed border-muted-foreground/30 mt-2"
                onClick={() =>
                  handleAddClick((newId) => {
                    onSelect(newId);
                  })
                }
              >
                <Plus className="h-4 w-4 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  {t("credentials.select.add")}
                </span>
              </button>
            </div>
          </ScrollArea>
        </div>
      </PopoverContent>
    </Popover>
  );
};

// Компонент для отображения credential в списке или кнопке
const CredentialItem = ({
  credential,
  compact = false,
}: {
  credential: Credential;
  compact?: boolean;
}) => {
  const config = CREDENTIAL_TYPE_CONFIG[credential.type];
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-2">
      <img src={config.icon} alt={config.label} className="w-5 h-5" />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate">
          {credential.name || t("credentials.untitled")}
        </p>
        {!compact && (
          <p className="text-[10px] text-muted-foreground">{config.label}</p>
        )}
      </div>
    </div>
  );
};
