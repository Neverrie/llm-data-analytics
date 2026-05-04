"use client";

import { memo } from "react";

type Row = Record<string, unknown>;

export const DataTable = memo(function DataTable({ columns, rows }: { columns: string[]; rows: Row[] }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>{columns.map((col) => <th key={col}>{col}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>{columns.map((col) => <td key={`${index}-${col}`}>{String(row[col] ?? "")}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});
