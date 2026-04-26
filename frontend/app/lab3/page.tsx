"use client";

import { useState } from "react";
import { api } from "../../lib/api";
import { SectionCard } from "../../components/SectionCard";

type Lab3Status = {
  lab: number;
  name: string;
  status: string;
  agent_architecture: {
    planner: string;
    tool_caller: string;
    critic: string;
    tools: string[];
  };
  security: string[];
};

export default function Lab3Page() {
  const [result, setResult] = useState<Lab3Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleCheck = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getLab3Status<Lab3Status>();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось получить ответ API");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Лаба 3 — LLM Analytics Agent">
        <ul className="list-disc space-y-1 pl-6">
          <li>загрузка датасета;</li>
          <li>агент;</li>
          <li>tool calling;</li>
          <li>графики;</li>
          <li>защита от prompt injection.</li>
        </ul>
      </SectionCard>

      <SectionCard title="Планируемая архитектура агента">
        <ul className="list-disc space-y-1 pl-6">
          <li>Planner model;</li>
          <li>Tool caller model;</li>
          <li>Critic model;</li>
          <li>Final report.</li>
        </ul>
      </SectionCard>

      <section className="neu-card p-6">
        <button className="neu-btn" onClick={handleCheck} disabled={loading}>
          {loading ? "Проверка..." : "Проверить статус агента"}
        </button>

        {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
        {result ? (
          <pre className="neu-inset mt-4 overflow-x-auto p-4 text-xs md:text-sm">{JSON.stringify(result, null, 2)}</pre>
        ) : null}
      </section>
    </div>
  );
}

