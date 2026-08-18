// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

export {
  billingApi,
  useGetBillingUsageQuery,
  useGetBillingPlanQuery,
  useGetBillingPlansQuery,
  useGetBillingPacksQuery,
  useGetCreditsQuery,
  useGetTransactionsQuery,
  useSubscribeToPaymentMutation,
  usePurchaseCreditPackMutation,
  useGetPaymentStatusQuery,
} from "./api/billing.api";

export type {
  BillingPlan,
  BillingUsageResponse,
  CreditsInfo,
  LimitsInfo,
  PlanInfo,
  AllPlansResponse,
  UsageStatus,
  CreditTransaction,
  TransactionType,
  CreditsInfoResponse,
  CreditPack,
  CreditPacksResponse,
  TransactionsResponse,
  TransactionsQueryParams,
  PaymentStatus,
  SubscribeRequest,
  PurchaseCreditPackRequest,
  SubscribeResponse,
  PaymentStatusResponse,
} from "./model/types";

export { usePaymentPolling } from "./lib/use-payment-polling";

export { PlanBadge } from "./ui/plan-badge";
export { UsageProgressCard } from "./ui/usage-progress-card";
export { LimitWarningBanner } from "./ui/limit-warning-banner";
export { CreditsBalanceCard } from "./ui/credits-balance-card";
export { CreditsTransactionsList } from "./ui/credits-transactions-list";
export { SubscribeConfirmDialog } from "./ui/subscribe-confirm-dialog";

// Utility function for usage calculation
export const calculateUsageStatus = (
  current: number,
  limit: number | null
): {
  percentage: number;
  color: "success" | "warning" | "destructive";
  isUnlimited: boolean;
} => {
  if (limit === null) {
    return {
      percentage: 0,
      color: "success",
      isUnlimited: true,
    };
  }

  const percentage = (current / limit) * 100;
  let color: "success" | "warning" | "destructive" = "success";

  if (percentage >= 90) {
    color = "destructive";
  } else if (percentage >= 70) {
    color = "warning";
  }

  return {
    percentage,
    color,
    isUnlimited: false,
  };
};