"use client";

export function CodeBlockCard({ title, code, meta }: { title: string; code: string; meta?: string }) {
  const lines = String(code || "").split("\n");
  const previewLines = lines.slice(0, 12).join("\n");
  const hasMore = lines.length > 12;
  return (
    <article className="block-card">
      <div className="block-head"><strong>{title}</strong><span>{meta || ""}</span></div>
      <pre className="code-pre">{hasMore ? previewLines : code}</pre>
      {hasMore ? (
        <details className="raw compact">
          <summary>Показать весь код</summary>
          <pre className="code-pre">{code}</pre>
        </details>
      ) : null}
    </article>
  );
}

