"use client";

import { useMemo, useState } from "react";
import { DatasetItem } from "@/lib/api";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";

export function DatasetExplorer({
  datasets,
  selected,
  preview,
  profile,
  onSelect,
  onUpload,
  onUseInChat,
  onDelete
}: {
  datasets: DatasetItem[];
  selected?: string;
  preview: any;
  profile: any;
  onSelect: (id: string) => void;
  onUpload: (file: File) => void;
  onUseInChat?: (id: string) => void;
  onDelete?: (id: string) => void;
}) {
  const [tab, setTab] = useState<"preview" | "profile" | "columns">("preview");
  const selectedDataset = useMemo(() => datasets.find((d) => d.id === selected), [datasets, selected]);

  return (
    <section className="main-panel workspace-screen">
      <div className="workspace-screen-scroll">
        <div className="explorer-toolbar dataset-toolbar">
          <h3>Датасеты</h3>
          <div className="panel-row dataset-controls">
            <select value={selected} onChange={(e) => onSelect(e.target.value)}>
              <option value="">Выберите датасет</option>
              {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <label className="btn-secondary upload-label">Загрузить
              <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])} hidden />
            </label>
          </div>
        </div>

        {!selectedDataset ? <EmptyState title="Датасет не выбран" description="Выберите датасет в списке, чтобы увидеть preview и профиль." /> : (
          <>
            <article className="dataset-selected-card">
              <div className="dataset-selected-title">{selectedDataset.name}</div>
              <div className="dataset-selected-actions">
                {selected && onUseInChat ? <button className="btn-secondary" onClick={() => onUseInChat(selected)}>Использовать в чате</button> : null}
                {selected && onDelete && (selectedDataset.source === "uploaded" || selectedDataset.source === "upload") ? (
                  <button className="btn-ghost danger" onClick={() => onDelete(selected)}>Удалить датасет</button>
                ) : null}
              </div>
            </article>

            <div className="tab-row">
              <button className={`mode-chip ${tab === "preview" ? "active" : ""}`} onClick={() => setTab("preview")}>Preview</button>
              <button className={`mode-chip ${tab === "profile" ? "active" : ""}`} onClick={() => setTab("profile")}>Profile</button>
              <button className={`mode-chip ${tab === "columns" ? "active" : ""}`} onClick={() => setTab("columns")}>Columns</button>
            </div>

            {tab === "preview" ? (
              preview?.rows?.length ? <DataTable columns={preview.columns || []} rows={preview.rows} maxHeight={560} /> : <EmptyState title="Нет preview" description="Данные preview пока недоступны." />
            ) : null}

            {tab === "profile" ? (
              <div className="code-pre">{JSON.stringify({ rows_count: profile?.rows_count, columns_count: profile?.columns_count }, null, 2)}</div>
            ) : null}

            {tab === "columns" ? (
              profile?.columns?.length ? <DataTable columns={["name", "dtype", "missing_count", "unique_count"]} rows={profile.columns} maxHeight={560} /> : <EmptyState title="Нет columns profile" description="Профиль колонок пока недоступен." />
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}
