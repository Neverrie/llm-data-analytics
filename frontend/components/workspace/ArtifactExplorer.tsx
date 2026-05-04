"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ArtifactItem } from "@/lib/api";
import { DataTable } from "./DataTable";

type PreviewState =
  | { kind: "none" }
  | { kind: "image"; url: string }
  | { kind: "json"; value: unknown }
  | { kind: "text"; value: string }
  | { kind: "table"; columns: string[]; rows: Record<string, unknown>[] };

export function ArtifactExplorer({
  items,
  onSelect,
  selected
}: {
  items: ArtifactItem[];
  onSelect: (id: string) => void;
  selected?: ArtifactItem;
}) {
  const [preview, setPreview] = useState<PreviewState>({ kind: "none" });

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;

    (async () => {
      if (!selected) {
        setPreview({ kind: "none" });
        return;
      }
      const response = await api.fetchArtifactPreview(selected.id);
      const contentType = response.headers.get("content-type") || "";

      if (!active) return;

      if (contentType.startsWith("image/")) {
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        if (active) setPreview({ kind: "image", url: objectUrl });
        return;
      }

      const text = await response.text();
      if (!active) return;

      if (contentType.includes("application/json")) {
        try {
          const parsed = JSON.parse(text);
          if (Array.isArray(parsed) && parsed.length && typeof parsed[0] === "object") {
            setPreview({ kind: "table", columns: Object.keys(parsed[0] as Record<string, unknown>), rows: parsed as Record<string, unknown>[] });
          } else {
            setPreview({ kind: "json", value: parsed });
          }
        } catch {
          setPreview({ kind: "text", value: text });
        }
        return;
      }

      try {
        const parsed = JSON.parse(text);
        if (parsed?.columns && parsed?.rows) {
          setPreview({ kind: "table", columns: parsed.columns, rows: parsed.rows });
          return;
        }
      } catch {
        // no-op
      }

      setPreview({ kind: "text", value: text });
    })().catch(() => setPreview({ kind: "text", value: "Не удалось загрузить превью артефакта." }));

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [selected]);

  const selectedId = selected?.id;
  const selectedDownload = useMemo(() => (selected ? api.artifactDownloadUrl(selected.id) : "#"), [selected]);

  return (
    <section className="main-panel artifacts-grid">
      <div className="artifact-list">
        {items.map((item) => (
          <button key={item.id} className={`artifact-item ${selectedId === item.id ? "active" : ""}`} onClick={() => onSelect(item.id)}>
            <strong>{item.title}</strong>
            <span>{item.kind} · {item.filename}</span>
          </button>
        ))}
      </div>
      <div className="artifact-preview">
        {!selected ? <p className="muted">Выберите артефакт</p> : null}
        {selected ? <h3>{selected.filename}</h3> : null}
        {preview.kind === "image" ? <img src={preview.url} alt={selected?.filename || "artifact"} /> : null}
        {preview.kind === "table" ? <DataTable columns={preview.columns} rows={preview.rows} /> : null}
        {preview.kind === "json" ? <pre className="code-pre">{JSON.stringify(preview.value, null, 2)}</pre> : null}
        {preview.kind === "text" ? <pre className="code-pre">{preview.value}</pre> : null}
        {selected ? <a className="btn-secondary" href={selectedDownload}>Download</a> : null}
      </div>
    </section>
  );
}
