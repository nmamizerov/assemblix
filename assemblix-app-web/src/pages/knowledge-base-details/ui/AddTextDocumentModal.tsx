import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";
import { Loader2 } from "lucide-react";
import { useAddTextDocumentMutation } from "@/entities/knowledge-base";
import { toast } from "sonner";

type AddTextDocumentModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  knowledgeBaseId: string;
};

export const AddTextDocumentModal = ({
  open,
  onOpenChange,
  knowledgeBaseId,
}: AddTextDocumentModalProps) => {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [nameError, setNameError] = useState("");
  const [contentError, setContentError] = useState("");
  const [inlineError, setInlineError] = useState("");

  const [addText, { isLoading }] = useAddTextDocumentMutation();

  // Сбрасываем поля при открытии модалки — во время рендера (React-паттерн
  // синхронизации state с пропом вместо эффекта).
  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setName("");
      setContent("");
      setNameError("");
      setContentError("");
      setInlineError("");
    }
  }

  const handleSubmit = async () => {
    let hasError = false;
    if (!name.trim()) {
      setNameError(t("knowledgeBaseDetails.addTextModal.nameRequired"));
      hasError = true;
    }
    if (!content.trim()) {
      setContentError(t("knowledgeBaseDetails.addTextModal.contentRequired"));
      hasError = true;
    }
    if (hasError) return;

    setNameError("");
    setContentError("");
    setInlineError("");

    try {
      await addText({
        knowledgeBaseId,
        name: name.trim(),
        content: content.trim(),
      }).unwrap();
      toast.success(t("knowledgeBaseDetails.addSuccess"));
      onOpenChange(false);
    } catch (error) {
      console.error(error);
      const err = error as { status?: number; data?: { detail?: string } };
      if (err.status === 409) {
        setInlineError(t("knowledgeBaseDetails.errorDuplicate"));
      } else if (err.status === 422) {
        setInlineError(
          err.data?.detail || t("knowledgeBaseDetails.addError")
        );
      } else {
        toast.error(t("knowledgeBaseDetails.addError"));
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {t("knowledgeBaseDetails.addTextModal.title")}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="doc-name">
              {t("knowledgeBaseDetails.addTextModal.nameLabel")}
            </Label>
            <Input
              id="doc-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError("");
              }}
              placeholder={t(
                "knowledgeBaseDetails.addTextModal.namePlaceholder"
              )}
            />
            {nameError && (
              <p className="text-sm text-destructive">{nameError}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="doc-content">
              {t("knowledgeBaseDetails.addTextModal.contentLabel")}
            </Label>
            <Textarea
              id="doc-content"
              value={content}
              onChange={(e) => {
                setContent(e.target.value);
                if (contentError) setContentError("");
                if (inlineError) setInlineError("");
              }}
              placeholder={t(
                "knowledgeBaseDetails.addTextModal.contentPlaceholder"
              )}
              rows={8}
              className="resize-none"
            />
            {contentError && (
              <p className="text-sm text-destructive">{contentError}</p>
            )}
          </div>

          {inlineError && (
            <p className="text-sm text-destructive rounded-md border border-destructive/20 bg-destructive/5 px-3 py-2">
              {inlineError}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
          >
            {t("common.cancel")}
          </Button>
          <Button onClick={handleSubmit} disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t("common.save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
