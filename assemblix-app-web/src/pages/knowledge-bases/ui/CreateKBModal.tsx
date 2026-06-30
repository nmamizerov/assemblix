import { useState } from "react";
import { useSelector } from "react-redux";
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
import {
  useCreateKnowledgeBaseMutation,
  useUpdateKnowledgeBaseMutation,
} from "@/entities/knowledge-base";
import type { KnowledgeBase } from "@/entities/knowledge-base";
import { selectCurrentProjectId } from "@/entities/organization";
import { toast } from "sonner";

type CreateKBModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingKB?: KnowledgeBase | null;
};

export const CreateKBModal = ({
  open,
  onOpenChange,
  editingKB,
}: CreateKBModalProps) => {
  const { t } = useTranslation();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nameError, setNameError] = useState("");

  const [createKB, { isLoading: isCreating }] =
    useCreateKnowledgeBaseMutation();
  const [updateKB, { isLoading: isUpdating }] =
    useUpdateKnowledgeBaseMutation();

  const isEditing = !!editingKB;
  const isLoading = isCreating || isUpdating;

  // Заполняем/сбрасываем поля при открытии или смене редактируемой базы —
  // во время рендера (React-паттерн синхронизации state с пропом вместо эффекта).
  const [prevSync, setPrevSync] = useState({ open, editingKB });
  if (prevSync.open !== open || prevSync.editingKB !== editingKB) {
    setPrevSync({ open, editingKB });
    if (open) {
      if (editingKB) {
        setName(editingKB.name);
        setDescription(editingKB.description || "");
      } else {
        setName("");
        setDescription("");
      }
      setNameError("");
    }
  }

  const handleSubmit = async () => {
    if (!name.trim()) {
      setNameError(t("knowledgeBases.createModal.nameRequired"));
      return;
    }
    setNameError("");

    try {
      if (isEditing) {
        await updateKB({
          id: editingKB.id,
          name: name.trim(),
          description: description.trim() || null,
        }).unwrap();
        toast.success(t("knowledgeBases.updateSuccess"));
      } else {
        await createKB({
          name: name.trim(),
          description: description.trim() || undefined,
          projectId: currentProjectId!,
        }).unwrap();
        toast.success(t("knowledgeBases.createSuccess"));
      }
      onOpenChange(false);
    } catch (error) {
      console.error(error);
      toast.error(
        isEditing
          ? t("knowledgeBases.updateError")
          : t("knowledgeBases.createError")
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isEditing
              ? t("knowledgeBases.createModal.editTitle")
              : t("knowledgeBases.createModal.title")}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="kb-name">
              {t("knowledgeBases.createModal.nameLabel")}
            </Label>
            <Input
              id="kb-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError("");
              }}
              placeholder={t("knowledgeBases.createModal.namePlaceholder")}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSubmit();
              }}
            />
            {nameError && (
              <p className="text-sm text-destructive">{nameError}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="kb-description">
              {t("knowledgeBases.createModal.descriptionLabel")}
            </Label>
            <Textarea
              id="kb-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t(
                "knowledgeBases.createModal.descriptionPlaceholder"
              )}
              rows={3}
            />
          </div>
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
            {isEditing ? t("common.save") : t("common.create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
