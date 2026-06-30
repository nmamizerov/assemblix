// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import { useDispatch } from "react-redux";
import {
  Loader2,
  Check,
  X,
  Crown,
  Users,
  Zap,
  Shield,
  Mail,
  Clock,
  Building2,
} from "lucide-react";
import {
  useGetBillingPlansQuery,
  useGetBillingPlanQuery,
  useSubscribeToPaymentMutation,
  usePaymentPolling,
  PlanBadge,
} from "@/entities/billing";
import { Button } from "@/shared/ui/button";
import type { PlanInfo } from "@/entities/billing";
import { toast } from "sonner";
import { baseApi } from "@/shared/api/baseApi";
import { openPaddleCheckout } from "@/shared/lib/paddle";
import { getCommunityLinks } from "@/shared/lib/community-links";

// USD prices matching the landing page (assmblx.com)
const USD_PRICES: Record<string, string> = {
  free: "$0",
  starter: "$29",
  pro: "$149",
};

export const PricingPage = () => {
  const { t, i18n } = useTranslation();
  const { formatNumber } = useFormatDate();
  const isEnglish = i18n.language === "en";
  const dispatch = useDispatch();
  const { data: plansData, isLoading: isLoadingPlans } =
    useGetBillingPlansQuery();
  const { data: currentPlan } = useGetBillingPlanQuery();
  const [subscribeToPayment] = useSubscribeToPaymentMutation();
  
  const [processingPlan, setProcessingPlan] = useState<string | null>(null);
  const [pendingPaymentId, setPendingPaymentId] = useState<string | null>(() => {
    // Восстанавливаем pendingPaymentId из localStorage при загрузке
    return localStorage.getItem("pendingPaymentId");
  });

  // Запускаем поллинг если есть ожидающий платеж
  const { status: paymentStatus } = usePaymentPolling(pendingPaymentId);

  // Обрабатываем результат поллинга
  useEffect(() => {
    if (!pendingPaymentId) return;
    if (paymentStatus === "loading") return;

    // Используем setTimeout для асинхронного обновления состояния
    const timer = setTimeout(() => {
      if (paymentStatus === "success") {
        // Инвалидируем все теги Billing для обновления данных
        dispatch(baseApi.util.invalidateTags(["Billing"]));
        toast.success(t("billing.payments.successPage.success"));
        setPendingPaymentId(null);
        setProcessingPlan(null);
        localStorage.removeItem("pendingPaymentId");
      } else if (paymentStatus === "error") {
        toast.error(t("billing.payments.successPage.error"));
        setPendingPaymentId(null);
        setProcessingPlan(null);
        localStorage.removeItem("pendingPaymentId");
      } else if (paymentStatus === "timeout") {
        toast.warning(t("billing.payments.successPage.timeout"));
        setPendingPaymentId(null);
        setProcessingPlan(null);
        localStorage.removeItem("pendingPaymentId");
      }
    }, 0);

    return () => clearTimeout(timer);
  }, [paymentStatus, pendingPaymentId, t, dispatch]);

  const handleUpgrade = async (plan: PlanInfo) => {
    // Для бизнес-плана оставляем редирект на Telegram
    if (plan.plan === "business") {
      window.open(getCommunityLinks(i18n.language).support, "_blank");
      return;
    }
    
    // Для FREE плана ничего не делаем
    if (plan.plan === "free") {
      return;
    }

    // Для остальных планов сразу создаем платеж
    setProcessingPlan(plan.plan);
    try {
      const response = await subscribeToPayment({
        targetPlan: plan.plan,
        isRecurrent: true, // Всегда включаем автопродление
      }).unwrap();

      // Сохраняем paymentId в localStorage и state
      localStorage.setItem("pendingPaymentId", response.paymentId);
      setPendingPaymentId(response.paymentId);

      // Paddle: open the checkout overlay on the current page.
      const url = new URL(response.paymentUrl);
      const txnId = url.searchParams.get("_ptxn");
      if (!txnId) {
        throw new Error("Missing Paddle transaction id in payment URL");
      }
      openPaddleCheckout(txnId);

      // Поллинг запустится автоматически через useEffect
    } catch (error) {
      console.error("Failed to create payment:", error);
      toast.error(t("billing.payments.confirmDialog.error"));
      setProcessingPlan(null);
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

  return (
    <div className="min-h-full bg-background">
      <main className="container mx-auto px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl space-y-12">
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
          <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-4">
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
                        {plan.plan === "business"
                          ? t("billing.pricing.business.price")
                          : isEnglish
                            ? (USD_PRICES[plan.plan] ?? `$${plan.priceRub}`)
                            : `${formatNumber(plan.priceRub ?? 0)}₽`}
                      </span>
                      {plan.plan !== "business" && plan.plan !== "free" && (
                        <span className="text-sm text-muted-foreground">
                          /{t("billing.pricing.perMonth")}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Features */}
                  <div className="mb-8 flex-1 space-y-4">
                    {plan.plan === "business" ? (
                      <div className="space-y-4">
                        <div className="flex items-start gap-3">
                          <Users className="mt-0.5 h-5 w-5 text-primary" />
                          <div className="flex-1">
                            <p className="font-medium text-foreground">
                              {t(
                                "billing.pricing.business.features.consulting"
                              )}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3">
                          <Zap className="mt-0.5 h-5 w-5 text-primary" />
                          <div className="flex-1">
                            <p className="font-medium text-foreground">
                              {t(
                                "billing.pricing.business.features.integration"
                              )}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3">
                          <Shield className="mt-0.5 h-5 w-5 text-primary" />
                          <div className="flex-1">
                            <p className="font-medium text-foreground">
                              {t("billing.pricing.business.features.sla")}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3">
                          <Building2 className="mt-0.5 h-5 w-5 text-primary" />
                          <div className="flex-1">
                            <p className="font-medium text-foreground">
                              {t("billing.pricing.business.features.onpremise")}
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <>
                        {/* Agents */}
                        <div className="flex items-start gap-3">
                          <Users className="mt-0.5 h-5 w-5 text-primary" />
                          <div className="flex-1">
                            <p className="font-medium text-foreground">
                              {plan.maxAgents === null
                                ? t("billing.pricing.unlimitedAgents")
                                : t("billing.pricing.agents", {
                                    count: plan.maxAgents,
                                  })}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {t("billing.pricing.agentsDesc")}
                            </p>
                          </div>
                        </div>

                        {/* Credits */}
                        <div className="flex items-start gap-3">
                          <Zap className="mt-0.5 h-5 w-5 text-primary" />
                          <div className="flex-1">
                            <p className="font-medium text-foreground">
                              {formatNumber(plan.creditsPerMonth ?? 0)}{" "}
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

                        {/* Own API Keys */}
                        <div className="flex items-start gap-3">
                          {plan.canUseOwnKeys ? (
                            <Check className="mt-0.5 h-5 w-5 text-success" />
                          ) : (
                            <X className="mt-0.5 h-5 w-5 text-muted-foreground" />
                          )}
                          <div className="flex-1">
                            <p
                              className={`font-medium ${
                                plan.canUseOwnKeys
                                  ? "text-foreground"
                                  : "text-muted-foreground line-through"
                              }`}
                            >
                              {plan.canUseOwnKeys
                                ? t("billing.pricing.unlimitedRequests")
                                : t("billing.pricing.ownApiKeys")}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {plan.canUseOwnKeys
                                ? t("billing.pricing.unlimitedRequestsDesc")
                                : t("billing.pricing.ownApiKeysDesc")}
                            </p>
                          </div>
                        </div>

                        {/* Project Variables */}
                        <div className="flex items-start gap-3">
                          {plan.hasProjectVariables ? (
                            <Check className="mt-0.5 h-5 w-5 text-success" />
                          ) : (
                            <X className="mt-0.5 h-5 w-5 text-muted-foreground" />
                          )}
                          <div className="flex-1">
                            <p
                              className={`font-medium ${
                                plan.hasProjectVariables
                                  ? "text-foreground"
                                  : "text-muted-foreground line-through"
                              }`}
                            >
                              {t("billing.pricing.projectVariables")}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {t("billing.pricing.projectVariablesDesc")}
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
                              {plan.supportLevel
                                ? t(
                                    `billing.pricing.support.${plan.supportLevel}`
                                  )
                                : t("billing.pricing.support.community")}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {plan.supportLevel
                                ? t(
                                    `billing.pricing.supportDesc.${plan.supportLevel}`
                                  )
                                : t("billing.pricing.supportDesc.community")}
                            </p>
                          </div>
                        </div>
                      </>
                    )}
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
                    ) : plan.plan === "business" ? (
                      t("billing.pricing.contactSales")
                    ) : (
                      t("billing.pricing.subscribe")
                    )}
                  </Button>
                </div>
              );
            })}
          </div>

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