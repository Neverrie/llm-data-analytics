"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ArtifactItem } from "@/lib/api";
import { DataTable } from "./DataTable";
import { ImageLightbox } from "./ImageLightbox";

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
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [lightboxOpen, setLightboxOpen] = useState(false);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return items.filter((i) => (kind === "all" || i.kind === kind) && (!q || i.title.toLowerCase().includes(q) || i.filename.toLowerCase().includes(q)));
  }, [items, query, kind]);

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

      if (contentType.startsWith("image/")) {
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        if (active) setPreview({ kind: "image", url: objectUrl });
        return;
      }

      const text = await response.text();
      if (!active) return;

      try {
        const parsed = JSON.parse(text);
        if (Array.isArray(parsed) && parsed.length && typeof parsed[0] === "object") {
          setPreview({ kind: "table", columns: Object.keys(parsed[0] as Record<string, unknown>), rows: parsed as Record<string, unknown>[] });
          return;
        }
        if (parsed?.columns && parsed?.rows) {
          setPreview({ kind: "table", columns: parsed.columns, rows: parsed.rows });
          return;
        }
        setPreview({ kind: "json", value: parsed });
        return;
      } catch {
        setPreview({ kind: "text", value: text });
      }
    })().catch(() => setPreview({ kind: "text", value: "Не удалось загрузить превью артефакта." }));

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [selected]);

  const kinds = useMemo(() => ["all", ...Array.from(new Set(items.map((i) => i.kind)))], [items]);
  const selectedId = selected?.id;
  const downloadSelected = async () => {
    if (!selected) return;
    const response = await api.fetchArtifactDownload(selected.id);
    if (!response.ok) throw new Error("Не удалось скачать артефакт.");
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = selected.filename || selected.title || "artifact";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(objectUrl);
  };

  return (
    <section className="main-panel workspace-screen">
      <div className="artifacts-scroll workspace-screen-scroll">
        <div className="artifacts-grid">
          <div className="artifact-list-wrap">
            <div className="explorer-toolbar">
              <h3>Артефакты</h3>
              <input className="small-input" placeholder="Поиск артефактов" value={query} onChange={(e) => setQuery(e.target.value)} />
              <select className="small-input" value={kind} onChange={(e) => setKind(e.target.value)}>
                {kinds.map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
            </div>
            <div className="artifact-list">
              {filtered.map((item) => (
                <button key={item.id} className={`artifact-item ${selectedId === item.id ? "active" : ""}`} onClick={() => onSelect(item.id)}>
                  <strong>{item.title}</strong>
                  <span>{item.kind} · {item.filename}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="artifact-preview">
            {!selected ? <div className="empty-state"><h3>Выберите артефакт</h3><p>Откройте файл из списка слева, чтобы увидеть превью.</p></div> : null}
            {selected ? <h3>{selected.filename}</h3> : null}
            {preview.kind === "image" ? (
              <button
                type="button"
                className="artifact-image-btn"
                onClick={() => setLightboxOpen(true)}
                title="Открыть в полный размер"
              >
                <img src={preview.url} alt={selected?.filename || "artifact"} />
              </button>
            ) : null}
            {preview.kind === "table" ? <DataTable columns={preview.columns} rows={preview.rows.slice(0, 30)} maxHeight={500} /> : null}
            {preview.kind === "json" ? <pre className="code-pre">{JSON.stringify(preview.value, null, 2)}</pre> : null}
            {preview.kind === "text" ? <pre className="code-pre">{preview.value}</pre> : null}
            {selected ? (
              <div className="panel-row">
                <button className="btn-secondary" onClick={() => onSelect(selected.id)}>Открыть</button>
                <button className="btn-secondary" onClick={() => void downloadSelected()}>Скачать</button>
                <button className="btn-ghost" onClick={() => navigator.clipboard.writeText(selected.path)}>Копировать путь</button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <ImageLightbox
        src={preview.kind === "image" ? preview.url : ""}
        alt={selected?.filename || "artifact"}
        open={lightboxOpen && preview.kind === "image"}
        onClose={() => setLightboxOpen(false)}
      />
    </section>
  );
}
