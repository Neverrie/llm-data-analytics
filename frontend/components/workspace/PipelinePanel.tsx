"use client";

import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";

export function PipelinePanel({
  sample,
  result,
  lastRun,
  running,
  onSample,
  onRun,
  loading,
  form,
  onForm
}: {
  sample: any;
  result: any;
  lastRun?: { updated_at?: string; title?: string; dataset?: string } | null;
  running?: boolean;
  onSample: () => void;
  onRun: () => void;
  loading: boolean;
  form: { limit: number; min_score: string; max_score: string };
  onForm: (key: "limit" | "min_score" | "max_score", value: string) => void;
}) {
  const runStages = ["Читаем датасет", "Фильтруем отзывы", "Отправляем в OpenRouter", "Валидируем JSON", "Сохраняем result"];
  return (
    <section className="main-panel">
      <div className="block-card">
        <strong>Pipeline</strong>
        <p className="muted">CSV → OpenRouter → JSON classification → result artifact</p>
        {lastRun?.updated_at ? <span className="muted">Последний запуск: {new Date(lastRun.updated_at).toLocaleString()}</span> : null}
      </div>
      <div className="pipeline-header glass-inset">
        <div className="pipeline-controls">
          <input type="number" value={form.limit} onChange={(e) => onForm("limit", e.target.value)} placeholder="limit" />
          <input type="number" value={form.min_score} onChange={(e) => onForm("min_score", e.target.value)} placeholder="min_score" />
          <input type="number" value={form.max_score} onChange={(e) => onForm("max_score", e.target.value)} placeholder="max_score" />
          <button className="btn-secondary" onClick={onSample} disabled={loading}>Показать sample</button>
          <button className="btn-primary" onClick={onRun} disabled={loading}>{loading ? "Запуск..." : "Запустить pipeline"}</button>
        </div>
      </div>
      {running ? <div className="progress-card"><strong>Pipeline выполняется...</strong><ul>{runStages.map((s) => <li key={s}>{s}</li>)}</ul></div> : null}

      <section className="result-block">
        <h3>Sample data</h3>
        {sample?.sample?.length ? <DataTable columns={Object.keys(sample.sample[0] || {})} rows={sample.sample} /> : <EmptyState title="Нет sample" description="Нажмите «Показать sample» для предварительного просмотра." />}
      </section>

      <section className="result-block">
        <h3>Pipeline results</h3>
        {result?.results?.length ? <DataTable columns={Object.keys(result.results[0] || {})} rows={result.results} /> : <EmptyState title="Нет результатов" description="Запустите pipeline, чтобы получить классификацию отзывов." />}
      </section>

      {result ? <details className="raw"><summary>Raw JSON</summary><pre>{JSON.stringify(result, null, 2)}</pre></details> : null}
    </section>
  );
}
