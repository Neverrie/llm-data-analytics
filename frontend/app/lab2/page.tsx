"use client";

import { useEffect, useMemo, useState } from "react";
import { SectionCard } from "../../components/SectionCard";
import { api, apiBaseUrl } from "../../lib/api";

type Lab2Status = {
  lab: number;
  name: string;
  status: string;
  dataset: string;
  model: string;
  pipeline: string[];
  available_endpoints: string[];
};

type SampleReview = {
  row_id: number;
  content: string;
  score: number | null;
  thumbs_up_count: number | null;
  at: string | null;
  app_version: string | null;
  review_created_version: string | null;
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

    fetchStatus();
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
        max_score: parsedMaxScore
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
      const data = await api.runLab2Pipeline<
        Lab2RunResponse,
        { limit: number; batch_size: number; min_score: number | null; max_score: number | null }
      >({
        limit,
        batch_size: batchSize,
        min_score: parsedMinScore,
        max_score: parsedMaxScore
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
        <p>
          Пайплайн читает реальные отзывы пользователей Uber из CSV, отправляет их в локальную LLM через Ollama API
          и сохраняет структурированный JSON с классификацией отзывов.
        </p>
      </SectionCard>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">Датасет</h2>
        <p>Uber Customer Reviews Dataset (2024)</p>
        <p className="text-sm text-slate-600">
          Текстовая колонка: <code>content</code>. Дополнительные поля: <code>score</code>, <code>thumbsUpCount</code>,
          <code> reviewCreatedVersion</code>, <code>at</code>, <code>appVersion</code>.
        </p>
      </section>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">Pipeline</h2>
        <ol className="list-decimal space-y-1 pl-6 text-sm text-slate-700">
          <li>read dataset</li>
          <li>filter reviews</li>
          <li>build prompt</li>
          <li>call Ollama API</li>
          <li>parse JSON</li>
          <li>validate with Pydantic</li>
          <li>save result.json</li>
        </ol>
      </section>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">Настройки запуска</h2>
        <p className="text-sm text-slate-600">
          `limit` — сколько отзывов обработать. `batch_size` — сколько отзывов отправлять в модель за один запрос.
          Backend ограничивает максимум по limit автоматически.
        </p>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-sm font-medium">limit</span>
            <input
              type="number"
              min={1}
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value) || 10)}
              className="neu-inset w-full px-3 py-2 text-sm"
            />
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium">batch_size</span>
            <input
              type="number"
              min={1}
              max={20}
              value={batchSize}
              onChange={(event) => setBatchSize(Number(event.target.value) || 5)}
              className="neu-inset w-full px-3 py-2 text-sm"
            />
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium">min_score (опционально)</span>
            <input
              type="number"
              min={1}
              max={5}
              value={minScore}
              onChange={(event) => setMinScore(event.target.value)}
              className="neu-inset w-full px-3 py-2 text-sm"
            />
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium">max_score (опционально)</span>
            <input
              type="number"
              min={1}
              max={5}
              value={maxScore}
              onChange={(event) => setMaxScore(event.target.value)}
              className="neu-inset w-full px-3 py-2 text-sm"
            />
          </label>
        </div>

        <div className="flex flex-wrap gap-2">
          <button className="neu-btn" onClick={handleLoadSample} disabled={loadingSample}>
            {loadingSample ? "Загрузка..." : "Показать sample data"}
          </button>
          <button className="neu-btn" onClick={handleRunPipeline} disabled={loadingRun}>
            {loadingRun ? "Запуск..." : "Запустить pipeline"}
          </button>
        </div>

        {loadingStatus ? <p className="text-sm">Загрузка статуса Lab 2...</p> : null}
        {status ? (
          <p className="text-sm text-slate-700">
            Модель: <span className="font-medium">{status.model}</span> | Датасет: <span className="font-medium">{status.dataset}</span>
          </p>
        ) : null}
        {error ? <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
      </section>

      {sampleData ? (
        <section className="neu-card space-y-4 p-6">
          <h2 className="text-xl font-semibold">Sample data</h2>
          <p className="text-sm text-slate-600">
            Dataset: {sampleData.dataset} | Rows after filtering: {sampleData.total_rows}
          </p>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="text-slate-600">
                  <th className="p-2">row_id</th>
                  <th className="p-2">score</th>
                  <th className="p-2">thumbs_up_count</th>
                  <th className="p-2">at</th>
                  <th className="p-2">content</th>
                </tr>
              </thead>
              <tbody>
                {sampleData.sample.map((row) => (
                  <tr key={row.row_id} className="border-t border-slate-200/70">
                    <td className="p-2">{row.row_id}</td>
                    <td className="p-2">{row.score ?? "-"}</td>
                    <td className="p-2">{row.thumbs_up_count ?? "-"}</td>
                    <td className="p-2">{row.at ?? "-"}</td>
                    <td className="p-2">{truncate(row.content, 140)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {runResult ? (
        <section className="neu-card space-y-4 p-6">
          <h2 className="text-xl font-semibold">Результат pipeline</h2>
          <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
            <p>model: {runResult.model}</p>
            <p>dataset: {runResult.dataset}</p>
            <p>rows_requested: {runResult.rows_requested}</p>
            <p>rows_processed: {runResult.rows_processed}</p>
            <p>batch_size: {runResult.batch_size}</p>
            <p>batches_processed: {runResult.batches_processed}</p>
            <p className="md:col-span-2">output_file: {runResult.output_file}</p>
          </div>

          {runResult.warnings.length > 0 ? (
            <div className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <p className="font-medium">Предупреждения:</p>
              <ul className="list-disc pl-5">
                {runResult.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="text-slate-600">
                  <th className="p-2">row_id</th>
                  <th className="p-2">sentiment</th>
                  <th className="p-2">issue_type</th>
                  <th className="p-2">topic</th>
                  <th className="p-2">urgency</th>
                  <th className="p-2">summary</th>
                  <th className="p-2">suggested_action</th>
                </tr>
              </thead>
              <tbody>
                {runResult.results.map((item) => (
                  <tr key={item.row_id} className="border-t border-slate-200/70 align-top">
                    <td className="p-2">{item.row_id}</td>
                    <td className="p-2">{item.sentiment}</td>
                    <td className="p-2">{item.issue_type}</td>
                    <td className="p-2">{item.topic}</td>
                    <td className="p-2">{item.urgency}</td>
                    <td className="p-2">{item.summary}</td>
                    <td className="p-2">{item.suggested_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <details className="neu-inset p-4">
            <summary className="cursor-pointer font-medium">Raw JSON</summary>
            <pre className="mt-2 overflow-x-auto text-xs md:text-sm">{JSON.stringify(runResult, null, 2)}</pre>
          </details>

          <a
            href={`${apiBaseUrl}/lab2/download`}
            className="inline-flex rounded-xl px-3 py-2 font-medium text-accent underline"
            target="_blank"
            rel="noreferrer"
          >
            Скачать result.json
          </a>
        </section>
      ) : null}
    </div>
  );
}
