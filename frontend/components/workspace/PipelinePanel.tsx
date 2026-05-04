"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";

const runStages = ["Читаем датасет", "Фильтруем отзывы", "Отправляем в OpenRouter", "Валидируем JSON", "Сохраняем result"];

function deriveColumns(rows: Record<string, unknown>[]) {
  const keys = new Set<string>();
  rows.forEach((row) => Object.keys(row || {}).forEach((k) => keys.add(k)));
  return Array.from(keys);
}

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
  const [stageIndex, setStageIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [sampleOpen, setSampleOpen] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);

  const sampleRows = useMemo(() => (Array.isArray(sample?.sample) ? sample.sample.slice(0, 20) : []), [sample]);
  const sampleCols = useMemo(() => deriveColumns(sampleRows), [sampleRows]);
  const resultRows = useMemo(() => (Array.isArray(result?.results) ? result.results : []), [result]);
  const resultCols = useMemo(() => deriveColumns(resultRows), [resultRows]);

  useEffect(() => {
    if (!running) {
      setStageIndex(0);
      setElapsed(0);
      return;
    }
    const t = setInterval(() => setElapsed((v) => v + 1), 1000);
    const s = setInterval(() => setStageIndex((v) => Math.min(v + 1, runStages.length - 1)), 1300);
    return () => {
      clearInterval(t);
      clearInterval(s);
    };
  }, [running]);

  useEffect(() => {
    if (resultRows.length) {
      setSampleOpen(false);
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [resultRows.length]);

  const hasResult = resultRows.length > 0;

  return (
    <section className="main-panel pipeline-panel">
      <div className="block-card">
        <strong>Lab 2 Pipeline</strong>
        <p className="muted">CSV → OpenRouter → JSON classification → result artifact</p>
        {lastRun?.updated_at ? <span className="muted">Последний запуск: {new Date(lastRun.updated_at).toLocaleString()}</span> : null}
      </div>

      <div className="pipeline-header glass-inset">
        <h3>Параметры запуска</h3>
        <div className="pipeline-controls">
          <input type="number" value={form.limit} onChange={(e) => onForm("limit", e.target.value)} placeholder="limit" />
          <input type="number" value={form.min_score} onChange={(e) => onForm("min_score", e.target.value)} placeholder="min_score" />
          <input type="number" value={form.max_score} onChange={(e) => onForm("max_score", e.target.value)} placeholder="max_score" />
          <button className="btn-secondary" onClick={onSample} disabled={loading}>Показать sample</button>
          <button className="btn-primary" onClick={onRun} disabled={loading}>{loading ? "Выполняется..." : "Запустить pipeline"}</button>
        </div>
      </div>

      {running ? (
        <div className="progress-card pipeline-progress-prominent">
          <strong>Pipeline выполняется...</strong>
          <ul>
            {runStages.map((s, i) => (
              <li key={s} className={i <= stageIndex ? "active-step" : ""}>
                <span className={`stage-dot ${i === stageIndex ? "active" : ""}`} />
                {s}
              </li>
            ))}
          </ul>
          <span className="muted">Прошло: {elapsed}с</span>
        </div>
      ) : null}

      {!running && hasResult ? (
        <div className="block-card pipeline-success">
          <strong>Pipeline завершён</strong>
          <div className="metric-grid small">
            <article className="metric-card"><h4>rows_processed</h4><strong>{result?.rows_processed ?? "-"}</strong></article>
            <article className="metric-card"><h4>batches_processed</h4><strong>{result?.batches_processed ?? "-"}</strong></article>
            <article className="metric-card"><h4>model</h4><strong>{result?.model ?? "-"}</strong></article>
            <article className="metric-card"><h4>output_file</h4><strong>{result?.output_file ?? "-"}</strong></article>
          </div>
        </div>
      ) : null}

      <section className="result-block" ref={resultRef}>
        <h3>Результат классификации</h3>
        {hasResult ? <DataTable columns={resultCols} rows={resultRows} /> : <EmptyState title="Нет результатов" description="Запустите pipeline, чтобы получить классификацию отзывов." />}
      </section>

      <details className="raw" open={!hasResult && sampleRows.length > 0 ? sampleOpen : false}>
        <summary onClick={(e) => { e.preventDefault(); setSampleOpen((v) => !v); }}>{sampleOpen ? "Скрыть sample" : "Показать sample"}</summary>
        <section className="result-block">
          <h3>Предпросмотр данных</h3>
          <p className="muted">Sample data: предпросмотр строк, доступен горизонтальный скролл</p>
          {sampleRows.length ? <DataTable columns={sampleCols} rows={sampleRows} /> : <EmptyState title="Нет sample" description="Нажмите «Показать sample» для предварительного просмотра." />}
        </section>
      </details>

      {result ? <details className="raw"><summary>Raw JSON</summary><pre>{JSON.stringify(result, null, 2)}</pre></details> : null}
    </section>
  );
}
