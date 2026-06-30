// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { Crown } from "lucide-react";
import type { BillingPlan } from "../model/types";

interface PlanBadgeProps {
  plan: BillingPlan;
  showIcon?: boolean;
  className?: string;
}

export const PlanBadge = ({
  plan,
  showIcon = true,
  className = "",
}: PlanBadgeProps) => {
  const planColors = {
    free: "bg-muted text-muted-foreground",
    starter: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
    pro: "bg-primary/10 text-primary",
    business: "bg-warning/10 text-warning",
  };

  const planNames = {
    free: "FREE",
    starter: "STARTER",
    pro: "PRO",
    business: "BUSINESS",
  };

  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${planColors[plan]} ${className}`}
    >
      {showIcon && plan !== "free" && <Crown className="h-3.5 w-3.5" />}
      {planNames[plan]}
    </div>
  );
};