import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Button } from "@/shared/ui/button";
import { AlertTriangle } from "lucide-react";

type DeleteConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiKeyName: string;
  onConfirm: () => void;
  isDeleting?: boolean;
};

export const DeleteConfirmDialog = ({
  open,
  onOpenChange,
  apiKeyName,
  onConfirm,
  isDeleting = false,
}: DeleteConfirmDialogProps) => {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10">
              <AlertTriangle className="h-5 w-5 text-destructive" />
            </div>
            <DialogTitle>{t("apiKeys.delete.title")}</DialogTitle>
          </div>
          <DialogDescription className="pt-4 text-left">
            {t("apiKeys.delete.description")}{" "}
            <span className="font-semibold text-foreground">
              "{apiKeyName}"
            </span>
            ?
            <br />
            <br />
            <span className="text-destructive">
              {t("apiKeys.delete.warning")}
            </span>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isDeleting}
          >
            {t("common.cancel")}
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={isDeleting}
          >
            {isDeleting ? t("apiKeys.delete.deleting") : t("common.delete")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
