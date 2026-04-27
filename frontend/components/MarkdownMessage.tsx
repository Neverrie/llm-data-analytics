import ReactMarkdown from "react-markdown";

type MarkdownMessageProps = {
  content: string;
};

export function MarkdownMessage({ content }: MarkdownMessageProps) {
  return (
    <div className="space-y-3 text-sm leading-6">
      <ReactMarkdown
        components={{
          h2: ({ children }) => <h2 className="mt-2 border-b pb-1 text-lg font-semibold" style={{ borderColor: "var(--border)" }}>{children}</h2>,
          h3: ({ children }) => <h3 className="mt-2 text-base font-semibold">{children}</h3>,
          p: ({ children }) => <p className="whitespace-pre-wrap">{children}</p>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
          blockquote: ({ children }) => (
            <blockquote className="rounded-r-md border-l-4 px-3 py-2 text-sm app-muted" style={{ borderColor: "var(--primary)", background: "var(--surface-2)" }}>
              {children}
            </blockquote>
          ),
          code: ({ children, className }) => {
            if (!className) {
              return (
                <code className="rounded px-1.5 py-0.5 font-mono text-xs" style={{ background: "var(--surface-2)", color: "var(--primary)" }}>
                  {children}
                </code>
              );
            }
            return (
              <pre className="app-code-block">
                <code className={className}>{children}</code>
              </pre>
            );
          },
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="app-table text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => <th>{children}</th>,
          td: ({ children }) => <td>{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
