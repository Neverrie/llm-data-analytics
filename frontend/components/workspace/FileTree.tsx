"use client";

export function FileTree({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="file-tree">
      <h4>{title}</h4>
      {items.map((item) => <div key={item} className="file-row">{item}</div>)}
    </div>
  );
}

