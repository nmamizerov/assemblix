import { useState, useEffect } from "react";
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
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Switch } from "@/shared/ui/switch";
import { useAddOrganizationMemberMutation } from "@/entities/organization";
import { toast } from "sonner";

type AddMemberModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  organizationId: string;
};

export const AddMemberModal = ({
  open,
  onOpenChange,
  organizationId,
}: AddMemberModalProps) => {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [isOwner, setIsOwner] = useState(false);
  const [addMember, { isLoading }] = useAddOrganizationMemberMutation();

  // Сброс состояния при закрытии модалки
  useEffect(() => {
    if (!open) {
      const timer = setTimeout(() => {
        setEmail("");
        setIsOwner(false);
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [open]);

  const handleAdd = async () => {
    if (!email.trim()) {
      toast.error(t("organization.addMemberModal.enterEmail"));
      return;
    }

    // Простая валидация email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      toast.error(t("organization.addMemberModal.enterValidEmail"));
      return;
    }

    try {
      await addMember({
        organizationId,
        data: {
          email: email.trim(),
          isOwner,
        },
      }).unwrap();
      toast.success(t("organization.addMemberModal.addSuccess"));
      onOpenChange(false);
    } catch (error) {
      const err = error as { status?: number };
      if (err?.status === 404) {
        toast.error(t("organization.addMemberModal.userNotFound"));
      } else if (err?.status === 400) {
        toast.error(t("organization.addMemberModal.userAlreadyMember"));
      } else if (err?.status === 403) {
        toast.error(t("organization.addMemberModal.noPermission"));
      } else {
        toast.error(t("organization.addMemberModal.addError"));
      }
    }
  };

  const handleClose = () => {
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("organization.addMemberModal.title")}</DialogTitle>
          <DialogDescription>
            {t("organization.addMemberModal.description")}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="email">{t("organization.email")}</Label>
            <Input
              id="email"
              type="email"
              placeholder={t("organization.addMemberModal.emailPlaceholder")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isLoading) {
                  handleAdd();
                }
              }}
              autoFocus
            />
          </div>
          <div className="flex items-center justify-between space-x-2">
            <div className="space-y-0.5">
              <Label htmlFor="is-owner">
                {t("organization.addMemberModal.isOwner")}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t("organization.addMemberModal.isOwnerDescription")}
              </p>
            </div>
            <Switch
              id="is-owner"
              checked={isOwner}
              onCheckedChange={setIsOwner}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isLoading}>
            {t("common.cancel")}
          </Button>
          <Button onClick={handleAdd} disabled={isLoading}>
            {isLoading
              ? t("organization.addMemberModal.adding")
              : t("organization.addMember")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
