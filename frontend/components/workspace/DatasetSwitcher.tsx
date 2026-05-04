"use client";

import { useMemo, useState } from "react";
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
  const selectedDataset = useMemo(() => datasets.find((d) => d.id === selectedDatasetId), [datasets, selectedDatasetId]);
  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return datasets.filter((d) => !q || d.name.toLowerCase().includes(q) || d.source.toLowerCase().includes(q));
  }, [datasets, query]);

  return (
    <div className="dataset-switcher">
      <span className="dataset-current">Dataset: {selectedDataset?.name || "не выбран"}</span>
      <button className="btn-ghost" onClick={() => setOpen((v) => !v)}>Сменить</button>
      <button
        className="btn-ghost"
        onClick={(e) => {
          e.stopPropagation();
          if (selectedDatasetId) onPreview(selectedDatasetId);
        }}
      >
        Превью
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
                className={`mini-item ${dataset.id === selectedDatasetId ? "active" : ""}`}
                onClick={() => {
                  onSelect(dataset.id);
                  setOpen(false);
                }}
              >
                <strong>{dataset.name}</strong>
                <span>{dataset.source} · {dataset.rows_count ?? "?"} rows</span>
              </button>
            ))}
            {!filtered.length ? <div className="empty-mini">Нет совпадений</div> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
