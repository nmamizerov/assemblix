import { Loader2, MessageSquare, Coins, Circle, Pencil, Trash2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useState, useRef } from "react";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import {
  useGetChatSessionsQuery,
  useRenameChatSessionMutation,
  useDeleteChatSessionMutation,
} from "@/entities/chat-session";
import { selectCurrentProjectId } from "@/entities/organization";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/shared/ui/dialog";
import { Button } from "@/shared/ui/button";
import { Pagination } from "@/shared/ui";
import { cn } from "@/shared/lib/utils";
import { useFormatDate } from "@/shared/lib/format-date";

interface ChatSessionsListProps {
  workflowId?: string;
  includeDebug?: boolean;
  showInfoBanner?: boolean;
  onItemClick?: (chatId: string) => void;
  selectedId?: string;
}

export const ChatSessionsList = ({
  workflowId,
  includeDebug = false,
  onItemClick,
  selectedId,
}: ChatSessionsListProps) => {
  const { t } = useTranslation();
  const { formatShortDateTime, formatNumber } = useFormatDate();
  const { projectId } = useParams();
  const [currentPage, setCurrentPage] = useState(1);
  const limit = 10;
  const currentProjectId = useSelector(selectCurrentProjectId);

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const renameInputRef = useRef<HTMLInputElement>(null);

  const [renameChatSession, { isLoading: isRenaming }] = useRenameChatSessionMutation();
  const [deleteChatSession, { isLoading: isDeleting }] = useDeleteChatSessionMutation();

  const { data, isLoading } = useGetChatSessionsQuery(
    {
      projectId: currentProjectId!,
      page: currentPage,
      limit,
      includeDebug,
      workflowId,
    },
    { skip: !currentProjectId },
  );

  const handleRenameStart = (e: React.MouseEvent, sessionId: string, currentName: string | null) => {
    e.preventDefault();
    e.stopPropagation();
    setRenamingId(sessionId);
    setRenameValue(currentName ?? "");
    setTimeout(() => renameInputRef.current?.focus(), 0);
  };

  const handleRenameSubmit = async (sessionId: string) => {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed.length >= 1) {
      await renameChatSession({ id: sessionId, name: trimmed });
    }
    setRenamingId(null);
  };

  const handleRenameKeyDown = (e: React.KeyboardEvent, sessionId: string) => {
    if (e.key === "Enter") {
      void handleRenameSubmit(sessionId);
    } else if (e.key === "Escape") {
      setRenamingId(null);
    }
  };

  const handleDeleteStart = (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();
    setDeletingId(sessionId);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingId) return;
    await deleteChatSession(deletingId);
    setDeletingId(null);
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const chatSessions = data?.data || [];

  if (chatSessions.length === 0) {
    return (
      <div className="flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/50 text-center">
        <p className="text-sm text-muted-foreground">
          {workflowId ? t("workflow.agentCalls.noChats") : t("chats.noChats")}
        </p>
      </div>
    );
  }

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Заголовок таблицы */}
      <div className="flex items-center justify-end px-4 pb-2">
        <span className="text-xs text-muted-foreground">
          {t("chats.lastMessage")}
        </span>
      </div>

      {/* Список чатов */}
      <TooltipProvider>
        {chatSessions.map((session) => {
          const lastMessageTime = session.lastMessageAt
            ? formatShortDateTime(session.lastMessageAt)
            : "—";

          const isSelected = selectedId === session.id;
          const isCurrentlyRenaming = renamingId === session.id;
          const displayName = session.name || session.id;

          const content = (
            <div
              className={cn(
                "group flex cursor-pointer items-center justify-between rounded-lg border border-border bg-card px-4 py-3 transition-all duration-200 hover:border-primary/50 hover:shadow-md",
                isSelected && "border-primary bg-primary/5",
              )}
              onClick={
                isCurrentlyRenaming
                  ? undefined
                  : onItemClick
                  ? () => onItemClick(session.id)
                  : undefined
              }
            >
              <div className="flex flex-col gap-3 min-w-0 flex-1 mr-3">
                <div className="flex items-center gap-2">
                  {isCurrentlyRenaming ? (
                    <input
                      ref={renameInputRef}
                      className="text-sm font-medium bg-transparent border-b border-primary outline-none text-card-foreground w-full max-w-xs"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => handleRenameKeyDown(e, session.id)}
                      onBlur={() => void handleRenameSubmit(session.id)}
                      placeholder={t("chats.renamePlaceholder")}
                      onClick={(e) => e.stopPropagation()}
                      disabled={isRenaming}
                    />
                  ) : (
                    <span
                      className="text-sm font-medium text-card-foreground truncate max-w-xs"
                      title={displayName}
                    >
                      {displayName}
                    </span>
                  )}

                  <div
                    className={`flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
                      session.isActive
                        ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                        : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                    }`}
                  >
                    <Circle
                      className={`h-2 w-2 ${
                        session.isActive
                          ? "fill-green-600 dark:fill-green-400"
                          : "fill-gray-400"
                      }`}
                    />
                    {session.isActive ? t("chats.active") : t("chats.inactive")}
                  </div>

                  {/* Кнопки действий — показываются при hover */}
                  {!isCurrentlyRenaming && (
                    <div className="hidden group-hover:flex items-center gap-1 ml-1">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                            onClick={(e) => handleRenameStart(e, session.id, session.name)}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>{t("chats.rename")}</p>
                        </TooltipContent>
                      </Tooltip>

                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            className="rounded p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                            onClick={(e) => handleDeleteStart(e, session.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>{t("chats.delete")}</p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">
                    {session.workflow.name}
                  </span>

                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <MessageSquare className="h-3.5 w-3.5" />
                        <span className="text-xs">{session.messageCount}</span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>
                        {t("chats.messages")}: {session.messageCount}
                      </p>
                    </TooltipContent>
                  </Tooltip>

                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="flex items-center gap-1 text-muted-foreground">
                        <Coins className="h-3.5 w-3.5" />
                        <span className="text-xs">
                          {formatNumber(session.totalCredits ?? 0)}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>
                        {t("chats.credits")}{" "}
                        {formatNumber(session.totalCredits ?? 0)}
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </div>
              </div>

              <span className="text-xs text-muted-foreground shrink-0">
                {lastMessageTime}
              </span>
            </div>
          );

          return onItemClick ? (
            <div key={session.id}>{content}</div>
          ) : (
            <Link
              key={session.id}
              to={`/projects/${projectId}/chats/${session.id}`}
              onClick={(e) => isCurrentlyRenaming && e.preventDefault()}
            >
              {content}
            </Link>
          );
        })}
      </TooltipProvider>

      {/* Пагинация */}
      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={setCurrentPage}
      />

      {/* Диалог подтверждения удаления */}
      <Dialog open={!!deletingId} onOpenChange={(open) => !open && setDeletingId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("chats.deleteTitle")}</DialogTitle>
            <DialogDescription>{t("chats.deleteDescription")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeletingId(null)}
              disabled={isDeleting}
            >
              {t("chats.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={() => void handleDeleteConfirm()}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                t("chats.delete")
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
