import { NavLink, Outlet, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/utils";

export const ProjectSettingsLayout = () => {
  const { t } = useTranslation();
  const { projectId } = useParams();

  const tabs = [
    {
      to: `/projects/${projectId}/settings/general`,
      label: t("settings.tabs.general"),
    },
    {
      to: `/projects/${projectId}/settings/api-keys`,
      label: t("settings.tabs.apiKeys"),
    },
    {
      to: `/projects/${projectId}/settings/credentials`,
      label: t("settings.tabs.credentials"),
    },
    {
      to: `/projects/${projectId}/settings/notifications`,
      label: t("settings.tabs.notifications"),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <nav className="flex items-center gap-1 border-b border-border">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              cn(
                "relative px-4 py-2.5 text-sm font-medium transition-colors",
                "hover:text-foreground",
                isActive
                  ? "text-foreground after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-primary"
                  : "text-muted-foreground"
              )
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  );
};
