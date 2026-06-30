import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion } from "framer-motion";

import { Tabs, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { Label } from "@/shared/ui/label";
import { ChatsPage } from "@/pages/chats";
import { ExecutionsPage } from "@/pages/executions";

type SessionTab = "chats" | "executions";

export const SessionsPage = () => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<SessionTab>("chats");
  const [includeDebug, setIncludeDebug] = useState(false);

  return (
    <div className="min-h-full">
      <main className="container mx-auto px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl space-y-8">
          <div className="flex flex-col items-center space-y-6 py-8 text-center">
            <div className="space-y-2">
              <h2 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                {t("sessions.title")}
              </h2>
              <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
                {t("sessions.subtitle")}
              </p>
            </div>
          </div>

          <Tabs
            value={activeTab}
            onValueChange={(value) => setActiveTab(value as SessionTab)}
            className="w-full"
          >
            <div className="mb-5 space-y-4">
              <TabsList className="h-11 rounded-full bg-muted p-1">
                <TabsTrigger
                  value="chats"
                  className="rounded-full px-6 py-2 text-sm"
                >
                  {t("sessions.tabs.chats")}
                </TabsTrigger>
                <TabsTrigger
                  value="executions"
                  className="rounded-full px-6 py-2 text-sm"
                >
                  {t("sessions.tabs.executions")}
                </TabsTrigger>
              </TabsList>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="includeDebug"
                  checked={includeDebug}
                  onChange={(e) => setIncludeDebug(e.target.checked)}
                  className="h-4 w-4 rounded border-border text-primary focus:ring-2 focus:ring-primary"
                />
                <Label
                  htmlFor="includeDebug"
                  className="cursor-pointer text-sm"
                >
                  {t("sessions.showTestSessions")}
                </Label>
              </div>
            </div>
          </Tabs>

          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeInOut" }}
            >
              {activeTab === "chats" ? (
                <ChatsPage includeDebug={includeDebug} />
              ) : (
                <ExecutionsPage includeDebug={includeDebug} />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
};
