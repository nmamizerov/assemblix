import { useTranslation } from "react-i18next";
import { NotificationChannelsManager } from "@/entities/notification-channel";

export const NotificationsTab = () => {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {t("notifications.title")}
        </h1>
        <p className="text-sm text-muted-foreground">
          {t("notifications.subtitle")}
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
        <NotificationChannelsManager />
      </div>
    </div>
  );
};
