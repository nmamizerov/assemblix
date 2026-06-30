import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownProps {
  content: string;
}

export const Markdown = ({ content }: MarkdownProps) => (
  <div className="text-sm leading-relaxed wrap-break-word">
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => <h1 className="text-lg font-bold mt-3 mb-1 first:mt-0">{children}</h1>,
        h2: ({ children }) => <h2 className="text-base font-bold mt-3 mb-1 first:mt-0">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-bold mt-2 mb-1 first:mt-0">{children}</h3>,
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => <ul className="list-disc list-outside pl-4 mb-2 space-y-0.5">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-outside pl-4 mb-2 space-y-0.5">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        code: ({ children, className }) => {
          const isBlock = className?.includes("language-");
          return isBlock
            ? <code className="block bg-black/10 dark:bg-white/10 rounded px-3 py-2 text-xs font-mono my-2 whitespace-pre overflow-x-auto">{children}</code>
            : <code className="bg-black/10 dark:bg-white/10 rounded px-1 py-0.5 text-xs font-mono">{children}</code>;
        },
        pre: ({ children }) => <pre className="my-2">{children}</pre>,
        blockquote: ({ children }) => <blockquote className="border-l-2 border-current opacity-70 pl-3 my-2 italic">{children}</blockquote>,
        hr: () => <hr className="border-current opacity-20 my-3" />,
        a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2 opacity-80 hover:opacity-100">{children}</a>,
      }}
    >
      {content}
    </ReactMarkdown>
  </div>
);
