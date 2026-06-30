// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { baseApi } from "@/shared/api/baseApi";
import type {
  BillingUsageResponse,
  PlanInfo,
  AllPlansResponse,
  CreditsInfoResponse,
  TransactionsResponse,
  TransactionsQueryParams,
  SubscribeRequest,
  SubscribeResponse,
  PaymentStatusResponse,
} from "../model/types";

export const billingApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getBillingUsage: build.query<BillingUsageResponse, string | void>({
      query: (organizationId) => ({
        url: organizationId
          ? `/billing/usage?organization_id=${organizationId}`
          : "/billing/usage",
        method: "GET",
      }),
      providesTags: ["Billing"],
    }),
    getBillingPlan: build.query<PlanInfo, string | void>({
      query: (organizationId) => ({
        url: organizationId
          ? `/billing/plan?organization_id=${organizationId}`
          : "/billing/plan",
        method: "GET",
      }),
      providesTags: ["Billing"],
    }),
    getBillingPlans: build.query<AllPlansResponse, void>({
      query: () => ({
        url: "/billing/plans",
        method: "GET",
      }),
    }),
    getCredits: build.query<CreditsInfoResponse, string | void>({
      query: (organizationId) => ({
        url: organizationId
          ? `/billing/credits?organization_id=${organizationId}`
          : "/billing/credits",
        method: "GET",
      }),
      providesTags: ["Billing"],
    }),
    getTransactions: build.query<
      TransactionsResponse,
      TransactionsQueryParams & { organizationId?: string }
    >({
      query: ({ organizationId, skip, limit, transactionType, fromDate, toDate }) => {
        const params = new URLSearchParams();
        if (organizationId) params.append("organization_id", organizationId);
        if (skip !== undefined) params.append("skip", skip.toString());
        if (limit !== undefined) params.append("limit", limit.toString());
        if (transactionType) params.append("transaction_type", transactionType);
        if (fromDate) params.append("from_date", fromDate);
        if (toDate) params.append("to_date", toDate);

        return {
          url: `/billing/credits/transactions?${params.toString()}`,
          method: "GET",
        };
      },
      providesTags: ["Billing"],
    }),
    subscribeToPayment: build.mutation<SubscribeResponse, SubscribeRequest>({
      query: (body) => ({
        url: "/payments/subscribe",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Billing"],
    }),
    getPaymentStatus: build.query<PaymentStatusResponse, string>({
      query: (paymentId) => ({
        url: `/payments/${paymentId}/status`,
        method: "GET",
      }),
    }),
  }),
});

export const {
  useGetBillingUsageQuery,
  useGetBillingPlanQuery,
  useGetBillingPlansQuery,
  useGetCreditsQuery,
  useGetTransactionsQuery,
  useSubscribeToPaymentMutation,
  useGetPaymentStatusQuery,
} = billingApi;