import { Loader2, User, Bot, ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Markdown } from "@/shared/ui/markdown";
import { useGetChatSessionDetailQuery } from "@/entities/chat-session";
import type { Message } from "@/entities/chat-session";
import { Button } from "@/shared/ui/button";
import { useFormatDate } from "@/shared/lib/format-date";
import { useEffect, useRef } from "react";

interface ChatDetailPanelProps {
  chatSessionId: string;
  onExecutionClick?: (executionId: string) => void;
  compact?: boolean;
}

export const ChatDetailPanel = ({
  chatSessionId,
  onExecutionClick,
  compact = false,
}: ChatDetailPanelProps) => {
  const { t } = useTranslation();
  const { formatShortDateTime, formatLongDateTime, formatNumber } = useFormatDate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: chatSession, isLoading } = useGetChatSessionDetailQuery(
    chatSessionId || "",
  );

  // Автоскролл к последнему сообщению
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatSession?.messages]);

  const formatMessageTime = (dateString: string) => formatShortDateTime(dateString);

  const renderMessage = (message: Message) => {
    const isUser = message.role === "user";

    return (
      <div
        key={message.id}
        className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
      >
        {/* Аватар */}
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </div>

        {/* Сообщение */}
        <div
          className={`flex max-w-[70%] flex-col gap-1 ${
            isUser ? "items-end" : "items-start"
          }`}
        >
          <div
            className={`rounded-2xl px-4 py-2 ${
              isUser
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-foreground"
            }`}
          >
            {isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-relaxed wrap-break-word">
              {message.content}
            </p>
            ) : (
              <Markdown content={message.content} />
            )}
          </div>
          <div className="flex items-center gap-2 px-2">
            <span className="text-xs text-muted-foreground">
              {formatMessageTime(message.createdAt)}
            </span>
            {!isUser && message.executionId && onExecutionClick && (
              <>
                <span className="text-xs text-muted-foreground">•</span>
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-xs text-primary hover:text-primary/80"
                  onClick={() => onExecutionClick(message.executionId!)}
                >
                  <ExternalLink className="h-3 w-3 mr-1" />
                  {t("chatDetails.goToExecution")}
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!chatSession) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">{t("chatDetails.notFound")}</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Заголовок чата */}
      {!compact && (
        <div className="border-b border-border bg-card p-4">
          <h2 className="text-lg font-semibold text-foreground">
            {t("chatDetails.title")}{" "}
            {formatLongDateTime(chatSession.createdAt)}
          </h2>
          <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
            <span>
              {chatSession.messageCount} {t("chats.messages")}
            </span>
            <span>•</span>
            <span>
              {formatNumber(chatSession.totalCredits ?? 0)}{" "}
              {t("chatDetails.credits")}
            </span>
          </div>
        </div>
      )}

      {/* Список сообщений */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-6">
          {chatSession.messages.length === 0 ? (
            <div className="flex min-h-[200px] items-center justify-center">
              <p className="text-sm text-muted-foreground">
                {t("chatDetails.noMessages")}
              </p>
            </div>
          ) : (
            <>
              {chatSession.messages.map(renderMessage)}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </div>
    </div>
  );
};
