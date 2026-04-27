"use client";

import { useState } from "react";
import { api } from "../../lib/api";
import { SectionCard } from "../../components/SectionCard";

type Lab1Status = {
  lab: number;
  name: string;
  status: string;
  planned_features: string[];
};

export default function Lab1Page() {
  const [result, setResult] = useState<Lab1Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleCheck = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getLab1Status<Lab1Status>();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось получить ответ API");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Лаба 1 — Prompt Engineering EDA">
        <ul className="list-disc space-y-1 pl-6">
          <li>Загрузка CSV</li>
          <li>4 промпт-блока</li>
          <li>Ответы LLM</li>
          <li>Комментарии студента</li>
          <li>Экспорт Markdown/PDF</li>
        </ul>
      </SectionCard>

      <section className="app-card space-y-4 p-6">
        <button className="app-button app-button-primary" onClick={handleCheck} disabled={loading}>
          {loading ? "Проверка..." : "Проверить API лабы 1"}
        </button>

        {error ? (
          <p className="rounded-lg px-3 py-2 text-sm" style={{ background: "color-mix(in srgb, var(--danger) 14%, transparent)", color: "var(--danger)" }}>
            {error}
          </p>
        ) : null}

        {result ? <pre className="app-code-block">{JSON.stringify(result, null, 2)}</pre> : null}
      </section>
    </div>
  );
}
