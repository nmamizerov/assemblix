import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Loader2 } from "lucide-react";
import { useGetKBDocumentQuery } from "@/entities/knowledge-base";

type ViewDocumentModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  knowledgeBaseId: string;
  documentId: string | null;
  documentName: string;
};

export const ViewDocumentModal = ({
  open,
  onOpenChange,
  knowledgeBaseId,
  documentId,
  documentName,
}: ViewDocumentModalProps) => {
  const { t } = useTranslation();

  const { data, isLoading } = useGetKBDocumentQuery(
    { knowledgeBaseId, documentId: documentId! },
    { skip: !documentId || !open }
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>
            {documentName ||
              t("knowledgeBaseDetails.viewDocumentModal.title")}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto mt-2">
          {isLoading ? (
            <div className="flex h-32 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : (
            <pre className="whitespace-pre-wrap text-sm text-foreground font-sans leading-relaxed">
              {data?.content}
            </pre>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
