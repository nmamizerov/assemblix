import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import { Loader2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import type { WorkflowVersion } from "../model/types";
import { toast } from "sonner";

interface VersionsDropdownProps {
  versions: WorkflowVersion[];
  currentWorkflowId: string;
  onVersionLoad: (versionId: string) => void;
  isDraft?: boolean;
}

export const VersionsDropdown = ({
  versions,
  currentWorkflowId,
  onVersionLoad,
  isDraft = true,
}: VersionsDropdownProps) => {
  const { t } = useTranslation();
  const { formatDateTime } = useFormatDate();
  const [selectedVersionId, setSelectedVersionId] =
    useState<string>(currentWorkflowId);
  const [isLoading, setIsLoading] = useState(false);

  // Сбрасываем выбранную версию при переключении в режим черновика
  useEffect(() => {
    if (isDraft) {
      setSelectedVersionId(currentWorkflowId);
    }
  }, [isDraft, currentWorkflowId]);

  const handleVersionChange = async (versionId: string) => {
    if (versionId === selectedVersionId) return;

    setIsLoading(true);
    setSelectedVersionId(versionId);

    try {
      // Вызываем callback для загрузки версии
      onVersionLoad(versionId);
    } catch (error) {
      console.error(error);
      toast.error(t("versionsDropdown.error"), {
        description: t("versionsDropdown.loadVersionError"),
      });
      setSelectedVersionId(currentWorkflowId);
    } finally {
      setIsLoading(false);
    }
  };

  if (!versions || versions.length === 0) {
    return null;
  }

  const formatDate = (dateString: string) => formatDateTime(dateString);

  // Сортируем версии по убыванию (самая новая первая)
  const sortedVersions = [...versions].sort((a, b) => b.version - a.version);

  // Определяем отображаемый текст
  const displayText = isDraft
    ? t("versionsDropdown.draft")
    : `v${
        sortedVersions.find((v) => v.id === selectedVersionId)?.version || "?"
      }`;

  return (
    <Select
      value={selectedVersionId}
      onValueChange={handleVersionChange}
      disabled={isLoading}
    >
      <SelectTrigger
        size="sm"
        className="h-7 border-none bg-muted/50 hover:bg-muted px-2 py-1 gap-1.5"
      >
        <SelectValue>
          {isLoading ? (
            <Loader2 className="size-3 animate-spin" />
          ) : (
            <span className="text-xs font-medium">{displayText}</span>
          )}
        </SelectValue>
      </SelectTrigger>
      <SelectContent align="start">
        {sortedVersions.map((version) => (
          <SelectItem key={version.id} value={version.id}>
            <div className="flex items-center justify-between gap-4">
              <span className="font-medium">v{version.version}</span>
              <span className="text-xs text-muted-foreground">
                {formatDate(version.createdAt)}
              </span>
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};
