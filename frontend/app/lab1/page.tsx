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
          <li>загрузка CSV;</li>
          <li>4 промпта;</li>
          <li>ответы LLM;</li>
          <li>комментарии студента;</li>
          <li>экспорт Markdown/PDF.</li>
        </ul>
      </SectionCard>

      <section className="neu-card p-6">
        <button className="neu-btn px-4 py-2" onClick={handleCheck} disabled={loading}>
          {loading ? "Проверка..." : "Проверить API лабы 1"}
        </button>

        {error ? <p className="error-box mt-4 px-3 py-2 text-sm">{error}</p> : null}
        {result ? <pre className="neu-inset mt-4 overflow-x-auto p-4 text-xs md:text-sm">{JSON.stringify(result, null, 2)}</pre> : null}
      </section>
    </div>
  );
}
