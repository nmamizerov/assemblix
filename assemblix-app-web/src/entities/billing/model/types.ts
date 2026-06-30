// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

export type BillingPlan = "free" | "starter" | "pro" | "business";

export interface BillingUsageResponse {
  organizationId: string;
  plan: BillingPlan;
  billingPeriodStart: string; // ISO 8601 datetime

  usage: {
    agents: {
      current: number;
      limit: number | null; // null means unlimited
    };
  };

  credits: {
    creditsBalance: number;
    plan: string;
    creditsPerMonth: number;
    periodStart: string; // ISO 8601 date
    nextResetDate: string; // ISO 8601 date
  };

  features: {
    projectVariables: boolean;
    canUseOwnKeys: boolean;
  };

  limits: {
    rpm_limit: number;
  };
}

export interface PlanInfo {
  plan: BillingPlan;
  name: string; // "Free", "Starter", "Pro", "Business"
  priceRub: number;
  maxAgents: number | null; // null = unlimited
  creditsPerMonth: number;
  hasProjectVariables: boolean;
  canUseOwnKeys: boolean;
  supportLevel: string;
  rpmLimit: number;
}

export interface AllPlansResponse {
  plans: PlanInfo[];
}

// Utility type for usage percentage calculation
export interface UsageStatus {
  current: number;
  limit: number | null;
  percentage: number;
  color: "success" | "warning" | "destructive";
  isUnlimited: boolean;
}

// Credits and transactions types
export type TransactionType =
  | "plan_grant"
  | "llm_usage"
  | "request_fee"
  | "manual_topup"
  | "refund";

export interface CreditTransaction {
  id: string;
  amountCredits: number;
  type: TransactionType;
  executionId?: string;
  description: string;
  metadata?: Record<string, unknown>;
  createdAt: string;
}

export interface CreditsInfoResponse {
  creditsBalance: number;
  plan: string;
  creditsPerMonth: number;
  periodStart: string;
  nextResetDate: string;
}

export interface TransactionsQueryParams {
  skip?: number;
  limit?: number;
  transactionType?: TransactionType;
  fromDate?: string;
  toDate?: string;
}

export interface TransactionsResponse {
  data: CreditTransaction[];
  total: number;
  page: number;
  limit: number;
}

// Payment types
export type PaymentStatus =
  | "init"
  | "new"
  | "form_showed"
  | "authorized"
  | "confirmed"
  | "rejected"
  | "refunded"
  | "canceled";

export interface SubscribeRequest {
  targetPlan: BillingPlan;
  isRecurrent?: boolean;
}

export interface SubscribeResponse {
  paymentId: string;
  paymentUrl: string;
  amount: number;
  amountRub: number;
  description: string;
  targetPlan: BillingPlan;
  expiresAt: string;
}

export interface PaymentStatusResponse {
  paymentId: string;
  status: PaymentStatus;
  amount: number;
  description: string;
  targetPlan: BillingPlan;
  paymentUrl: string | null;
  createdAt: string;
  updatedAt: string;
}