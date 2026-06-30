// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/shared/ui/button";
import { usePaymentPolling } from "@/entities/billing/lib/use-payment-polling";
import { useGetBillingPlanQuery } from "@/entities/billing";

export const PaymentSuccessPage = () => {
  const { t } = useTranslation();
  const { formatNumber } = useFormatDate();
  const navigate = useNavigate();

  // Получаем paymentId из localStorage
  const paymentId = localStorage.getItem("pendingPaymentId");

  // Используем хук поллинга
  const { status, paymentData } = usePaymentPolling(paymentId);

  // Получаем текущий план для отображения после успеха
  const { refetch: refetchPlan } = useGetBillingPlanQuery();

  useEffect(() => {
    if (status === "success") {
      // Обновляем информацию о плане после успешной оплаты
      refetchPlan();
      // Очищаем localStorage
      localStorage.removeItem("pendingPaymentId");
    }
  }, [status, refetchPlan]);

  const handleGoToWorkflows = () => {
    navigate("/");
  };

  const handleRetry = () => {
    localStorage.removeItem("pendingPaymentId");
    navigate("/pricing");
  };

  // Loading состояние
  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="w-full max-w-md space-y-6 text-center">
          <div className="flex justify-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary/10">
              <Loader2 className="h-10 w-10 animate-spin text-primary" />
            </div>
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-bold text-foreground">
              {t("billing.payments.successPage.checking")}
            </h1>
            <p className="text-muted-foreground">
              {t("billing.payments.successPage.checkingHint")}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Success состояние
  if (status === "success" && paymentData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="w-full max-w-md space-y-6 text-center">
          <div className="flex justify-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
              <CheckCircle2 className="h-10 w-10 text-green-600 dark:text-green-400" />
            </div>
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-bold text-foreground">
              {t("billing.payments.successPage.success")}
            </h1>
            <p className="text-muted-foreground">
              {t("billing.payments.successPage.successHint", {
                plan: paymentData.targetPlan.toUpperCase(),
              })}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">
                  {t("billing.pricing.title")}:
                </span>
                <span className="font-medium text-foreground">
                  {paymentData.targetPlan.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">
                  {t("billing.payments.confirmDialog.price")}:
                </span>
                <span className="font-medium text-foreground">
                  {formatNumber(paymentData.amount / 100)}₽
                </span>
              </div>
            </div>
          </div>
          <Button onClick={handleGoToWorkflows} size="lg" className="w-full">
            {t("billing.payments.successPage.goToAgents")}
          </Button>
        </div>
      </div>
    );
  }

  // Error состояние
  if (status === "error") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="w-full max-w-md space-y-6 text-center">
          <div className="flex justify-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
              <XCircle className="h-10 w-10 text-red-600 dark:text-red-400" />
            </div>
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-bold text-foreground">
              {t("billing.payments.successPage.error")}
            </h1>
            <p className="text-muted-foreground">
              {t("billing.payments.successPage.errorHint")}
            </p>
          </div>
          <div className="space-y-3">
            <Button onClick={handleRetry} size="lg" className="w-full">
              {t("billing.payments.successPage.retry")}
            </Button>
            <Button
              variant="outline"
              onClick={handleGoToWorkflows}
              size="lg"
              className="w-full"
            >
              {t("billing.payments.successPage.goToAgents")}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Timeout состояние
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-6 text-center">
        <div className="flex justify-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/30">
            <AlertTriangle className="h-10 w-10 text-amber-600 dark:text-amber-400" />
          </div>
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-foreground">
            {t("billing.payments.successPage.timeout")}
          </h1>
          <p className="text-muted-foreground">
            {t("billing.payments.successPage.timeoutHint")}
          </p>
        </div>
        <Button onClick={handleGoToWorkflows} size="lg" className="w-full">
          {t("billing.payments.successPage.goToAgents")}
        </Button>
      </div>
    </div>
  );
};