import { Info, Search } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ExecutionsList } from "@/entities/execution";
import { Input } from "@/shared/ui/input";

interface ExecutionsPageProps {
  includeDebug?: boolean;
}

export const ExecutionsPage = ({
  includeDebug = false,
}: ExecutionsPageProps) => {
  const { t } = useTranslation();
  const [clientIdFilter, setClientIdFilter] = useState("");

  return (
    <div className="flex flex-col gap-4">
      {/* Информационная плашка */}
      <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-950/30">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-indigo-600 dark:text-indigo-400 mt-0.5 shrink-0" />
          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold text-indigo-900 dark:text-indigo-100">
              {t("executions.infoBanner.title")}
            </h3>
            <p className="text-sm text-indigo-700 dark:text-indigo-300">
              {t("executions.infoBanner.description")}
            </p>
          </div>
        </div>
      </div>

      {/* Фильтр по Client ID */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder={t("executions.filterByClientId")}
          value={clientIdFilter}
          onChange={(e) => setClientIdFilter(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Список вызовов */}
      <ExecutionsList
        includeDebug={includeDebug}
        clientId={clientIdFilter || undefined}
      />
    </div>
  );
};
