import { useState } from "react";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import {
  Loader2,
  Users,
  Coins,
  Search,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { useGetClientSessionsQuery } from "@/entities/client-session";
import { selectCurrentProjectId } from "@/entities/organization";
import { Input } from "@/shared/ui/input";
import { Pagination } from "@/shared/ui";
import { Label } from "@/shared/ui/label";
import { cn } from "@/shared/lib/utils";
import { useFormatDate } from "@/shared/lib/format-date";

export const ClientSessionsPage = () => {
  const { t } = useTranslation();
  const { formatShortDateTime, formatNumber } = useFormatDate();
  const { projectId } = useParams();
  const [currentPage, setCurrentPage] = useState(1);
  const [activeOnly, setActiveOnly] = useState(false);
  const [includeDebug, setIncludeDebug] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const limit = 50;
  const currentProjectId = useSelector(selectCurrentProjectId);

  const { data, isLoading } = useGetClientSessionsQuery(
    {
      projectId: currentProjectId!,
      page: currentPage,
      limit,
      activeOnly,
      includeDebug,
    },
    { skip: !currentProjectId },
  );

  const formatDate = (dateString: string | null) => {
    if (!dateString) return t("clientSessions.never");
    return formatShortDateTime(dateString);
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const clientSessions = data?.data || [];
  const filteredSessions = searchQuery
    ? clientSessions.filter((session) =>
        session.clientId.toLowerCase().includes(searchQuery.toLowerCase()),
      )
    : clientSessions;

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            {t("clientSessions.title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("clientSessions.subtitle")}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder={t("clientSessions.searchPlaceholder")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="activeOnly"
              checked={activeOnly}
              onChange={(e) => {
                setActiveOnly(e.target.checked);
                setCurrentPage(1);
              }}
              className="h-4 w-4 rounded border-border text-primary focus:ring-2 focus:ring-primary"
            />
            <Label htmlFor="activeOnly" className="cursor-pointer text-sm">
              {t("clientSessions.onlyActive")}
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="includeDebug"
              checked={includeDebug}
              onChange={(e) => {
                setIncludeDebug(e.target.checked);
                setCurrentPage(1);
              }}
              className="h-4 w-4 rounded border-border text-primary focus:ring-2 focus:ring-primary"
            />
            <Label htmlFor="includeDebug" className="cursor-pointer text-sm">
              {t("clientSessions.showTestSessions")}
            </Label>
          </div>
        </div>
      </div>

      {/* Table */}
      {filteredSessions.length === 0 ? (
        <div className="flex min-h-[300px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <Users className="h-8 w-8 text-primary" />
          </div>
          <h3 className="mt-4 text-lg font-semibold">
            {t("clientSessions.noSessions")}
          </h3>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full">
            <thead className="border-b border-border bg-muted/50">
              <tr>
                <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                  {t("clientSessions.clientId")}
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-foreground">
                  {t("clientSessions.lastActivity")}
                </th>
                <th className="px-6 py-4 text-right text-sm font-semibold text-foreground">
                  {t("clientSessions.executions")}
                </th>
                <th className="px-6 py-4 text-right text-sm font-semibold text-foreground">
                  {t("clientSessions.credits")}
                </th>
                <th className="px-6 py-4 text-center text-sm font-semibold text-foreground">
                  {t("clientSessions.status")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredSessions.map((session) => (
                <tr
                  key={session.id}
                  className="transition-colors hover:bg-muted/50"
                >
                  <td className="px-6 py-4">
                    <Link
                      to={`/projects/${projectId}/client-sessions/${encodeURIComponent(
                        session.clientId,
                      )}`}
                      className="font-mono text-sm font-medium text-primary hover:underline"
                    >
                      {session.clientId}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-sm text-muted-foreground">
                    {formatDate(session.lastActivityAt)}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <span className="text-sm font-medium">
                        {session.executionCount}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-1.5 text-muted-foreground">
                      <Coins className="h-3.5 w-3.5" />
                      <span className="text-sm">
                        {formatNumber(session.totalCredits ?? 0)}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-center">
                    {session.isActive ? (
                      <div
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                          "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
                        )}
                      >
                        <CheckCircle2 className="h-3 w-3" />
                        {t("clientSessions.active")}
                      </div>
                    ) : (
                      <div
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                          "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400",
                        )}
                      >
                        <XCircle className="h-3 w-3" />
                        {t("clientSessions.inactive")}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
        />
      )}
    </div>
  );
};
