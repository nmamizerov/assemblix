import { Info } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ChatSessionsList } from "@/entities/chat-session";

interface ChatsPageProps {
  includeDebug?: boolean;
}

export const ChatsPage = ({ includeDebug = false }: ChatsPageProps) => {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-4">
      {/* Информационная плашка */}
      <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-950/30">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-indigo-600 dark:text-indigo-400 mt-0.5 shrink-0" />
          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold text-indigo-900 dark:text-indigo-100">
              {t("chats.infoBanner.title")}
            </h3>
            <p className="text-sm text-indigo-700 dark:text-indigo-300">
              {t("chats.infoBanner.description")}
            </p>
          </div>
        </div>
      </div>

      {/* Список чатов */}
      <ChatSessionsList includeDebug={includeDebug} />
    </div>
  );
};
