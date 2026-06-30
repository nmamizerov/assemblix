// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import {
  Gift,
  Bot,
  Send,
  DollarSign,
  RotateCcw,
  ArrowRight,
  Coins,
} from "lucide-react";
import type { CreditTransaction, TransactionType } from "../model/types";
import { Button } from "@/shared/ui/button";
import clsx from "clsx";

interface CreditsTransactionsListProps {
  transactions: CreditTransaction[];
  showViewAll?: boolean;
  onViewAll?: () => void;
  className?: string;
  total?: number;
  footer?: React.ReactNode;
}

const getTransactionIcon = (type: TransactionType) => {
  const icons = {
    plan_grant: Gift,
    llm_usage: Bot,
    request_fee: Send,
    manual_topup: DollarSign,
    refund: RotateCcw,
  };
  return icons[type] || Send;
};

export const CreditsTransactionsList = ({
  transactions,
  showViewAll = false,
  onViewAll,
  className = "",
  total,
  footer,
}: CreditsTransactionsListProps) => {
  const { t } = useTranslation();
  const { formatShortDateTime, formatNumber } = useFormatDate();

  const formatDate = (dateString: string) => formatShortDateTime(dateString);

  if (transactions.length === 0) {
    return (
      <div
        className={`rounded-lg border border-border bg-card p-6 ${className}`}
      >
        <h3 className="mb-4 text-lg font-semibold text-foreground">
          {t("billing.credits.transactions")}
        </h3>
        <p className="text-center text-sm text-muted-foreground">
          {t("billing.credits.noTransactions")}
        </p>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border border-border bg-card ${className}`}>
      <div className="border-b border-border p-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              {t("billing.credits.transactions")}
            </h3>
            {total !== undefined && (
              <p className="mt-1 text-sm text-muted-foreground">
                {t("billing.credits.totalTransactions")}: {formatNumber(total)}
              </p>
            )}
          </div>
          {showViewAll && onViewAll && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onViewAll}
              className="text-sm"
            >
              {t("billing.credits.viewAll")}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <div className="divide-y divide-border">
        {transactions.map((transaction) => {
          const Icon = getTransactionIcon(transaction.type);
          const isPositive = (transaction.amountCredits || 0) > 0;

          return (
            <div
              key={transaction.id}
              className="flex items-center justify-between p-4 transition-colors hover:bg-muted/50"
            >
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-full ${
                    isPositive ? "bg-success/10" : "bg-muted"
                  }`}
                >
                  <Icon
                    className={`h-5 w-5 ${
                      isPositive ? "text-success" : "text-muted-foreground"
                    }`}
                  />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {t(
                      `billing.credits.transactionTypes.${transaction.type}` as const
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(transaction.createdAt)}
                  </p>
                  {transaction.description && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {transaction.description}
                    </p>
                  )}
                </div>
              </div>

              <div className="text-right">
                <p
                  className={`flex items-center gap-1 text-lg font-semibold ${
                    isPositive ? "text-success" : "text-destructive"
                  }`}
                >
                  <Coins
                    className={clsx(
                      "h-4 w-4",
                      isPositive ? "text-success" : "text-destructive"
                    )}
                  />
                  {isPositive ? "+" : ""}
                  {formatNumber(transaction.amountCredits ?? 0)}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {footer && <div className="border-t border-border">{footer}</div>}
    </div>
  );
};