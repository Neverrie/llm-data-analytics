"use client";

import { useEffect, useMemo, useState } from "react";
import { SectionCard } from "../../components/SectionCard";
import { api, apiBaseUrl } from "../../lib/api";

type Lab2Status = {
  provider: string;
  model: string;
  dataset: string;
  configured: boolean;
};

type SampleReview = {
  row_id: number;
  content: string;
  score: number | null;
  thumbs_up_count: number | null;
  at: string | null;
};

type Lab2SampleDataResponse = { dataset: string; total_rows: number; sample: SampleReview[] };
type ReviewClassification = {
  row_id: number;
  sentiment: "positive" | "negative" | "neutral" | "mixed";
  issue_type: string;
  topic: string;
  urgency: "low" | "medium" | "high";
  summary: string;
  suggested_action: string;
};
type Lab2RunResponse = {
  provider: string;
  model: string;
  dataset: string;
  rows_requested: number;
  rows_processed: number;
  batch_size: number;
  batches_processed: number;
  output_file: string;
  warnings: string[];
  results?: ReviewClassification[];
  data?: { results?: ReviewClassification[] };
};

const MAX_LIMIT = 200;

function truncate(text: string, maxLength = 130): string {
  return text.length <= maxLength ? text : `${text.slice(0, maxLength)}...`;
}

export default function Lab2Page() {
  const [status, setStatus] = useState<Lab2Status | null>(null);
  const [sampleData, setSampleData] = useState<Lab2SampleDataResponse | null>(null);
  const [runResult, setRunResult] = useState<Lab2RunResponse | null>(null);

  const [limit, setLimit] = useState(20);
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [batchSize, setBatchSize] = useState("");
  const [processAll, setProcessAll] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getLab2Status<Lab2Status>().then(setStatus).catch((e) => setError(e.message));
  }, []);

  const parsedMin = useMemo(() => {
    const v = minScore.trim();
    if (!v) return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
  }, [minScore]);

  const parsedMax = useMemo(() => {
    const v = maxScore.trim();
    if (!v) return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
  }, [maxScore]);

  const parsedBatch = useMemo(() => {
    const v = batchSize.trim();
    if (!v) return null;
    const n = Number(v);
    return Number.isNaN(n) ? null : n;
  }, [batchSize]);

  const resultRows = runResult?.results ?? runResult?.data?.results ?? [];

  const loadSample = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getLab2SampleData<Lab2SampleDataResponse>({ limit, min_score: parsedMin, max_score: parsedMax });
      setSampleData(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить sample data");
    } finally {
      setLoading(false);
    }
  };

  const runPipeline = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = {
        limit,
        min_score: parsedMin,
        max_score: parsedMax,
        batch_size: parsedBatch,
        process_all: processAll,
      };
      const data = await api.runLab2Pipeline<Lab2RunResponse, typeof payload>(payload);
      setRunResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось запустить pipeline");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Лаба 2 — API Pipeline">
        <p>Классификация отзывов Uber через OpenRouter. Backend читает датасет, обрабатывает батчами и сохраняет JSON в outputs.</p>
      </SectionCard>

      <section className="app-card p-6 space-y-4">
        <h2 className="app-section-title">Параметры запуска</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <label className="space-y-1"><span className="text-sm">limit (до {MAX_LIMIT})</span><input className="app-input" type="number" min={1} max={MAX_LIMIT} value={limit} onChange={(e) => setLimit(Number(e.target.value) || 20)} /></label>
          <label className="space-y-1"><span className="text-sm">min_score</span><input className="app-input" type="number" min={1} max={5} value={minScore} onChange={(e) => setMinScore(e.target.value)} /></label>
          <label className="space-y-1"><span className="text-sm">max_score</span><input className="app-input" type="number" min={1} max={5} value={maxScore} onChange={(e) => setMaxScore(e.target.value)} /></label>
        </div>

        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={processAll} onChange={(e) => setProcessAll(e.target.checked)} /> Обработать максимум строк</label>

        <details className="app-expansion">
          <summary>Расширенные настройки</summary>
          <div className="p-3">
            <label className="space-y-1 block"><span className="text-sm">batch_size (опционально)</span><input className="app-input" type="number" min={1} max={200} value={batchSize} onChange={(e) => setBatchSize(e.target.value)} /></label>
          </div>
        </details>

        <div className="flex flex-wrap gap-2">
          <button className="app-button app-button-secondary" onClick={() => { setLimit(20); setMinScore("1"); setMaxScore("2"); }}>Demo на негативных отзывах</button>
          <button className="app-button app-button-secondary" onClick={loadSample} disabled={loading}>Показать sample data</button>
          <button className="app-button app-button-primary" onClick={runPipeline} disabled={loading}>Запустить pipeline</button>
        </div>

        {status ? <p className="text-sm app-muted">Provider: <b>{status.provider}</b> · Model: <b>{status.model}</b> · Dataset: <b>{status.dataset}</b></p> : null}
        {status && !status.configured ? <p className="text-sm" style={{ color: "var(--danger)" }}>OpenRouter API key не настроен. Создайте .env на основе .env.example.</p> : null}
        {error ? <p className="text-sm" style={{ color: "var(--danger)" }}>{error}</p> : null}
      </section>

      {sampleData ? (
        <section className="app-card p-6 space-y-3">
          <h2 className="app-section-title">Sample data</h2>
          <div className="overflow-x-auto"><table className="app-table"><thead><tr><th>row_id</th><th>score</th><th>thumbs_up_count</th><th>at</th><th>content</th></tr></thead><tbody>{sampleData.sample.map((r) => <tr key={r.row_id}><td>{r.row_id}</td><td>{r.score ?? "-"}</td><td>{r.thumbs_up_count ?? "-"}</td><td>{r.at ?? "-"}</td><td>{truncate(r.content)}</td></tr>)}</tbody></table></div>
        </section>
      ) : null}

      {runResult ? (
        <section className="app-card p-6 space-y-4">
          <h2 className="app-section-title">Результат pipeline</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
            <p>provider: {runResult.provider}</p><p>model: {runResult.model}</p>
            <p>dataset: {runResult.dataset}</p><p>rows_requested: {runResult.rows_requested}</p>
            <p>rows_processed: {runResult.rows_processed}</p><p>batch_size: {runResult.batch_size}</p>
            <p>batches_processed: {runResult.batches_processed}</p><p>output_file: {runResult.output_file}</p>
          </div>

          {runResult.warnings?.length ? <div className="text-sm app-muted">{runResult.warnings.map((w) => <p key={w}>{w}</p>)}</div> : null}

          {resultRows.length > 0 ? (
            <div className="overflow-x-auto"><table className="app-table"><thead><tr><th>row_id</th><th>sentiment</th><th>issue_type</th><th>topic</th><th>urgency</th><th>summary</th><th>suggested_action</th></tr></thead><tbody>{resultRows.map((r) => <tr key={r.row_id}><td>{r.row_id}</td><td>{r.sentiment}</td><td>{r.issue_type}</td><td>{r.topic}</td><td>{r.urgency}</td><td>{r.summary}</td><td>{r.suggested_action}</td></tr>)}</tbody></table></div>
          ) : <p className="text-sm app-muted">Pipeline завершён, но results пустой.</p>}

          <details className="app-expansion"><summary>Raw JSON</summary><pre className="app-code-block m-3">{JSON.stringify(runResult, null, 2)}</pre></details>
          <a href={`${apiBaseUrl}/lab2/download`} target="_blank" rel="noreferrer" className="font-semibold underline" style={{ color: "var(--primary)" }}>Скачать result.json</a>
        </section>
      ) : null}
    </div>
  );
}
