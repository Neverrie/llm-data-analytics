"use client";

export function CodeBlockCard({ title, code, meta }: { title: string; code: string; meta?: string }) {
  return (
    <article className="block-card">
      <div className="block-head"><strong>{title}</strong><span>{meta || ""}</span></div>
      <pre className="code-pre">{code}</pre>
    </article>
  );
}

