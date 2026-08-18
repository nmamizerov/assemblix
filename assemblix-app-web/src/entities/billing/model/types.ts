// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

export type BillingPlan = "free" | "pro" | "business";

export interface CreditsInfo {
  creditsBalance: number;
  creditsGranted: number;
  creditsPurchased: number;
  plan: string;
  creditsPerMonth: number;
  periodStart: string; // ISO 8601 date
  nextReset: string; // ISO 8601 date
}

export interface LimitsInfo {
  rpmLimit: number;
  concurrentCalls: number;
}

export interface BillingUsageResponse {
  organizationId: string;
  plan: BillingPlan;
  billingPeriodStart: string; // ISO 8601 datetime

  credits: CreditsInfo;
  limits: LimitsInfo;
}

export interface PlanInfo {
  plan: BillingPlan;
  name: string; // "Free", "Pro", "Business"
  priceUsdCents: number;
  creditsPerMonth: number;
  supportLevel: string;
  rpmLimit: number;
  concurrentCalls: number;
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

export type CreditsInfoResponse = CreditsInfo;

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

// One-off credit packs
export interface CreditPack {
  code: string;
  priceUsdCents: number;
  credits: number;
}

export interface CreditPacksResponse {
  packs: CreditPack[];
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

export interface PurchaseCreditPackRequest {
  packCode: string;
}

export interface SubscribeResponse {
  paymentId: string;
  paymentUrl: string;
  amount: number;
  amountUsdCents: number;
  description: string;
  targetPlan: string | null;
  expiresAt: string;
}

export interface PaymentStatusResponse {
  paymentId: string;
  status: PaymentStatus;
  amount: number;
  description: string;
  targetPlan: string | null;
  paymentUrl: string | null;
  createdAt: string;
  updatedAt: string;
}
