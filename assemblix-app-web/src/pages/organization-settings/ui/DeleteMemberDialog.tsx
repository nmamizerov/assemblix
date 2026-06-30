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

type DeleteMemberDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  memberName: string;
  memberEmail: string;
  onConfirm: () => void;
  isDeleting: boolean;
};

export const DeleteMemberDialog = ({
  open,
  onOpenChange,
  memberName,
  memberEmail,
  onConfirm,
  isDeleting,
}: DeleteMemberDialogProps) => {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10">
              <AlertTriangle className="h-5 w-5 text-destructive" />
            </div>
            <DialogTitle>
              {t("organization.removeMemberModal.title")}
            </DialogTitle>
          </div>
          <DialogDescription className="pt-4">
            {t("organization.removeMemberModal.description")}{" "}
            <span className="font-semibold text-foreground">
              {memberName || memberEmail}
            </span>{" "}
            {t("organization.removeMemberModal.fromOrganization")}
            <br />
            <br />
            {t("organization.removeMemberModal.warning")}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
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
            {isDeleting
              ? t("organization.removeMemberModal.deleting")
              : t("common.delete")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
