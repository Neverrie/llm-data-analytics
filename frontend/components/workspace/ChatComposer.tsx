"use client";

import { useState } from "react";

export function ChatComposer({ onSend, loading }: { onSend: (text: string) => void; loading: boolean }) {
  const [value, setValue] = useState("");

  return (
    <div className="composer">
      <textarea value={value} onChange={(e) => setValue(e.target.value)} placeholder="Задайте вопрос по датасету..." />
      <button
        className="btn-primary"
        disabled={loading || !value.trim()}
        onClick={() => {
          onSend(value.trim());
          setValue("");
        }}
      >
        {loading ? "Отправка..." : "Отправить"}
      </button>
    </div>
  );
}

