import JsonView from "@uiw/react-json-view";
import { lightTheme } from "@uiw/react-json-view/light";
import { darkTheme } from "@uiw/react-json-view/dark";
import { cn } from "@/shared/lib/utils";
import { useEffect, useState } from "react";

interface JsonViewerProps {
  data: unknown;
  defaultExpanded?: boolean;
  title?: string;
  className?: string;
}

export const JsonViewer = ({
  data,
  defaultExpanded = true,
  title,
  className,
}: JsonViewerProps) => {
  // Инициализируем тему на основе текущего состояния
  const [isDark, setIsDark] = useState(() => {
    return document.documentElement.classList.contains("dark");
  });

  useEffect(() => {
    // Слушаем изменения темы
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains("dark"));
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => observer.disconnect();
  }, []);

  return (
    <div className={cn("relative", className)}>
      {title && (
        <div className="mb-2">
          <h4 className="text-sm font-medium text-foreground">{title}</h4>
        </div>
      )}
      <div className="rounded-md border border-border overflow-auto max-h-[400px]">
        <JsonView
          value={data as object}
          collapsed={defaultExpanded ? false : 1}
          displayObjectSize={true}
          displayDataTypes={false}
          enableClipboard={true}
          indentWidth={15}
          shortenTextAfterLength={0}
          style={isDark ? darkTheme : lightTheme}
        />
      </div>
    </div>
  );
};
