// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import { Coins, Calendar, ShoppingBag, Gift } from "lucide-react";

interface CreditsBalanceCardProps {
  creditsBalance: number;
  creditsGranted: number;
  creditsPurchased: number;
  nextReset: string;
  className?: string;
}

/** Shows the balance as one number — that is the whole point of the single-
 *  currency model — with the granted and purchased parts underneath, since
 *  only the granted part expires at the reset date. */
export const CreditsBalanceCard = ({
  creditsBalance,
  creditsGranted,
  creditsPurchased,
  nextReset,
  className = "",
}: CreditsBalanceCardProps) => {
  const { t } = useTranslation();
  const { formatLongDate, formatNumber } = useFormatDate();

  const safeCreditsBalance = creditsBalance ?? 0;
  const safeCreditsGranted = creditsGranted ?? 0;
  const safeCreditsPurchased = creditsPurchased ?? 0;

  const formatNextResetDate = (dateString: string) => {
    if (!dateString) return t("billing.credits.dateUnknown");
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return t("billing.credits.dateUnknown");
    return formatLongDate(date);
  };

  return (
    <div className={`rounded-lg border border-border bg-card p-6 ${className}`}>
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
          <Coins className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h3 className="text-sm font-medium text-muted-foreground">
            {t("billing.credits.balance")}
          </h3>
          <p className="text-2xl font-bold text-foreground">
            {formatNumber(safeCreditsBalance)}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2 text-muted-foreground">
            <Gift className="h-4 w-4" />
            {t("billing.credits.granted")}
          </span>
          <span className="font-medium text-foreground">
            {formatNumber(safeCreditsGranted)}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="flex items-center gap-2 text-muted-foreground">
            <ShoppingBag className="h-4 w-4" />
            {t("billing.credits.purchased")}
          </span>
          <span className="font-medium text-foreground">
            {formatNumber(safeCreditsPurchased)}
          </span>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Calendar className="h-4 w-4" />
        <span>
          {t("billing.credits.nextRefill")}: {formatNextResetDate(nextReset)}
        </span>
      </div>
    </div>
  );
};
