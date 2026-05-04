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
  onUseInChat
}: {
  datasets: DatasetItem[];
  selected?: string;
  preview: any;
  profile: any;
  onSelect: (id: string) => void;
  onUpload: (file: File) => void;
  onUseInChat?: (id: string) => void;
}) {
  const [tab, setTab] = useState<"preview" | "profile" | "columns">("preview");
  const selectedDataset = useMemo(() => datasets.find((d) => d.id === selected), [datasets, selected]);

  return (
    <section className="main-panel workspace-screen">
      <div className="workspace-screen-scroll">
      <div className="explorer-toolbar">
        <h3>Датасеты</h3>
        <div className="panel-row">
          <select value={selected} onChange={(e) => onSelect(e.target.value)}>
            <option value="">Выберите датасет</option>
            {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <label className="btn-secondary upload-label">Загрузить
            <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])} hidden />
          </label>
          {selected && onUseInChat ? <button className="btn-secondary" onClick={() => onUseInChat(selected)}>Использовать в чате</button> : null}
        </div>
      </div>

      {!selectedDataset ? <EmptyState title="Dataset не выбран" description="Выберите датасет в списке, чтобы увидеть preview и профиль." /> : (
        <>
          <div className="metric-grid small">
            <article className="metric-card"><h4>Name</h4><strong>{selectedDataset.name}</strong></article>
            <article className="metric-card"><h4>Source</h4><strong>{selectedDataset.source}</strong></article>
            <article className="metric-card"><h4>Rows</h4><strong>{profile?.rows_count ?? selectedDataset.rows_count ?? "?"}</strong></article>
            <article className="metric-card"><h4>Columns</h4><strong>{profile?.columns_count ?? selectedDataset.columns_count ?? "?"}</strong></article>
          </div>

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
