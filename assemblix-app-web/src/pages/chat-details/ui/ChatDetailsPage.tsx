import { useParams, useNavigate } from "react-router-dom";
import { Loader2, ArrowLeft, User, Bot, ExternalLink } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Markdown } from "@/shared/ui/markdown";
import { useGetChatSessionDetailQuery } from "@/entities/chat-session";
import type { Message } from "@/entities/chat-session";
import { Button } from "@/shared/ui/button";
import { useFormatDate } from "@/shared/lib/format-date";
import { useEffect, useRef } from "react";

export const ChatDetailsPage = () => {
  const { t } = useTranslation();
  const { formatShortDateTime, formatLongDateTime, formatNumber } = useFormatDate();
  const { chatId, projectId } = useParams<{ chatId: string; projectId: string }>();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: chatSession, isLoading } = useGetChatSessionDetailQuery(
    chatId || ""
  );

  // Автоскролл к последнему сообщению
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatSession?.messages]);

  if (isLoading) {
    return (
      <div className="min-h-full">
        <div className="flex h-[calc(100vh-80px)] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  if (!chatSession) {
    return (
      <div className="min-h-full">
        <div className="flex h-[calc(100vh-80px)] items-center justify-center">
          <p className="text-muted-foreground">{t("chatDetails.notFound")}</p>
        </div>
      </div>
    );
  }

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
            {!isUser && message.executionId && (
              <>
                <span className="text-xs text-muted-foreground">•</span>
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto p-0 text-xs text-primary hover:text-primary/80"
                  onClick={() =>
                    navigate(
                      `/projects/${projectId}/workflows/${chatSession?.workflowId}/executions/${message.executionId}`,
                      { state: { from: `/projects/${projectId}/chats/${chatId}` } }
                    )
                  }
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

  return (
    <div className="flex min-h-full flex-col">
      {/* Заголовок чата */}
      <div className="sticky top-0 z-10 border-b border-border bg-card">
        <div className="container mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-4xl items-center gap-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(`/projects/${projectId}/sessions`)}
              className="shrink-0"
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <div className="flex-1">
              <h1 className="text-lg font-semibold text-foreground">
                {t("chatDetails.title")}{" "}
                {formatLongDateTime(chatSession.createdAt)}
              </h1>
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
          </div>
        </div>
      </div>

      {/* Список сообщений */}
      <main className="flex-1 overflow-y-auto">
        <div className="container mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-4xl space-y-6">
            {chatSession.messages.length === 0 ? (
              <div className="flex min-h-[400px] items-center justify-center">
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
      </main>
    </div>
  );
};
