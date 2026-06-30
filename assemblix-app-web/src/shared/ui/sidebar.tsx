import {
  Users,
  History,
  BookMarked,
  UsersRound,
  Settings,
  ExternalLink,
} from "lucide-react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/utils";
import { getCommunityLinks } from "@/shared/lib/community-links";

type NavLinkItem = {
  label: string;
  icon: typeof Users;
  path: string;
  dataTour?: string;
};

type NavSection = {
  label?: string;
  items: NavLinkItem[];
};

export const Sidebar = () => {
  const location = useLocation();
  const { projectId } = useParams();
  const { t, i18n } = useTranslation();
  const communityLinks = getCommunityLinks(i18n.language);

  const sections: NavSection[] = [
    {
      label: t("sidebar.sections.creation"),
      items: [
        {
          label: t("sidebar.agents"),
          icon: Users,
          path: `/projects/${projectId}/workflows`,
          dataTour: "sidebar-agents",
        },
        {
          label: t("sidebar.knowledgeBases"),
          icon: BookMarked,
          path: `/projects/${projectId}/knowledge-bases`,
        },
      ],
    },
    {
      label: t("sidebar.sections.monitoring"),
      items: [
        {
          label: t("sidebar.agentSessions"),
          icon: History,
          path: `/projects/${projectId}/sessions`,
        },
        {
          label: t("sidebar.clientSessions"),
          icon: UsersRound,
          path: `/projects/${projectId}/client-sessions`,
        },
      ],
    },
    {
      items: [
        {
          label: t("sidebar.settings"),
          icon: Settings,
          path: `/projects/${projectId}/settings`,
        },
      ],
    },
  ];

  const isItemActive = (path: string) => location.pathname.startsWith(path);

  return (
    <aside className="w-64 bg-sidebar h-full flex flex-col">
      <nav className="flex-1 p-4 flex flex-col gap-6">
        {sections.map((section, idx) => (
          <div key={section.label ?? `section-${idx}`} className="space-y-1">
            {section.label && (
              <div className="px-4 pb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">
                {section.label}
              </div>
            )}
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = isItemActive(item.path);
              return (
                <Link
                  key={item.label}
                  to={item.path}
                  data-tour={item.dataTour}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-primary/10 hover:text-foreground"
                  )}
                >
                  <Icon className="h-5 w-5" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="p-4 flex flex-col gap-0.5 border-t border-sidebar-border/50">
        <button
          type="button"
          onClick={() => window.open(communityLinks.community, "_blank")}
          className="flex items-center gap-3 px-4 py-2 rounded-lg text-xs text-muted-foreground/70 hover:text-foreground transition-colors text-left"
        >
          <ExternalLink className="h-4 w-4" />
          <span>{t("sidebar.community")}</span>
        </button>
      </div>
    </aside>
  );
};
