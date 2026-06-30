// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useTranslation } from "react-i18next";
import { useFormatDate } from "@/shared/lib/format-date";
import { AlertTriangle, X } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { useNavigate } from "react-router-dom";
import { useState } from "react";

interface LimitWarningBannerProps {
  type: "agents" | "credits";
  current: number;
  limit: number;
  percentage: number;
  dismissible?: boolean;
}

export const LimitWarningBanner = ({
  type,
  current,
  limit,
  percentage,
  dismissible = true,
}: LimitWarningBannerProps) => {
  const { t } = useTranslation();
  const { formatNumber } = useFormatDate();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const isCritical = percentage >= 95;
  const bgColor = isCritical
    ? "bg-destructive/10 border-destructive/30"
    : "bg-warning/10 border-warning/30";

  const textColor = isCritical ? "text-destructive" : "text-warning";

  return (
    <div
      className={`relative flex items-center justify-between gap-4 rounded-lg border p-4 ${bgColor}`}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className={`mt-0.5 h-5 w-5 ${textColor}`} />
        <div className="flex-1">
          <h4 className={`font-semibold ${textColor}`}>
            {isCritical
              ? t(`billing.limitWarning.critical.${type}.title`)
              : t(`billing.limitWarning.warning.${type}.title`)}
          </h4>
          <p className="mt-1 text-sm text-muted-foreground">
            {isCritical
              ? t(`billing.limitWarning.critical.${type}.description`, {
                  current: formatNumber(current),
                  limit: formatNumber(limit),
                  percentage: Math.round(percentage),
                })
              : t(`billing.limitWarning.warning.${type}.description`, {
                  current: formatNumber(current),
                  limit: formatNumber(limit),
                  percentage: Math.round(percentage),
                })}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button onClick={() => navigate("/pricing")} variant="default">
          {t("billing.upgrade")}
        </Button>
        {dismissible && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setDismissed(true)}
            className="h-8 w-8"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
};