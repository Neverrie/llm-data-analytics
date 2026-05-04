"use client";

import { memo } from "react";

type Row = Record<string, unknown>;

export const DataTable = memo(function DataTable({
  columns,
  rows,
  maxHeight = 360,
  density = "normal",
  stickyHeader = true
}: {
  columns: string[];
  rows: Row[];
  maxHeight?: number | string;
  density?: "compact" | "normal";
  stickyHeader?: boolean;
}) {
  const resolvedHeight = typeof maxHeight === "number" ? `${maxHeight}px` : maxHeight;

  return (
    <div className="data-table-shell">
      <div className="data-table-scroll" style={{ maxHeight: resolvedHeight }}>
        <table className={`data-table ${density === "compact" ? "compact" : ""} ${stickyHeader ? "" : "no-sticky"}`}>
          <thead>
            <tr>{columns.map((col) => <th key={col}>{col}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
            <tr key={index}>{columns.map((col) => <td key={`${index}-${col}`} data-col={col}>{String(row[col] ?? "")}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
});
