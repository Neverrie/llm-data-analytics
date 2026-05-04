"use client";

import { useState } from "react";

export function ChatComposer({
  onSend,
  loading,
  draft,
  onDraftChange
}: {
  onSend: (text: string) => void;
  loading: boolean;
  draft?: string;
  onDraftChange?: (text: string) => void;
}) {
  const [localValue, setLocalValue] = useState("");
  const value = typeof draft === "string" ? draft : localValue;
  const setValue = onDraftChange ?? setLocalValue;

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
