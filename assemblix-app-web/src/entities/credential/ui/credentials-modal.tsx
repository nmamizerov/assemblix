import { useDispatch, useSelector } from "react-redux";
import { useTranslation } from "react-i18next";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";

import { closeModal, selectIsOpen } from "../model/credential.slice";
import { CredentialsManager } from "./credentials-manager";

export const CredentialsModal = () => {
  const dispatch = useDispatch();
  const isOpen = useSelector(selectIsOpen);
  const { t } = useTranslation();

  const handleClose = () => {
    dispatch(closeModal());
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>{t("credentials.title")}</DialogTitle>
          <DialogDescription>{t("credentials.subtitle")}</DialogDescription>
        </DialogHeader>

        <div className="-mx-6 px-6 overflow-y-auto flex-1">
          <CredentialsManager />
        </div>
      </DialogContent>
    </Dialog>
  );
};
