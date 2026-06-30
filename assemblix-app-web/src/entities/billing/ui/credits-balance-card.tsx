// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import { Coins, Calendar, TrendingUp } from "lucide-react";
import { Progress } from "@/shared/ui/progress";
import { calculateUsageStatus } from "../index";

interface CreditsBalanceCardProps {
  creditsBalance: number;
  creditsPerMonth: number;
  nextResetDate: string;
  className?: string;
}

export const CreditsBalanceCard = ({
  creditsBalance,
  creditsPerMonth,
  nextResetDate,
  className = "",
}: CreditsBalanceCardProps) => {
  const { t } = useTranslation();
  const { formatLongDate, formatNumber } = useFormatDate();

  // Безопасные значения с проверкой на undefined/null
  const safeCreditsBalance = creditsBalance ?? 0;
  const safeCreditsPerMonth = creditsPerMonth ?? 0;

  // Вычисляем использованные кредиты
  const creditsUsed = safeCreditsPerMonth - safeCreditsBalance;
  const { percentage, color } = calculateUsageStatus(
    creditsUsed,
    safeCreditsPerMonth
  );

  const colorClasses = {
    success: "text-success",
    warning: "text-warning",
    destructive: "text-destructive",
  };

  const progressColorClasses = {
    success: "[&>div]:bg-success",
    warning: "[&>div]:bg-warning",
    destructive: "[&>div]:bg-destructive",
  };

  // Форматируем дату следующего пополнения
  const formatNextResetDate = (dateString: string) => {
    if (!dateString) return t("billing.credits.dateUnknown");
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return t("billing.credits.dateUnknown");
    return formatLongDate(date);
  };

  return (
    <div className={`rounded-lg border border-border bg-card p-6 ${className}`}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
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
        {percentage >= 80 && (
          <span className={`text-xs font-semibold ${colorClasses[color]}`}>
            {Math.round(percentage)}%
          </span>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {t("billing.credits.used")}
          </span>
          <span className="font-medium text-foreground">
            {formatNumber(creditsUsed)} /{" "}
            {formatNumber(safeCreditsPerMonth)}
          </span>
        </div>

        <Progress
          value={percentage}
          className={`h-2 ${progressColorClasses[color]}`}
        />
      </div>

      {percentage >= 80 && (
        <div className="mt-4 flex items-start gap-2 rounded-md bg-muted/50 p-3">
          <TrendingUp className="mt-0.5 h-4 w-4 text-warning" />
          <p className="text-xs text-muted-foreground">
            {percentage >= 95
              ? t("billing.criticalUsage")
              : t("billing.highUsage")}
          </p>
        </div>
      )}

      <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Calendar className="h-4 w-4" />
        <span>
          {t("billing.credits.nextRefill")}:{" "}
          {formatNextResetDate(nextResetDate)}
        </span>
      </div>
    </div>
  );
};