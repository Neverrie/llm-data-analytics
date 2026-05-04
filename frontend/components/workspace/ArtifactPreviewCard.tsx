"use client";

export function ArtifactPreviewCard({ title, value }: { title: string; value: string }) {
  return (
    <article className="block-card">
      <div className="block-head"><strong>{title}</strong></div>
      <div className="muted">{value}</div>
    </article>
  );
}

