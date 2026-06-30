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
import { AlertTriangle, Loader2 } from "lucide-react";

type DeleteKBDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  kbName: string;
  onConfirm: () => void;
  isDeleting?: boolean;
};

export const DeleteKBDialog = ({
  open,
  onOpenChange,
  kbName,
  onConfirm,
  isDeleting = false,
}: DeleteKBDialogProps) => {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10">
              <AlertTriangle className="h-5 w-5 text-destructive" />
            </div>
            <DialogTitle>
              {t("knowledgeBases.deleteDialog.title")}
            </DialogTitle>
          </div>
          <DialogDescription className="pt-2 text-left">
            {t("knowledgeBases.deleteDialog.description", { name: kbName })}
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
            {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t("common.delete")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
