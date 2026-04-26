"use client";

import { useState } from "react";
import { api } from "../../lib/api";
import { SectionCard } from "../../components/SectionCard";

type Lab2Demo = {
  lab: number;
  name: string;
  status: string;
  pipeline: string[];
  sample_result: {
    dataset: string;
    rows: number;
    columns: number;
    summary: string;
  };
};

export default function Lab2Page() {
  const [result, setResult] = useState<Lab2Demo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getLab2Demo<Lab2Demo>();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось получить ответ API");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Лаба 2 — API Pipeline">
        <ul className="list-disc space-y-1 pl-6">
          <li>чтение CSV;</li>
          <li>запрос к LLM API;</li>
          <li>JSON-ответ;</li>
          <li>сохранение результата.</li>
        </ul>
      </SectionCard>

      <section className="neu-card p-6">
        <button className="neu-btn" onClick={handleRun} disabled={loading}>
          {loading ? "Запуск..." : "Запустить демо pipeline"}
        </button>

        {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
        {result ? (
          <pre className="neu-inset mt-4 overflow-x-auto p-4 text-xs md:text-sm">{JSON.stringify(result, null, 2)}</pre>
        ) : null}
      </section>
    </div>
  );
}

