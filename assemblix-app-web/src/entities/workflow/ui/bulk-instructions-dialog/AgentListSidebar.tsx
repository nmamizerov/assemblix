import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Search, Bot } from "lucide-react";
import { Input } from "@/shared/ui/input";
import { cn } from "@/shared/lib/utils";
import type { AgentNodeConfig } from "../../model/types";

export interface AgentListItem {
  id: string;
  config: AgentNodeConfig;
  fallbackName: string;
}

interface AgentListSidebarProps {
  agents: AgentListItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export const AgentListSidebar = ({
  agents,
  selectedId,
  onSelect,
}: AgentListSidebarProps) => {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");

  const filteredAgents = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return agents;
    return agents.filter((agent) => {
      const name = (agent.config.name || agent.fallbackName).toLowerCase();
      const firstInstruction =
        agent.config.instructions?.[0]?.content?.toLowerCase() ?? "";
      return name.includes(q) || firstInstruction.includes(q);
    });
  }, [agents, query]);

  return (
    <div className="flex flex-col w-[260px] shrink-0 border-r overflow-hidden">
      <div className="p-3 border-b">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("workflow.bulkInstructions.searchPlaceholder")}
            className="pl-7 h-8 text-xs"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {filteredAgents.length === 0 ? (
          <div className="px-3 py-4 text-xs text-muted-foreground text-center">
            {t("workflow.bulkInstructions.noAgentsFound")}
          </div>
        ) : (
          <ul className="py-1">
            {filteredAgents.map((agent) => {
              const displayName = agent.config.name?.trim() || agent.fallbackName;
              const preview =
                agent.config.instructions?.[0]?.content?.trim() ?? "";
              return (
                <li key={agent.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(agent.id)}
                    className={cn(
                      "w-full text-left px-3 py-2 transition-colors flex gap-2 items-start hover:bg-accent/50",
                      selectedId === agent.id && "bg-accent",
                    )}
                  >
                    <Bot className="size-4 mt-0.5 text-muted-foreground shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium truncate">
                        {displayName}
                      </div>
                      {preview && (
                        <div className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                          {preview}
                        </div>
                      )}
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
};
