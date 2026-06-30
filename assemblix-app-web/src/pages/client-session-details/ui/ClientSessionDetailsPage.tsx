import { useState } from "react";
import { useSelector } from "react-redux";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Loader2,
  ArrowLeft,
  Coins,
  Calendar,
  Activity,
  Trash2,
  Edit3,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  useGetClientSessionQuery,
  useGetClientSessionExecutionsQuery,
  useGetClientSessionChatSessionsQuery,
  useUpdateClientSessionMetadataMutation,
  useDeactivateClientSessionMutation,
} from "@/entities/client-session";
import { selectCurrentProjectId } from "@/entities/organization";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/shared/ui/tabs";
import { Button } from "@/shared/ui/button";
import { JsonViewer } from "@/shared/ui/json-viewer";
import { Textarea } from "@/shared/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Pagination } from "@/shared/ui";
import { toast } from "sonner";
import { cn } from "@/shared/lib/utils";
import { useFormatDate } from "@/shared/lib/format-date";

export const ClientSessionDetailsPage = () => {
  const { t } = useTranslation();
  const { formatDateTime, formatNumber } = useFormatDate();
  const { clientId, projectId } = useParams<{ clientId: string; projectId: string }>();
  const navigate = useNavigate();
  const currentProjectId = useSelector(selectCurrentProjectId);
  const [activeTab, setActiveTab] = useState("overview");
  const [executionsPage, setExecutionsPage] = useState(1);
  const [chatsPage, setChatsPage] = useState(1);
  const [editMetadataOpen, setEditMetadataOpen] = useState(false);
  const [deactivateDialogOpen, setDeactivateDialogOpen] = useState(false);
  const [metadataJson, setMetadataJson] = useState("");
  const [metadataError, setMetadataError] = useState("");

  const { data: session, isLoading: sessionLoading } = useGetClientSessionQuery(
    {
      projectId: currentProjectId!,
      clientId: decodeURIComponent(clientId!),
    },
    { skip: !currentProjectId || !clientId }
  );

  const { data: executionsData, isLoading: executionsLoading } =
    useGetClientSessionExecutionsQuery(
      {
        projectId: currentProjectId!,
        clientId: decodeURIComponent(clientId!),
        page: executionsPage,
        limit: 10,
      },
      { skip: !currentProjectId || !clientId || activeTab !== "executions" }
    );

  const { data: chatsData, isLoading: chatsLoading } =
    useGetClientSessionChatSessionsQuery(
      {
        projectId: currentProjectId!,
        clientId: decodeURIComponent(clientId!),
        page: chatsPage,
        limit: 10,
      },
      { skip: !currentProjectId || !clientId || activeTab !== "chatSessions" }
    );

  const [updateMetadata, { isLoading: isUpdating }] =
    useUpdateClientSessionMetadataMutation();
  const [deactivateSession, { isLoading: isDeactivating }] =
    useDeactivateClientSessionMutation();

  const formatDate = (dateString: string | null) => {
    if (!dateString) return t("clientSessions.never");
    return formatDateTime(dateString);
  };

  const handleEditMetadata = () => {
    setMetadataJson(JSON.stringify(session?.metadata || {}, null, 2));
    setMetadataError("");
    setEditMetadataOpen(true);
  };

  const handleSaveMetadata = async () => {
    try {
      const parsed = JSON.parse(metadataJson);
      await updateMetadata({
        projectId: currentProjectId!,
        clientId: decodeURIComponent(clientId!),
        data: { metadata: parsed },
      }).unwrap();
      toast.success(t("clientSessions.metadataUpdated"));
      setEditMetadataOpen(false);
    } catch (err) {
      if (err instanceof SyntaxError) {
        setMetadataError(t("clientSessions.invalidJson"));
      } else {
        toast.error(t("clientSessions.updateError"));
      }
    }
  };

  const handleDeactivate = async () => {
    try {
      await deactivateSession({
        projectId: currentProjectId!,
        clientId: decodeURIComponent(clientId!),
      }).unwrap();
      toast.success(t("clientSessions.deactivateSuccess"));
      navigate(`/projects/${projectId}/client-sessions`);
    } catch {
      toast.error(t("clientSessions.deactivateError"));
    }
  };

  if (sessionLoading || !session) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const executions = executionsData?.data || [];
  const executionsTotalPages = executionsData
    ? Math.ceil(executionsData.total / 10)
    : 0;

  const chats = chatsData?.data || [];
  const chatsTotalPages = chatsData ? Math.ceil(chatsData.total / 10) : 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to={`/projects/${projectId}/client-sessions`}>
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              {session.clientId}
            </h1>
            <p className="text-sm text-muted-foreground">
              {t("clientSessions.details")}
            </p>
          </div>
        </div>
        {session.isActive && (
          <Button
            variant="destructive"
            onClick={() => setDeactivateDialogOpen(true)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            {t("clientSessions.deactivate")}
          </Button>
        )}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">
            {t("clientSessions.tabs.overview")}
          </TabsTrigger>
          <TabsTrigger value="state">
            {t("clientSessions.tabs.state")}
          </TabsTrigger>
          <TabsTrigger value="metadata">
            {t("clientSessions.tabs.metadata")}
          </TabsTrigger>
          <TabsTrigger value="executions">
            {t("clientSessions.tabs.executions")}
          </TabsTrigger>
          <TabsTrigger value="chatSessions">
            {t("clientSessions.tabs.chatSessions")}
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Activity className="h-4 w-4" />
                {t("clientSessions.executions")}
              </div>
              <div className="mt-2 text-2xl font-bold">
                {session.executionCount}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Coins className="h-4 w-4" />
                {t("clientSessions.credits")}
              </div>
              <div className="mt-2 text-2xl font-bold">
                {formatNumber(session.totalCredits ?? 0)}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Calendar className="h-4 w-4" />
                {t("clientSessions.status")}
              </div>
              <div className="mt-2">
                {session.isActive ? (
                  <div
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                      "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                    )}
                  >
                    <CheckCircle2 className="h-3 w-3" />
                    {t("clientSessions.active")}
                  </div>
                ) : (
                  <div
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                      "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400"
                    )}
                  >
                    <XCircle className="h-3 w-3" />
                    {t("clientSessions.inactive")}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-6">
            <h3 className="mb-4 font-semibold">
              {t("clientSessions.information")}
            </h3>
            <dl className="grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-sm font-medium text-muted-foreground">
                  {t("clientSessions.createdAt")}
                </dt>
                <dd className="mt-1 text-sm">
                  {formatDate(session.createdAt)}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">
                  {t("clientSessions.updatedAt")}
                </dt>
                <dd className="mt-1 text-sm">
                  {formatDate(session.updatedAt)}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">
                  {t("clientSessions.lastActivity")}
                </dt>
                <dd className="mt-1 text-sm">
                  {formatDate(session.lastActivityAt)}
                </dd>
              </div>
            </dl>
          </div>
        </TabsContent>

        {/* State Tab */}
        <TabsContent value="state" className="space-y-4">
          <div className="rounded-lg border border-border bg-card p-6">
            <h3 className="mb-4 font-semibold">
              {t("clientSessions.projectState")}
            </h3>
            <JsonViewer data={session.state} />
          </div>
        </TabsContent>

        {/* Metadata Tab */}
        <TabsContent value="metadata" className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-border bg-card p-4">
            <h3 className="font-semibold">{t("clientSessions.metadata")}</h3>
            <Button onClick={handleEditMetadata} size="sm">
              <Edit3 className="mr-2 h-4 w-4" />
              {t("clientSessions.editMetadata")}
            </Button>
          </div>
          <div className="rounded-lg border border-border bg-card p-6">
            <JsonViewer data={session.metadata} />
          </div>
        </TabsContent>

        {/* Executions Tab */}
        <TabsContent value="executions" className="space-y-4">
          {executionsLoading ? (
            <div className="flex h-32 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : executions.length === 0 ? (
            <div className="flex min-h-[200px] items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-center">
              <p className="text-sm text-muted-foreground">
                {t("clientSessions.noExecutions")}
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-2">
                {executions.map((execution) => (
                  <Link
                    key={execution.id}
                    to={`/projects/${projectId}/workflows/${execution.workflowId}/executions/${execution.id}`}
                    className="block rounded-lg border border-border bg-card p-4 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium">
                          {execution.workflow.name}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {formatDate(execution.startedAt)}
                        </div>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <div className="flex items-center gap-1">
                          <Coins className="h-3.5 w-3.5" />
                          {formatNumber(execution.totalCredits ?? 0)}
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
              {executionsTotalPages > 1 && (
                <Pagination
                  currentPage={executionsPage}
                  totalPages={executionsTotalPages}
                  onPageChange={setExecutionsPage}
                />
              )}
            </>
          )}
        </TabsContent>

        {/* Chat Sessions Tab */}
        <TabsContent value="chatSessions" className="space-y-4">
          {chatsLoading ? (
            <div className="flex h-32 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : chats.length === 0 ? (
            <div className="flex min-h-[200px] items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-center">
              <p className="text-sm text-muted-foreground">
                {t("clientSessions.noChatSessions")}
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-2">
                {chats.map((chat) => (
                  <Link
                    key={chat.id}
                    to={`/projects/${projectId}/chats/${chat.id}`}
                    className="block rounded-lg border border-border bg-card p-4 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium">
                          {t("chats.title")} #{chat.id.slice(0, 8)}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {formatDate(chat.createdAt)}
                        </div>
                      </div>
                      <div
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                          chat.isActive
                            ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                            : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400"
                        )}
                      >
                        {chat.isActive
                          ? t("chats.active")
                          : t("chats.inactive")}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
              {chatsTotalPages > 1 && (
                <Pagination
                  currentPage={chatsPage}
                  totalPages={chatsTotalPages}
                  onPageChange={setChatsPage}
                />
              )}
            </>
          )}
        </TabsContent>
      </Tabs>

      {/* Edit Metadata Dialog */}
      <Dialog open={editMetadataOpen} onOpenChange={setEditMetadataOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t("clientSessions.editMetadata")}</DialogTitle>
            <DialogDescription>
              {t("clientSessions.editMetadataDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Textarea
              value={metadataJson}
              onChange={(e) => setMetadataJson(e.target.value)}
              rows={15}
              className="font-mono text-sm"
            />
            {metadataError && (
              <p className="text-sm text-red-600 dark:text-red-400">
                {metadataError}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setEditMetadataOpen(false)}
              disabled={isUpdating}
            >
              {t("common.cancel")}
            </Button>
            <Button onClick={handleSaveMetadata} disabled={isUpdating}>
              {isUpdating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t("common.saving")}
                </>
              ) : (
                t("common.save")
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Deactivate Dialog */}
      <Dialog
        open={deactivateDialogOpen}
        onOpenChange={setDeactivateDialogOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("clientSessions.deactivateConfirm")}</DialogTitle>
            <DialogDescription>
              {t("clientSessions.deactivateWarning")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setDeactivateDialogOpen(false)}
              disabled={isDeactivating}
            >
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeactivate}
              disabled={isDeactivating}
            >
              {isDeactivating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t("common.deleting")}
                </>
              ) : (
                t("clientSessions.deactivate")
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
