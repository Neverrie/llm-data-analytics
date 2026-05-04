"use client";

import { useEffect, useMemo, useState } from "react";
import { SectionCard } from "../../components/SectionCard";
import { api, apiBaseUrl } from "../../lib/api";

type Lab2Status = {
  lab: number;
  name: string;
  status: string;
  provider: string;
  dataset: string;
  model: string;
  configured: boolean;
  pipeline: string[];
  available_endpoints: string[];
};

type SampleReview = {
  row_id: number;
  content: string;
  score: number | null;
  thumbs_up_count: number | null;
  at: string | null;
};

type Lab2SampleDataResponse = {
  dataset: string;
  total_rows: number;
  sample: SampleReview[];
};

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
  lab: number;
  status: string;
  provider: string;
  model: string;
  dataset: string;
  rows_requested: number;
  rows_processed: number;
  batch_size: number;
  batches_processed: number;
  output_file: string;
  warnings: string[];
  results: ReviewClassification[];
};

function truncate(text: string, maxLength = 120): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}

export default function Lab2Page() {
  const [status, setStatus] = useState<Lab2Status | null>(null);
  const [sampleData, setSampleData] = useState<Lab2SampleDataResponse | null>(null);
  const [runResult, setRunResult] = useState<Lab2RunResponse | null>(null);

  const [limit, setLimit] = useState(10);
  const [batchSize, setBatchSize] = useState(5);
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");

  const [loadingStatus, setLoadingStatus] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);
  const [loadingRun, setLoadingRun] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStatus = async () => {
      setLoadingStatus(true);
      setError(null);
      try {
        const data = await api.getLab2Status<Lab2Status>();
        setStatus(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось получить статус Lab 2");
      } finally {
        setLoadingStatus(false);
      }
    };
    void fetchStatus();
  }, []);

  const parsedMinScore = useMemo(() => {
    const value = minScore.trim();
    if (!value) return null;
    const parsed = Number(value);
    return Number.isNaN(parsed) ? null : parsed;
  }, [minScore]);

  const parsedMaxScore = useMemo(() => {
    const value = maxScore.trim();
    if (!value) return null;
    const parsed = Number(value);
    return Number.isNaN(parsed) ? null : parsed;
  }, [maxScore]);

  const handleLoadSample = async () => {
    setLoadingSample(true);
    setError(null);
    try {
      const data = await api.getLab2SampleData<Lab2SampleDataResponse>({
        limit,
        min_score: parsedMinScore,
        max_score: parsedMaxScore,
      });
      setSampleData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить sample data");
    } finally {
      setLoadingSample(false);
    }
  };

  const handleRunPipeline = async () => {
    setLoadingRun(true);
    setError(null);
    try {
      const data = await api.runLab2Pipeline<Lab2RunResponse, { limit: number; batch_size: number; min_score: number | null; max_score: number | null }>({
        limit,
        batch_size: batchSize,
        min_score: parsedMinScore,
        max_score: parsedMaxScore,
      });
      setRunResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось запустить pipeline");
    } finally {
      setLoadingRun(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Лаба 2 — API Pipeline">
        <p>Пайплайн читает отзывы Uber из CSV, отправляет их в OpenRouter и сохраняет структурированный JSON.</p>
      </SectionCard>

      <section className="app-card space-y-3 p-6">
        <h2 className="app-section-title">Pipeline</h2>
        <ol className="list-decimal space-y-1 pl-6 text-sm app-muted">
          <li>read dataset</li>
          <li>filter reviews</li>
          <li>build prompt</li>
          <li>call LLM API</li>
          <li>parse JSON</li>
          <li>validate with Pydantic</li>
          <li>save result.json</li>
        </ol>
      </section>

      <section className="app-card space-y-4 p-6">
        <h2 className="app-section-title">Настройки запуска</h2>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="space-y-1">
            <span className="text-sm font-medium">limit</span>
            <input type="number" min={1} value={limit} onChange={(event) => setLimit(Number(event.target.value) || 10)} className="app-input" />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">batch_size</span>
            <input type="number" min={1} max={20} value={batchSize} onChange={(event) => setBatchSize(Number(event.target.value) || 5)} className="app-input" />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">min_score</span>
            <input type="number" min={1} max={5} value={minScore} onChange={(event) => setMinScore(event.target.value)} className="app-input" />
          </label>
          <label className="space-y-1">
            <span className="text-sm font-medium">max_score</span>
            <input type="number" min={1} max={5} value={maxScore} onChange={(event) => setMaxScore(event.target.value)} className="app-input" />
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          <button className="app-button app-button-secondary" onClick={handleLoadSample} disabled={loadingSample}>
            {loadingSample ? "Загрузка..." : "Показать sample data"}
          </button>
          <button className="app-button app-button-primary" onClick={handleRunPipeline} disabled={loadingRun}>
            {loadingRun ? "Запуск..." : "Запустить pipeline"}
          </button>
        </div>

        {loadingStatus ? <p className="text-sm app-muted">Загрузка статуса...</p> : null}
        {status ? (
          <p className="text-sm app-muted">
            Provider: <strong>{status.provider}</strong> | Model: <strong>{status.model}</strong> | Dataset: <strong>{status.dataset}</strong>
          </p>
        ) : null}
        {status && !status.configured ? (
          <p className="rounded-lg px-3 py-2 text-sm" style={{ background: "color-mix(in srgb, var(--danger) 14%, transparent)", color: "var(--danger)" }}>
            OpenRouter API key не настроен. Создайте .env на основе .env.example.
          </p>
        ) : null}
        {error ? (
          <p className="rounded-lg px-3 py-2 text-sm" style={{ background: "color-mix(in srgb, var(--danger) 14%, transparent)", color: "var(--danger)" }}>
            {error}
          </p>
        ) : null}
      </section>

      {sampleData ? (
        <section className="app-card space-y-4 p-6">
          <h2 className="app-section-title">Sample data</h2>
          <div className="overflow-x-auto">
            <table className="app-table">
              <thead>
                <tr>
                  <th>row_id</th>
                  <th>score</th>
                  <th>thumbs_up_count</th>
                  <th>at</th>
                  <th>content</th>
                </tr>
              </thead>
              <tbody>
                {sampleData.sample.map((row) => (
                  <tr key={row.row_id}>
                    <td>{row.row_id}</td>
                    <td>{row.score ?? "-"}</td>
                    <td>{row.thumbs_up_count ?? "-"}</td>
                    <td>{row.at ?? "-"}</td>
                    <td>{truncate(row.content, 140)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {runResult ? (
        <section className="app-card space-y-4 p-6">
          <h2 className="app-section-title">Результат pipeline</h2>
          <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
            <p>provider: {runResult.provider}</p>
            <p>model: {runResult.model}</p>
            <p>dataset: {runResult.dataset}</p>
            <p>rows_processed: {runResult.rows_processed}</p>
          </div>
          <details className="app-expansion">
            <summary>Raw JSON</summary>
            <pre className="app-code-block m-3">{JSON.stringify(runResult, null, 2)}</pre>
          </details>
          <a href={`${apiBaseUrl}/lab2/download`} className="inline-flex text-sm font-semibold underline" style={{ color: "var(--primary)" }} target="_blank" rel="noreferrer">
            Скачать result.json
          </a>
        </section>
      ) : null}
    </div>
  );
}
