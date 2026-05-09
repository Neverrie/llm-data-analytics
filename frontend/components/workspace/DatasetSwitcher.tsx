"use client";

import { useMemo, useState } from "react";
import { ChevronDown, Plus } from "lucide-react";
import { DatasetItem } from "@/lib/api";

export function DatasetSwitcher({
  datasets,
  selectedDatasetId,
  onSelect,
  onPreview
}: {
  datasets: DatasetItem[];
  selectedDatasetId?: string;
  onSelect: (id: string) => void;
  onPreview: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [draftDatasetId, setDraftDatasetId] = useState<string>("");
  const selectedDataset = useMemo(() => datasets.find((d) => d.id === selectedDatasetId), [datasets, selectedDatasetId]);
  const activeDraftId = draftDatasetId || selectedDatasetId || "";
  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return datasets.filter((d) => !q || d.name.toLowerCase().includes(q) || d.source.toLowerCase().includes(q));
  }, [datasets, query]);
  const compactName = useMemo(() => {
    const name = selectedDataset?.name || "Датасет не выбран";
    return name.length > 28 ? `${name.slice(0, 28)}...` : name;
  }, [selectedDataset]);

  return (
    <div className="dataset-switcher">
      <button className="dataset-chip-btn" onClick={() => setOpen((v) => !v)} title={selectedDataset?.name || "Датасет не выбран"}>
        <span className="dataset-current">{compactName}</span>
        <ChevronDown size={14} />
      </button>
      {open ? (
        <div className="dataset-switcher-popover">
          <input
            className="small-input"
            placeholder="Поиск датасета"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="dataset-switcher-list">
            {filtered.map((dataset) => (
              <button
                key={dataset.id}
                className={`mini-item ${dataset.id === activeDraftId ? "active" : ""}`}
                onClick={() => {
                  // Apply dataset immediately on click to avoid "selected but not applied" UX.
                  setDraftDatasetId(dataset.id);
                  onSelect(dataset.id);
                  setOpen(false);
                  setDraftDatasetId("");
                }}
              >
                <strong>{dataset.name}</strong>
                <span>{dataset.source} · {dataset.rows_count ?? "?"} rows</span>
              </button>
            ))}
            {!filtered.length ? <div className="empty-mini">Нет совпадений</div> : null}
          </div>
          <div className="dataset-popover-actions">
            <button className="btn-ghost" onClick={() => activeDraftId && onPreview(activeDraftId)}>
              Превью выбранного
            </button>
            <button
              className="btn-primary"
              type="button"
              onClick={() => {
                if (!activeDraftId) return;
                onSelect(activeDraftId);
                setOpen(false);
                setDraftDatasetId("");
              }}
            >
              <Plus size={14} /> Добавить
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
