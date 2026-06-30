import { useState } from "react";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { useFormatDate } from "@/shared/lib/format-date";
import { Loader2, Plus, BookMarked, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/shared/ui/button";
import {
  useGetKnowledgeBasesQuery,
  useDeleteKnowledgeBaseMutation,
} from "@/entities/knowledge-base";
import type { KnowledgeBase } from "@/entities/knowledge-base";
import { selectCurrentProjectId } from "@/entities/organization";
import { CreateKBModal } from "./CreateKBModal";
import { DeleteKBDialog } from "./DeleteKBDialog";
import { toast } from "sonner";

export const KnowledgeBasesPage = () => {
  const currentProjectId = useSelector(selectCurrentProjectId);
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { projectId } = useParams();
  const { formatShortDate } = useFormatDate();

  const { data, isLoading } = useGetKnowledgeBasesQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId }
  );
  const [deleteKB, { isLoading: isDeleting }] =
    useDeleteKnowledgeBaseMutation();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editingKB, setEditingKB] = useState<KnowledgeBase | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingKB, setDeletingKB] = useState<KnowledgeBase | null>(null);

  const handleEditClick = (e: React.MouseEvent, kb: KnowledgeBase) => {
    e.stopPropagation();
    setEditingKB(kb);
    setCreateModalOpen(true);
  };

  const handleDeleteClick = (e: React.MouseEvent, kb: KnowledgeBase) => {
    e.stopPropagation();
    setDeletingKB(kb);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingKB) return;
    try {
      await deleteKB(deletingKB.id).unwrap();
      toast.success(t("knowledgeBases.deleteSuccess"));
      setDeleteDialogOpen(false);
      setDeletingKB(null);
    } catch (error) {
      console.error(error);
      toast.error(t("knowledgeBases.deleteError"));
    }
  };

  const handleModalClose = (open: boolean) => {
    setCreateModalOpen(open);
    if (!open) setEditingKB(null);
  };

  const formatNumber = (n: number | undefined) => (n ?? 0).toLocaleString();

  return (
    <div className="min-h-full">
      <main className="container mx-auto">
        <div className="mx-auto space-y-8">
          {/* Header */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-foreground">
                {t("knowledgeBases.title")}
              </h1>
              <p className="mt-2 text-muted-foreground">
                {t("knowledgeBases.subtitle")}
              </p>
            </div>
            <Button
              onClick={() => {
                setEditingKB(null);
                setCreateModalOpen(true);
              }}
              size="lg"
              className="shrink-0"
            >
              <Plus className="mr-2 h-5 w-5" />
              {t("knowledgeBases.create")}
            </Button>
          </div>

          {/* Content */}
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : !data || data.length === 0 ? (
            <div className="flex min-h-[400px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                <BookMarked className="h-8 w-8 text-primary" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">
                {t("knowledgeBases.empty")}
              </h3>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                {t("knowledgeBases.emptyDescription")}
              </p>
              <Button
                onClick={() => {
                  setEditingKB(null);
                  setCreateModalOpen(true);
                }}
                className="mt-6"
                size="lg"
              >
                <Plus className="mr-2 h-5 w-5" />
                {t("knowledgeBases.create")}
              </Button>
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-card shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("knowledgeBases.columns.name")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("knowledgeBases.columns.description")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("knowledgeBases.columns.documents")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("knowledgeBases.columns.characters")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("knowledgeBases.columns.createdAt")}
                      </th>
                      <th className="px-6 py-4 text-right text-sm font-semibold text-foreground">
                        {t("knowledgeBases.columns.actions")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data.map((kb) => (
                      <tr
                        key={kb.id}
                        className="cursor-pointer transition-colors hover:bg-muted/50"
                        onClick={() =>
                          navigate(`/projects/${projectId}/knowledge-bases/${kb.id}`)
                        }
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                              <BookMarked className="h-4 w-4 text-primary" />
                            </div>
                            <span className="font-medium text-foreground">
                              {kb.name}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground max-w-[200px] truncate">
                          {kb.description || "—"}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {kb.documentCount}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {formatNumber(kb.totalCharacters)}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {formatShortDate(kb.createdAt)}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => handleEditClick(e, kb)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => handleDeleteClick(e, kb)}
                              className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>

      <CreateKBModal
        open={createModalOpen}
        onOpenChange={handleModalClose}
        editingKB={editingKB}
      />
      <DeleteKBDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        kbName={deletingKB?.name || ""}
        onConfirm={handleDeleteConfirm}
        isDeleting={isDeleting}
      />
    </div>
  );
};
