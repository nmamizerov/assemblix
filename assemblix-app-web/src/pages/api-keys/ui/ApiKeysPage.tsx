import { useState } from "react";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import { Loader2, Plus, Trash2, Key } from "lucide-react";
import { Button } from "@/shared/ui/button";
import {
  useGetApiKeysQuery,
  useDeleteApiKeyMutation,
} from "@/entities/api-key";
import type { ApiKey } from "@/entities/api-key";
import { selectCurrentProjectId } from "@/entities/organization";
import { CreateApiKeyModal } from "./CreateApiKeyModal";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";
import { toast } from "sonner";

export const ApiKeysPage = () => {
  const currentProjectId = useSelector(selectCurrentProjectId);
  const { t } = useTranslation();
  const { formatShortDate, formatNumber } = useFormatDate();
  const { data, isLoading } = useGetApiKeysQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId }
  );
  const [deleteApiKey, { isLoading: isDeleting }] = useDeleteApiKeyMutation();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<ApiKey | null>(null);

  const handleDeleteClick = (key: ApiKey) => {
    setSelectedKey(key);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedKey) return;

    try {
      await deleteApiKey(selectedKey.id).unwrap();
      toast.success(t("apiKeys.deleteSuccess"));
      setDeleteDialogOpen(false);
      setSelectedKey(null);
    } catch (error) {
      console.error(error);
      toast.error(t("apiKeys.deleteError"));
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return t("apiKeys.justNow");
    if (diffMins < 60) return t("apiKeys.minutesAgo", { count: diffMins });
    if (diffHours < 24) return t("apiKeys.hoursAgo", { count: diffHours });
    if (diffDays < 30) return t("apiKeys.daysAgo", { count: diffDays });

    return formatShortDate(date);
  };

  return (
    <div className="min-h-full">
      <main className="container mx-auto">
        <div className="mx-auto space-y-8">
          {/* Header Section */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-foreground">
                {t("apiKeys.title")}
              </h1>
              <p className="mt-2 text-muted-foreground">
                {t("apiKeys.subtitle")}
              </p>
            </div>
            <Button
              onClick={() => setCreateModalOpen(true)}
              size="lg"
              className="shrink-0"
            >
              <Plus className="mr-2 h-5 w-5" />
              {t("apiKeys.createKey")}
            </Button>
          </div>

          {/* Content */}
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : !data || data.keys.length === 0 ? (
            <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                <Key className="h-8 w-8 text-primary" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">
                {t("apiKeys.noKeys")}
              </h3>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                {t("apiKeys.noKeysDescription")}
              </p>
              <Button
                onClick={() => setCreateModalOpen(true)}
                className="mt-6"
                size="lg"
              >
                <Plus className="mr-2 h-5 w-5" />
                {t("apiKeys.createFirstKey")}
              </Button>
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-card shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("apiKeys.name")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("apiKeys.key")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("apiKeys.created")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("apiKeys.lastUsed")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("apiKeys.requests")}
                      </th>
                      <th className="px-6 py-4 text-right text-sm font-semibold text-foreground">
                        {t("common.actions")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data.keys.map((key) => (
                      <tr
                        key={key.id}
                        className="transition-colors hover:bg-muted/50"
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                              <Key className="h-4 w-4 text-primary" />
                            </div>
                            <span className="font-medium text-foreground">
                              {key.name}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <code className="rounded bg-muted px-2 py-1 font-mono text-xs text-foreground">
                            {key.prefix}...
                          </code>
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {formatDate(key.createdAt)}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {key.lastUsedAt
                            ? formatDate(key.lastUsedAt)
                            : t("apiKeys.neverUsed")}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {formatNumber(key.requestCount)}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteClick(key)}
                            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data.total > 0 && (
                <div className="border-t border-border bg-muted/30 px-6 py-3">
                  <p className="text-sm text-muted-foreground">
                    {t("apiKeys.totalKeys")}: {data.total}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {/* Modals */}
      <CreateApiKeyModal
        open={createModalOpen}
        onOpenChange={setCreateModalOpen}
      />
      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        apiKeyName={selectedKey?.name || ""}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
      />
    </div>
  );
};
