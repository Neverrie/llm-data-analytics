"use client";

import { ArtifactItem } from "@/lib/api";

export function ArtifactExplorer({
  items,
  previewUrl,
  downloadUrl,
  onSelect,
  selected
}: {
  items: ArtifactItem[];
  previewUrl: (id: string) => string;
  downloadUrl: (id: string) => string;
  onSelect: (id: string) => void;
  selected?: ArtifactItem;
}) {
  return (
    <section className="main-panel artifacts-grid">
      <div className="artifact-list">
        {items.map((item) => (
          <button key={item.id} className="artifact-item" onClick={() => onSelect(item.id)}>
            <strong>{item.title}</strong>
            <span>{item.kind}</span>
          </button>
        ))}
      </div>
      <div className="artifact-preview">
        {selected ? (
          <>
            <h3>{selected.filename}</h3>
            {selected.mime_type.startsWith("image/") ? <img src={previewUrl(selected.id)} alt={selected.filename} /> : <iframe src={previewUrl(selected.id)} title={selected.filename} />}
            <a className="btn-secondary" href={downloadUrl(selected.id)}>Download</a>
          </>
        ) : <p className="muted">Выберите артефакт</p>}
      </div>
    </section>
  );
}

