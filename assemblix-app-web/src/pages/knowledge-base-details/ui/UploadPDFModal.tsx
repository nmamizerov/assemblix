import { useState, useEffect, useRef } from "react";
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
import { Loader2, Upload } from "lucide-react";
import { useUploadPDFDocumentMutation } from "@/entities/knowledge-base";
import { toast } from "sonner";

type UploadPDFModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  knowledgeBaseId: string;
};

export const UploadPDFModal = ({
  open,
  onOpenChange,
  knowledgeBaseId,
}: UploadPDFModalProps) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [nameError, setNameError] = useState("");
  const [fileError, setFileError] = useState("");
  const [inlineError, setInlineError] = useState("");

  const [uploadPDF, { isLoading }] = useUploadPDFDocumentMutation();

  // Сбрасываем поля при открытии модалки — во время рендера (React-паттерн
  // синхронизации state с пропом вместо эффекта).
  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setName("");
      setFile(null);
      setNameError("");
      setFileError("");
      setInlineError("");
    }
  }

  // Очистка нативного input — это DOM-побочный эффект, поэтому остаётся в effect.
  useEffect(() => {
    if (open && fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, [open]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    if (fileError) setFileError("");
    if (inlineError) setInlineError("");
    if (selected && !name) {
      const baseName = selected.name.replace(/\.pdf$/i, "");
      setName(baseName);
    }
  };

  const handleSubmit = async () => {
    let hasError = false;
    if (!name.trim()) {
      setNameError(t("knowledgeBaseDetails.uploadPDFModal.nameRequired"));
      hasError = true;
    }
    if (!file) {
      setFileError(t("knowledgeBaseDetails.uploadPDFModal.fileRequired"));
      hasError = true;
    }
    if (hasError) return;

    setNameError("");
    setFileError("");
    setInlineError("");

    const formData = new FormData();
    formData.append("file", file!);
    formData.append("name", name.trim());

    try {
      await uploadPDF({ knowledgeBaseId, formData }).unwrap();
      toast.success(t("knowledgeBaseDetails.uploadSuccess"));
      onOpenChange(false);
    } catch (error) {
      console.error(error);
      const err = error as { status?: number; data?: { detail?: string } };
      if (err.status === 409) {
        setInlineError(t("knowledgeBaseDetails.errorDuplicate"));
      } else if (err.status === 422) {
        const detail = err.data?.detail;
        if (detail && detail.toLowerCase().includes("текст")) {
          setInlineError(t("knowledgeBaseDetails.errorNoText"));
        } else {
          setInlineError(detail || t("knowledgeBaseDetails.uploadError"));
        }
      } else {
        toast.error(t("knowledgeBaseDetails.uploadError"));
      }
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {t("knowledgeBaseDetails.uploadPDFModal.title")}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="pdf-file">
              {t("knowledgeBaseDetails.uploadPDFModal.fileLabel")}
            </Label>
            <div
              className="flex items-center gap-2 rounded-md border border-input bg-background px-3 py-2 cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="h-4 w-4 text-muted-foreground shrink-0" />
              <span className="text-sm text-muted-foreground truncate">
                {file
                  ? file.name
                  : t("knowledgeBaseDetails.uploadPDFModal.filePlaceholder")}
              </span>
            </div>
            <input
              ref={fileInputRef}
              id="pdf-file"
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handleFileChange}
            />
            {fileError && (
              <p className="text-sm text-destructive">{fileError}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="pdf-name">
              {t("knowledgeBaseDetails.uploadPDFModal.nameLabel")}
            </Label>
            <Input
              id="pdf-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError("");
              }}
              placeholder={t(
                "knowledgeBaseDetails.uploadPDFModal.namePlaceholder"
              )}
            />
            {nameError && (
              <p className="text-sm text-destructive">{nameError}</p>
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
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t("knowledgeBaseDetails.uploadPDFModal.uploading")}
              </>
            ) : (
              t("common.save")
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
