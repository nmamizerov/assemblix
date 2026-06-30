import { useTheme } from "@/shared/lib/theme-context";
import { Button } from "@/shared/ui/button";
import { useTranslation } from "react-i18next";

export const SettingsPage = () => {
  const { theme, setTheme } = useTheme();
  const { t } = useTranslation();

  const categories = [
    {
      titleKey: "settings.colorCategories.basic",
      colors: [
        {
          name: "Background",
          class: "bg-background text-foreground",
          var: "--background",
        },
        {
          name: "Foreground",
          class: "bg-foreground text-background",
          var: "--foreground",
        },
        { name: "Card", class: "bg-card text-card-foreground", var: "--card" },
        {
          name: "Popover",
          class: "bg-popover text-popover-foreground",
          var: "--popover",
        },
        { name: "Canvas", class: "bg-canvas", var: "--canvas" },
      ],
    },
    {
      titleKey: "settings.colorCategories.accents",
      colors: [
        {
          name: "Primary",
          class: "bg-primary text-primary-foreground",
          var: "--primary",
        },
        {
          name: "Secondary",
          class: "bg-secondary text-secondary-foreground",
          var: "--secondary",
        },
        {
          name: "Muted",
          class: "bg-muted text-muted-foreground",
          var: "--muted",
        },
        {
          name: "Accent",
          class: "bg-accent text-accent-foreground",
          var: "--accent",
        },
      ],
    },
    {
      titleKey: "settings.colorCategories.statuses",
      colors: [
        {
          name: "Destructive",
          class: "bg-destructive text-destructive-foreground",
          var: "--destructive",
        },
        {
          name: "Success",
          class: "bg-success text-success-foreground",
          var: "--success",
        },
        {
          name: "Warning",
          class: "bg-warning text-warning-foreground",
          var: "--warning",
        },
        { name: "Info", class: "bg-info text-info-foreground", var: "--info" },
      ],
    },
    {
      titleKey: "settings.colorCategories.workflowNodes",
      colors: [
        {
          name: "Node Start",
          class: "bg-node-start text-node-start-foreground",
          var: "--node-start",
        },
        {
          name: "Node Sticker",
          class: "bg-node-sticker text-node-sticker-foreground",
          var: "--node-sticker",
        },
        {
          name: "Node LLM",
          class: "bg-node-llm text-node-llm-foreground",
          var: "--node-llm",
        },
        {
          name: "Node Tool",
          class: "bg-node-tool text-node-tool-foreground",
          var: "--node-tool",
        },
        {
          name: "Node Logic",
          class: "bg-node-logic text-node-logic-foreground",
          var: "--node-logic",
        },
        {
          name: "Node Data",
          class: "bg-node-data text-node-data-foreground",
          var: "--node-data",
        },
        {
          name: "Node Data",
          class: "bg-node-http text-node-http-foreground",
          var: "--node-http",
        },
      ],
    },
    {
      titleKey: "settings.colorCategories.borders",
      colors: [
        { name: "Border", class: "bg-border", var: "--border" },
        { name: "Input", class: "bg-input", var: "--input" },
        { name: "Ring", class: "bg-ring", var: "--ring" },
      ],
    },
    {
      titleKey: "settings.colorCategories.sidebar",
      colors: [
        {
          name: "Sidebar",
          class: "bg-sidebar text-sidebar-foreground",
          var: "--sidebar",
        },
        {
          name: "Sidebar Primary",
          class: "bg-sidebar-primary text-sidebar-primary-foreground",
          var: "--sidebar-primary",
        },
        {
          name: "Sidebar Accent",
          class: "bg-sidebar-accent text-sidebar-accent-foreground",
          var: "--sidebar-accent",
        },
        {
          name: "Sidebar Border",
          class: "bg-sidebar-border",
          var: "--sidebar-border",
        },
      ],
    },
  ];

  return (
    <div className="p-8 space-y-12">
      <div>
        <h1 className="text-3xl font-bold mb-2">{t("settings.title")}</h1>
        <p className="text-muted-foreground">{t("settings.subtitle")}</p>
      </div>

      <section className="bg-card p-6 rounded-xl border border-border shadow-sm">
        <h2 className="text-xl font-semibold mb-4">{t("settings.theme")}</h2>
        <div className="flex gap-2">
          <Button
            variant={theme === "light" ? "default" : "outline"}
            onClick={() => setTheme("light")}
          >
            {t("settings.lightTheme")}
          </Button>
          <Button
            variant={theme === "dark" ? "default" : "outline"}
            onClick={() => setTheme("dark")}
          >
            {t("settings.darkTheme")}
          </Button>
          <Button
            variant={theme === "system" ? "default" : "outline"}
            onClick={() => setTheme("system")}
          >
            {t("settings.systemTheme")}
          </Button>
        </div>
      </section>

      <div className="grid gap-12">
        {categories.map((category) => (
          <section key={category.titleKey}>
            <h2 className="text-xl font-semibold mb-4 border-b pb-2">
              {t(category.titleKey)}
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {category.colors.map((color) => (
                <div key={color.name} className="flex flex-col gap-2">
                  <div
                    className={`${color.class} h-20 w-full rounded-lg border flex items-center justify-center text-sm font-medium shadow-sm transition-transform hover:scale-105`}
                  >
                    {color.name}
                  </div>
                  <div className="px-1 text-xs">
                    <p className="font-mono text-muted-foreground">
                      {color.var}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
};
