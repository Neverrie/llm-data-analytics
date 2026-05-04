"use client";

import { useEffect, useState } from "react";

const baseStages = ["Подготовка датасета", "Модель пишет код", "Sandbox выполняет код", "Модель анализирует результат", "Формируем ответ"];

export function AgentRunProgress({
  active,
  stats
}: {
  active: boolean;
  stats?: { provider?: string; model?: string; llm_calls_count?: number; successful_executions_count?: number; elapsed_seconds?: number } | null;
}) {
  const [stageIndex, setStageIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!active) {
      setStageIndex(0);
      setElapsed(0);
      return;
    }
    const t = setInterval(() => setElapsed((v) => v + 1), 1000);
    const s = setInterval(() => setStageIndex((v) => Math.min(v + 1, baseStages.length - 1)), 1400);
    return () => {
      clearInterval(t);
      clearInterval(s);
    };
  }, [active]);

  if (!active) return null;
  return (
    <div className="progress-card">
      <strong>Агент выполняет анализ...</strong>
      <ul>{baseStages.map((s, i) => <li key={s} className={i <= stageIndex ? "active-step" : ""}>{s}</li>)}</ul>
      <span className="muted">Прошло: {elapsed}с</span>
      {stats?.model ? (
        <p className="muted">
          {stats.provider || "provider"} / {stats.model} • LLM calls: {stats.llm_calls_count ?? 0} • success exec: {stats.successful_executions_count ?? 0}
        </p>
      ) : null}
    </div>
  );
}
