// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useTranslation } from "react-i18next";
import { Lock, Crown } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { useNavigate } from "react-router-dom";
import type { BillingPlan } from "../model/types";

interface FeatureLockedCardProps {
  featureName: string;
  featureDescription: string;
  requiredPlan: Exclude<BillingPlan, "free">;
  className?: string;
}

export const FeatureLockedCard = ({
  featureName,
  featureDescription,
  requiredPlan,
  className = "",
}: FeatureLockedCardProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const planNames = {
    starter: "STARTER",
    pro: "PRO",
    business: "BUSINESS",
  };

  return (
    <div
      className={`flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/30 p-8 text-center ${className}`}
    >
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <Lock className="h-8 w-8 text-muted-foreground" />
      </div>

      <h3 className="mb-2 text-lg font-semibold text-foreground">
        {featureName}
      </h3>

      <p className="mb-4 max-w-md text-sm text-muted-foreground">
        {featureDescription}
      </p>

      <div className="mb-4 flex items-center gap-2 rounded-full bg-primary/10 px-4 py-2">
        <Crown className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold text-primary">
          {t("billing.availableInPlan", { plan: planNames[requiredPlan] })}
        </span>
      </div>

      <Button onClick={() => navigate("/pricing")} size="lg">
        {t("billing.upgradeToPlan", { plan: planNames[requiredPlan] })}
      </Button>
    </div>
  );
};