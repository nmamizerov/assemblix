// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import { TrendingUp, Infinity as InfinityIcon } from "lucide-react";
import { calculateUsageStatus } from "../index";
import { Progress } from "@/shared/ui/progress";

interface UsageProgressCardProps {
  title: string;
  current: number;
  limit: number | null;
  icon?: React.ReactNode;
  className?: string;
}

export const UsageProgressCard = ({
  title,
  current,
  limit,
  icon,
  className = "",
}: UsageProgressCardProps) => {
  const { t } = useTranslation();
  const { formatNumber } = useFormatDate();
  const { percentage, color, isUnlimited } = calculateUsageStatus(
    current,
    limit
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

  return (
    <div className={`rounded-lg border border-border bg-card p-4 ${className}`}>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon && <div className="text-muted-foreground">{icon}</div>}
          <h3 className="text-sm font-medium text-foreground">{title}</h3>
        </div>
        {!isUnlimited && (
          <span className={`text-xs font-semibold ${colorClasses[color]}`}>
            {Math.round(percentage)}%
          </span>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-baseline justify-between">
          <span className="text-2xl font-bold text-foreground">
            {formatNumber(current)}
          </span>
          {isUnlimited ? (
            <div className="flex items-center gap-1 text-sm text-muted-foreground">
              <InfinityIcon className="h-4 w-4" />
              <span>{t("billing.unlimited")}</span>
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">
              / {formatNumber(limit!)}
            </span>
          )}
        </div>

        {!isUnlimited && (
          <Progress
            value={percentage}
            className={`h-2 ${progressColorClasses[color]}`}
          />
        )}
      </div>

      {!isUnlimited && percentage >= 80 && (
        <div className="mt-3 flex items-start gap-2 rounded-md bg-muted/50 p-2">
          <TrendingUp className="mt-0.5 h-3.5 w-3.5 text-warning" />
          <p className="text-xs text-muted-foreground">
            {percentage >= 95
              ? t("billing.criticalUsage")
              : t("billing.highUsage")}
          </p>
        </div>
      )}
    </div>
  );
};