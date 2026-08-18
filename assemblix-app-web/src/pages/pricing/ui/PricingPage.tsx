// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import { useDispatch } from "react-redux";
import { Loader2, Check, Crown, Zap, Shield, Mail, Clock, Phone } from "lucide-react";
import {
  useGetBillingPlansQuery,
  useGetBillingPlanQuery,
  useGetBillingPacksQuery,
  useSubscribeToPaymentMutation,
  usePurchaseCreditPackMutation,
  usePaymentPolling,
  PlanBadge,
} from "@/entities/billing";
import { Button } from "@/shared/ui/button";
import type { PlanInfo, CreditPack } from "@/entities/billing";
import { toast } from "sonner";
import { baseApi } from "@/shared/api/baseApi";
import { openPaddleCheckout } from "@/shared/lib/paddle";

type PendingPurchaseKind = "plan" | "pack";

export const PricingPage = () => {
  const { t } = useTranslation();
  const { formatNumber } = useFormatDate();
  const dispatch = useDispatch();
  const { data: plansData, isLoading: isLoadingPlans } =
    useGetBillingPlansQuery();
  const { data: currentPlan } = useGetBillingPlanQuery();
  const { data: packsData, isLoading: isLoadingPacks } =
    useGetBillingPacksQuery();
  const [subscribeToPayment] = useSubscribeToPaymentMutation();
  const [purchaseCreditPack] = usePurchaseCreditPackMutation();

  const [processingPlan, setProcessingPlan] = useState<string | null>(null);
  const [processingPack, setProcessingPack] = useState<string | null>(null);
  const [pendingPaymentId, setPendingPaymentId] = useState<string | null>(() =>
    localStorage.getItem("pendingPaymentId")
  );
  const [pendingPurchaseKind, setPendingPurchaseKind] =
    useState<PendingPurchaseKind | null>(
      () =>
        (localStorage.getItem("pendingPurchaseKind") as PendingPurchaseKind) ||
        null
    );

  const { status: paymentStatus } = usePaymentPolling(pendingPaymentId);

  useEffect(() => {
    if (!pendingPaymentId) return;
    if (paymentStatus === "loading") return;

    const timer = setTimeout(() => {
      const isPack = pendingPurchaseKind === "pack";

      if (paymentStatus === "success") {
        dispatch(baseApi.util.invalidateTags(["Billing"]));
        toast.success(
          isPack
            ? t("billing.packs.purchaseSuccess")
            : t("billing.payments.successPage.success")
        );
      } else if (paymentStatus === "error") {
        toast.error(t("billing.payments.successPage.error"));
      } else if (paymentStatus === "timeout") {
        toast.warning(t("billing.payments.successPage.timeout"));
      }

      setPendingPaymentId(null);
      setPendingPurchaseKind(null);
      setProcessingPlan(null);
      setProcessingPack(null);
      localStorage.removeItem("pendingPaymentId");
      localStorage.removeItem("pendingPurchaseKind");
    }, 0);

    return () => clearTimeout(timer);
  }, [paymentStatus, pendingPaymentId, pendingPurchaseKind, t, dispatch]);

  const startCheckout = (paymentId: string, paymentUrl: string, kind: PendingPurchaseKind) => {
    localStorage.setItem("pendingPaymentId", paymentId);
    localStorage.setItem("pendingPurchaseKind", kind);
    setPendingPaymentId(paymentId);
    setPendingPurchaseKind(kind);

    // Paddle: open the checkout overlay on the current page.
    const url = new URL(paymentUrl);
    const txnId = url.searchParams.get("_ptxn");
    if (!txnId) {
      throw new Error("Missing Paddle transaction id in payment URL");
    }
    openPaddleCheckout(txnId);
  };

  const handleUpgrade = async (plan: PlanInfo) => {
    if (plan.plan === "free") {
      return;
    }

    setProcessingPlan(plan.plan);
    try {
      const response = await subscribeToPayment({
        targetPlan: plan.plan,
        isRecurrent: true, // Всегда включаем автопродление
      }).unwrap();

      startCheckout(response.paymentId, response.paymentUrl, "plan");
    } catch (error) {
      console.error("Failed to create payment:", error);
      toast.error(t("billing.payments.confirmDialog.error"));
      setProcessingPlan(null);
    }
  };

  const handleBuyPack = async (pack: CreditPack) => {
    setProcessingPack(pack.code);
    try {
      const response = await purchaseCreditPack({
        packCode: pack.code,
      }).unwrap();

      startCheckout(response.paymentId, response.paymentUrl, "pack");
    } catch (error) {
      console.error("Failed to create pack payment:", error);
      toast.error(t("billing.payments.confirmDialog.error"));
      setProcessingPack(null);
    }
  };

  if (isLoadingPlans) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const plans = plansData?.plans || [];
  const packs = packsData?.packs || [];

  return (
    <div className="min-h-full bg-background">
      <main className="container mx-auto px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl space-y-16">
          {/* Header */}
          <div className="text-center">
            <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              {t("billing.pricing.title")}
            </h1>
            <p className="mt-4 text-lg text-muted-foreground">
              {t("billing.pricing.subtitle")}
            </p>
          </div>

          {/* Plans Grid */}
          <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
            {plans.map((plan) => {
              const isCurrent = currentPlan?.plan === plan.plan;
              const isPopular = plan.plan === "pro";

              return (
                <div
                  key={plan.plan}
                  className={`relative flex flex-col rounded-2xl border p-8 ${
                    isPopular
                      ? "border-primary shadow-2xl ring-2 ring-primary"
                      : "border-border shadow-sm"
                  }`}
                >
                  {/* Popular Badge */}
                  {isPopular && (
                    <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                      <div className="flex items-center gap-1.5 rounded-full bg-primary px-4 py-1.5 text-xs font-semibold text-primary-foreground shadow-lg">
                        <Crown className="h-3.5 w-3.5" />
                        {t("billing.pricing.popular")}
                      </div>
                    </div>
                  )}

                  {/* Current Plan Badge */}
                  {isCurrent && (
                    <div className="absolute right-4 top-4">
                      <PlanBadge plan={plan.plan} showIcon={false} />
                    </div>
                  )}

                  {/* Plan Header */}
                  <div className="mb-6 text-center">
                    <h3 className="mb-2 text-2xl font-bold text-foreground">
                      {plan.name}
                    </h3>
                    <div className="flex items-baseline justify-center gap-1">
                      <span className="text-4xl font-bold text-foreground">
                        ${formatNumber(plan.priceUsdCents / 100)}
                      </span>
                      {plan.plan !== "free" && (
                        <span className="text-sm text-muted-foreground">
                          /{t("billing.pricing.perMonth")}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Features */}
                  <div className="mb-8 flex-1 space-y-4">
                    {/* Credits */}
                    <div className="flex items-start gap-3">
                      <Zap className="mt-0.5 h-5 w-5 text-primary" />
                      <div className="flex-1">
                        <p className="font-medium text-foreground">
                          {formatNumber(plan.creditsPerMonth)}{" "}
                          {t("billing.pricing.creditsPerMonth")}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {t("billing.pricing.creditsDesc")}
                        </p>
                      </div>
                    </div>

                    {/* RPM Limit */}
                    <div className="flex items-start gap-3">
                      <Clock className="mt-0.5 h-5 w-5 text-primary" />
                      <div className="flex-1">
                        <p className="font-medium text-foreground">
                          {t("billing.pricing.rpmLimit", {
                            count: plan.rpmLimit,
                          })}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {t("billing.pricing.rpmDesc")}
                        </p>
                      </div>
                    </div>

                    {/* Concurrent calls */}
                    <div className="flex items-start gap-3">
                      <Phone className="mt-0.5 h-5 w-5 text-primary" />
                      <div className="flex-1">
                        <p className="font-medium text-foreground">
                          {t("billing.pricing.concurrentCalls", {
                            count: plan.concurrentCalls,
                          })}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {t("billing.pricing.concurrentCallsDesc")}
                        </p>
                      </div>
                    </div>

                    {/* Support */}
                    <div className="flex items-start gap-3">
                      {plan.supportLevel === "community" ? (
                        <Mail className="mt-0.5 h-5 w-5 text-muted-foreground" />
                      ) : (
                        <Shield className="mt-0.5 h-5 w-5 text-primary" />
                      )}
                      <div className="flex-1">
                        <p className="font-medium text-foreground">
                          {t(`billing.pricing.support.${plan.supportLevel}`)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {t(`billing.pricing.supportDesc.${plan.supportLevel}`)}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* CTA Button */}
                  <Button
                    onClick={() => handleUpgrade(plan)}
                    disabled={
                      isCurrent ||
                      plan.plan === "free" ||
                      processingPlan === plan.plan
                    }
                    size="lg"
                    variant={isPopular ? "default" : "outline"}
                    className="w-full"
                  >
                    {processingPlan === plan.plan ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {t("billing.payments.confirmDialog.loading")}
                      </>
                    ) : isCurrent ? (
                      t("billing.pricing.currentPlan")
                    ) : plan.plan === "free" ? (
                      t("billing.pricing.getStarted")
                    ) : (
                      t("billing.pricing.subscribe")
                    )}
                  </Button>
                </div>
              );
            })}
          </div>

          {/* Credit Packs. The server lists a pack only when it can actually take
              money for it, so an empty list means there is nothing to sell here —
              a Buy button that always fails is worse than no button. */}
          {(isLoadingPacks || packs.length > 0) && (
            <div className="space-y-6">
              <div className="text-center">
                <h2 className="text-2xl font-bold tracking-tight text-foreground">
                  {t("billing.packs.title")}
                </h2>
                <p className="mt-2 text-muted-foreground">
                  {t("billing.packs.subtitle")}
                </p>
              </div>

              {isLoadingPacks ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
                  {packs.map((pack) => (
                    <div
                      key={pack.code}
                      className="flex flex-col items-center gap-4 rounded-2xl border border-border p-6 text-center shadow-sm"
                    >
                      <span className="text-3xl font-bold text-foreground">
                        {formatNumber(pack.credits)}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        {t("billing.packs.credits")}
                      </span>
                      <span className="text-xl font-semibold text-foreground">
                        ${formatNumber(pack.priceUsdCents / 100)}
                      </span>
                      <Button
                        onClick={() => handleBuyPack(pack)}
                        disabled={processingPack === pack.code}
                        className="w-full"
                      >
                        {processingPack === pack.code ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            {t("billing.payments.confirmDialog.loading")}
                          </>
                        ) : (
                          t("billing.packs.buy")
                        )}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Common Features */}
          <div className="rounded-2xl border border-border bg-card p-8">
            <h3 className="mb-6 text-center text-xl font-semibold text-foreground">
              {t("billing.pricing.allPlansInclude")}
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[
                "allProviders",
                "visualBuilder",
                "apiAccess",
                "sessionManagement",
                "logsMonitoring",
              ].map((feature) => (
                <div key={feature} className="flex items-center gap-3">
                  <Check className="h-5 w-5 text-success" />
                  <span className="text-sm text-foreground">
                    {t(`billing.pricing.commonFeatures.${feature}`)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* FAQ or Note */}
          <div className="rounded-lg bg-muted/50 p-6 text-center">
            <p className="text-sm text-muted-foreground">
              {t("billing.pricing.note")}
            </p>
          </div>
        </div>
      </main>
    </div>
  );
};
