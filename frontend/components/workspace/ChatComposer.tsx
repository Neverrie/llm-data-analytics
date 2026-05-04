"use client";

import { useState } from "react";

export function ChatComposer({ onSend, loading }: { onSend: (text: string) => void; loading: boolean }) {
  const [value, setValue] = useState("");

  function submit() {
    if (loading || !value.trim()) return;
    onSend(value.trim());
    setValue("");
  }

  return (
    <div className="composer modern-composer">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Спросите агента о данных..."
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <div className="composer-row">
        <span className="muted">Ctrl/Cmd + Enter</span>
        <button className="btn-primary" disabled={loading || !value.trim()} onClick={submit}>
          {loading ? "Выполняется..." : "Отправить"}
        </button>
      </div>
    </div>
  );
}
