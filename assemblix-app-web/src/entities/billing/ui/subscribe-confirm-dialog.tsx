// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import { Loader2, CreditCard } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Button } from "@/shared/ui/button";
import { Checkbox } from "@/shared/ui/checkbox";
import { Label } from "@/shared/ui/label";
import { useSubscribeToPaymentMutation } from "../api/billing.api";
import type { PlanInfo } from "../model/types";
import { toast } from "sonner";

interface SubscribeConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plan: PlanInfo | null;
}

export const SubscribeConfirmDialog = ({
  open,
  onOpenChange,
  plan,
}: SubscribeConfirmDialogProps) => {
  const { t } = useTranslation();
  const { formatNumber } = useFormatDate();
  const [isRecurrent, setIsRecurrent] = useState(true);
  const [subscribeToPayment, { isLoading }] = useSubscribeToPaymentMutation();

  const handleSubscribe = async () => {
    if (!plan) return;

    try {
      const response = await subscribeToPayment({
        targetPlan: plan.plan,
        isRecurrent,
      }).unwrap();

      // Сохраняем paymentId в localStorage
      localStorage.setItem("pendingPaymentId", response.paymentId);

      // Перенаправляем на страницу оплаты
      window.location.href = response.paymentUrl;
    } catch (error) {
      console.error("Failed to create payment:", error);
      toast.error(t("billing.payments.confirmDialog.error"));
    }
  };

  if (!plan) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
              <CreditCard className="h-5 w-5 text-primary" />
            </div>
            <div>
              <DialogTitle>
                {t("billing.payments.confirmDialog.title")}
              </DialogTitle>
              <DialogDescription>
                {t("billing.payments.confirmDialog.subtitle", {
                  plan: plan.name,
                })}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Информация о плане */}
          <div className="rounded-lg border border-border bg-muted/50 p-4">
            <div className="flex items-baseline justify-between">
              <span className="text-sm text-muted-foreground">
                {t("billing.payments.confirmDialog.price")}
              </span>
              <span className="text-2xl font-bold text-foreground">
                {formatNumber(plan.priceRub)}₽
                <span className="text-sm font-normal text-muted-foreground">
                  /{t("billing.pricing.perMonth")}
                </span>
              </span>
            </div>
          </div>

          {/* Чекбокс автопродления */}
          <div className="flex items-start space-x-3 rounded-lg border border-border p-4">
            <Checkbox
              id="auto-renewal"
              checked={isRecurrent}
              onCheckedChange={(checked) =>
                setIsRecurrent(checked === true)
              }
            />
            <div className="flex-1 space-y-1">
              <Label
                htmlFor="auto-renewal"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                {t("billing.payments.confirmDialog.autoRenewal")}
              </Label>
              <p className="text-xs text-muted-foreground">
                {t("billing.payments.confirmDialog.autoRenewalHint")}
              </p>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
          >
            {t("billing.payments.confirmDialog.cancel")}
          </Button>
          <Button onClick={handleSubscribe} disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t("billing.payments.confirmDialog.loading")}
              </>
            ) : (
              t("billing.payments.confirmDialog.submit")
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};