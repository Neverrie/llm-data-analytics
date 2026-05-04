"use client";

import { DatasetItem } from "@/lib/api";
import { DataTable } from "./DataTable";

export function DatasetExplorer({
  datasets,
  selected,
  preview,
  profile,
  onSelect,
  onUpload
}: {
  datasets: DatasetItem[];
  selected?: string;
  preview: any;
  profile: any;
  onSelect: (id: string) => void;
  onUpload: (file: File) => void;
}) {
  return (
    <section className="main-panel">
      <div className="panel-row">
        <select value={selected} onChange={(e) => onSelect(e.target.value)}>
          {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])} />
      </div>
      {profile ? <div className="stat-strip"><span>rows: {profile.rows_count}</span><span>columns: {profile.columns_count}</span></div> : null}
      {preview?.rows?.length ? <DataTable columns={preview.columns || []} rows={preview.rows} /> : null}
    </section>
  );
}

