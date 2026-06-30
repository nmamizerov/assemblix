import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import {
  Loader2,
  Plus,
  Upload,
  Trash2,
  ArrowLeft,
  FileText,
  FileType2,
} from "lucide-react";
import { Button } from "@/shared/ui/button";
import { Progress } from "@/shared/ui/progress";
import {
  useGetKnowledgeBaseQuery,
  useGetKBDocumentsQuery,
  useDeleteKBDocumentMutation,
} from "@/entities/knowledge-base";
import type { KBDocument } from "@/entities/knowledge-base";
import { toast } from "sonner";
import { AddTextDocumentModal } from "./AddTextDocumentModal";
import { UploadPDFModal } from "./UploadPDFModal";
import { ViewDocumentModal } from "./ViewDocumentModal";
import { DeleteDocumentDialog } from "./DeleteDocumentDialog";

export const KnowledgeBaseDetailsPage = () => {
  const { knowledgeBaseId, projectId } = useParams<{ knowledgeBaseId: string; projectId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { formatShortDate } = useFormatDate();

  const { data: kb, isLoading: kbLoading } = useGetKnowledgeBaseQuery(
    knowledgeBaseId!,
    { skip: !knowledgeBaseId }
  );
  const { data: documents, isLoading: docsLoading } = useGetKBDocumentsQuery(
    { knowledgeBaseId: knowledgeBaseId! },
    { skip: !knowledgeBaseId }
  );
  const [deleteDocument, { isLoading: isDeleting }] =
    useDeleteKBDocumentMutation();

  const [addTextOpen, setAddTextOpen] = useState(false);
  const [uploadPDFOpen, setUploadPDFOpen] = useState(false);
  const [viewDocOpen, setViewDocOpen] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<KBDocument | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingDoc, setDeletingDoc] = useState<KBDocument | null>(null);

  const handleDocumentClick = (doc: KBDocument) => {
    setSelectedDoc(doc);
    setViewDocOpen(true);
  };

  const handleDeleteClick = (e: React.MouseEvent, doc: KBDocument) => {
    e.stopPropagation();
    setDeletingDoc(doc);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingDoc || !knowledgeBaseId) return;
    try {
      await deleteDocument({
        knowledgeBaseId,
        documentId: deletingDoc.id,
      }).unwrap();
      toast.success(t("knowledgeBaseDetails.deleteSuccess"));
      setDeleteDialogOpen(false);
      setDeletingDoc(null);
    } catch (error) {
      console.error(error);
      toast.error(t("knowledgeBaseDetails.deleteError"));
    }
  };

  const formatNumber = (n: number | undefined) =>
    (n ?? 0).toLocaleString();
  const usagePercent =
    kb && kb.maxCharacters
      ? Math.min(((kb.totalCharacters ?? 0) / kb.maxCharacters) * 100, 100)
      : 0;

  const isLoading = kbLoading || docsLoading;

  return (
    <div className="min-h-full">
      <main className="container mx-auto">
        <div className="mx-auto space-y-8">
          {/* Header */}
          <div className="flex flex-col gap-4">
            <button
              onClick={() => navigate(`/projects/${projectId}/knowledge-bases`)}
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-fit"
            >
              <ArrowLeft className="h-4 w-4" />
              {t("knowledgeBaseDetails.backToList")}
            </button>

            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-1">
                {kbLoading ? (
                  <div className="h-8 w-48 bg-muted animate-pulse rounded" />
                ) : (
                  <h1 className="text-3xl font-bold tracking-tight text-foreground">
                    {kb?.name}
                  </h1>
                )}
                {kb?.description && (
                  <p className="text-muted-foreground">{kb.description}</p>
                )}
              </div>

              <div className="flex gap-2 shrink-0">
                <Button
                  variant="outline"
                  onClick={() => setUploadPDFOpen(true)}
                >
                  <Upload className="mr-2 h-4 w-4" />
                  {t("knowledgeBaseDetails.uploadPDF")}
                </Button>
                <Button onClick={() => setAddTextOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  {t("knowledgeBaseDetails.addText")}
                </Button>
              </div>
            </div>

            {/* Usage indicator */}
            {kb && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm text-muted-foreground">
                  <span>
                    {t("knowledgeBaseDetails.usage", {
                      used: formatNumber(kb.totalCharacters),
                      max: formatNumber(kb.maxCharacters),
                    })}
                  </span>
                  <span>{Math.round(usagePercent)}%</span>
                </div>
                <Progress value={usagePercent} className="h-2" />
              </div>
            )}
          </div>

          {/* Documents */}
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : !documents || documents.length === 0 ? (
            <div className="flex min-h-[300px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                <FileText className="h-8 w-8 text-primary" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">
                {t("knowledgeBaseDetails.empty")}
              </h3>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                {t("knowledgeBaseDetails.emptyDescription")}
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-card shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b border-border bg-muted/50">
                    <tr>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("knowledgeBaseDetails.columns.name")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("knowledgeBaseDetails.columns.type")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("knowledgeBaseDetails.columns.characters")}
                      </th>
                      <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                        {t("knowledgeBaseDetails.columns.createdAt")}
                      </th>
                      <th className="px-6 py-4 text-right text-sm font-semibold text-foreground">
                        {t("knowledgeBaseDetails.columns.actions")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {documents.map((doc) => (
                      <tr
                        key={doc.id}
                        className="cursor-pointer transition-colors hover:bg-muted/50"
                        onClick={() => handleDocumentClick(doc)}
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                              {doc.type === "pdf" ? (
                                <FileType2 className="h-4 w-4 text-primary" />
                              ) : (
                                <FileText className="h-4 w-4 text-primary" />
                              )}
                            </div>
                            <span className="font-medium text-foreground">
                              {doc.name}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-muted">
                            {doc.type === "pdf"
                              ? t("knowledgeBaseDetails.docType.pdf")
                              : t("knowledgeBaseDetails.docType.text")}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {formatNumber(doc.characterCount)}
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {formatShortDate(doc.createdAt)}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => handleDeleteClick(e, doc)}
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
            </div>
          )}
        </div>
      </main>

      {knowledgeBaseId && (
        <>
          <AddTextDocumentModal
            open={addTextOpen}
            onOpenChange={setAddTextOpen}
            knowledgeBaseId={knowledgeBaseId}
          />
          <UploadPDFModal
            open={uploadPDFOpen}
            onOpenChange={setUploadPDFOpen}
            knowledgeBaseId={knowledgeBaseId}
          />
          <ViewDocumentModal
            open={viewDocOpen}
            onOpenChange={setViewDocOpen}
            knowledgeBaseId={knowledgeBaseId}
            documentId={selectedDoc?.id ?? null}
            documentName={selectedDoc?.name ?? ""}
          />
          <DeleteDocumentDialog
            open={deleteDialogOpen}
            onOpenChange={setDeleteDialogOpen}
            documentName={deletingDoc?.name ?? ""}
            onConfirm={handleDeleteConfirm}
            isDeleting={isDeleting}
          />
        </>
      )}
    </div>
  );
};
