import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/shared/lib/utils";

interface CodeExample {
  language: string;
  code: string;
}

interface CodeBlockProps {
  examples: CodeExample[];
}

export const CodeBlock = ({ examples }: CodeBlockProps) => {
  const [activeTab, setActiveTab] = useState(examples[0]?.language || "");
  const [copied, setCopied] = useState(false);

  const currentExample = examples.find((ex) => ex.language === activeTab);

  const handleCopy = () => {
    if (currentExample) {
      navigator.clipboard.writeText(currentExample.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="rounded-lg border bg-muted/30 overflow-hidden max-w-full">
      {/* Tabs */}
      <div className="flex items-center justify-between border-b bg-muted/50 px-4 shrink-0">
        <div className="flex gap-2 overflow-x-auto">
          {examples.map((example) => (
            <button
              key={example.language}
              onClick={() => setActiveTab(example.language)}
              className={cn(
                "px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px whitespace-nowrap",
                activeTab === example.language
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {example.language}
            </button>
          ))}
        </div>
        <button
          onClick={handleCopy}
          className="p-2 hover:bg-accent rounded-md transition-colors shrink-0 ml-2"
          title={copied ? "Скопировано!" : "Копировать"}
        >
          {copied ? (
            <Check className="h-4 w-4 text-success" />
          ) : (
            <Copy className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
      </div>

      {/* Code */}
      <div className="p-4 overflow-x-auto">
        <pre className="text-sm">
          <code className="text-foreground font-mono whitespace-pre">
            {currentExample?.code}
          </code>
        </pre>
      </div>
    </div>
  );
};
