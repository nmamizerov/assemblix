// SPDX-License-Identifier: LicenseRef-Assemblix-EE
// Assemblix Enterprise — commercially-licensed file. NOT covered by the project's
// MIT + Commons Clause license. Governed by LICENSE_EE.md; running or distributing
// it requires a valid commercial agreement with the copyright holder.

import { useFormatDate } from "@/shared/lib/format-date";

interface UsageProgressCardProps {
  title: string;
  value: number;
  description?: string;
  icon?: React.ReactNode;
  className?: string;
}

/** A flat plan-limit stat: no plan caps how much you can build anymore, so
 *  there is nothing left to show as a current-vs-limit progress bar — just
 *  the cap itself (RPM, concurrent calls). */
export const UsageProgressCard = ({
  title,
  value,
  description,
  icon,
  className = "",
}: UsageProgressCardProps) => {
  const { formatNumber } = useFormatDate();

  return (
    <div className={`rounded-lg border border-border bg-card p-4 ${className}`}>
      <div className="mb-3 flex items-center gap-2">
        {icon && <div className="text-muted-foreground">{icon}</div>}
        <h3 className="text-sm font-medium text-foreground">{title}</h3>
      </div>

      <span className="text-2xl font-bold text-foreground">
        {formatNumber(value)}
      </span>

      {description && (
        <p className="mt-2 text-xs text-muted-foreground">{description}</p>
      )}
    </div>
  );
};
