import ReactMarkdown from "react-markdown";

type MarkdownMessageProps = {
  content: string;
};

export function MarkdownMessage({ content }: MarkdownMessageProps) {
  return (
    <div className="space-y-3 text-sm leading-6 app-text">
      <ReactMarkdown
        components={{
          h2: ({ children }) => <h2 className="mt-2 text-lg font-semibold app-text">{children}</h2>,
          h3: ({ children }) => <h3 className="mt-2 text-base font-semibold app-text">{children}</h3>,
          p: ({ children }) => <p className="whitespace-pre-wrap">{children}</p>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
          code: ({ children, className }) => {
            if (!className) {
              return (
                <code
                  className="rounded-lg px-1.5 py-0.5 font-mono text-xs"
                  style={{ backgroundColor: "var(--panel-strong)", color: "var(--accent)" }}
                >
                  {children}
                </code>
              );
            }
            return (
              <pre className="json-block overflow-x-auto p-3 text-xs">
                <code className={className}>{children}</code>
              </pre>
            );
          },
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-left text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="soft-border border-b px-2 py-1 font-semibold">{children}</th>,
          td: ({ children }) => <td className="soft-border border-b px-2 py-1 align-top">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
