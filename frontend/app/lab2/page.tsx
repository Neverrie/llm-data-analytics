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
          Пайплайн читает реальные отзывы пользователей Uber из CSV, отправляет их в локальную LLM через Ollama API и
          сохраняет структурированный JSON с классификацией отзывов.
        </p>
      </SectionCard>

      <SectionCard title="Датасет">
        <ul className="list-disc space-y-1 pl-6">
          <li>Uber Customer Reviews Dataset (2024)</li>
          <li>Используемая текстовая колонка: content</li>
          <li>Дополнительные поля: score, thumbsUpCount, reviewCreatedVersion, at, appVersion</li>
          <li>Файл: {status?.dataset ?? "загрузка..."}</li>
          <li>Модель: {status?.model ?? "загрузка..."}</li>
        </ul>
      </SectionCard>

      <SectionCard title="Pipeline">
        <ol className="list-decimal space-y-1 pl-6">
          <li>read dataset</li>
          <li>filter reviews</li>
          <li>build prompt</li>
          <li>call Ollama API</li>
          <li>parse JSON</li>
          <li>validate with Pydantic</li>
          <li>save result.json</li>
        </ol>
      </SectionCard>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">Настройки запуска</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="space-y-2">
            <span className="text-sm font-medium">limit</span>
            <p className="text-xs text-slate-600">Сколько отзывов обработать. Backend ограничит максимум.</p>
            <input
              type="number"
              min={1}
              max={1000}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value) || 10)}
              className="neu-inset w-full px-3 py-2 text-sm"
            />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium">batch_size</span>
            <p className="text-xs text-slate-600">Сколько отзывов отправлять в модель за один запрос.</p>
            <input
              type="number"
              min={1}
              max={20}
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value) || 5)}
              className="neu-inset w-full px-3 py-2 text-sm"
            />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium">min_score (опционально)</span>
            <p className="text-xs text-slate-600">Нижняя граница фильтра по оценке.</p>
            <input
              type="number"
              min={1}
              max={5}
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              className="neu-inset w-full px-3 py-2 text-sm"
              placeholder="например, 1"
            />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium">max_score (опционально)</span>
            <p className="text-xs text-slate-600">Верхняя граница фильтра по оценке.</p>
            <input
              type="number"
              min={1}
              max={5}
              value={maxScore}
              onChange={(e) => setMaxScore(e.target.value)}
              className="neu-inset w-full px-3 py-2 text-sm"
              placeholder="например, 5"
            />
          </label>
        </div>

        <div className="flex flex-wrap gap-3">
          <button className="neu-btn" onClick={handleLoadSample} disabled={loadingSample || loadingRun}>
            {loadingSample ? "Загрузка sample data..." : "Показать sample data"}
          </button>
          <button className="neu-btn" onClick={handleRunPipeline} disabled={loadingRun || loadingSample}>
            {loadingRun ? "Запуск pipeline..." : "Запустить pipeline"}
          </button>
        </div>

        {loadingStatus ? <p className="text-sm text-slate-600">Загрузка статуса Lab 2...</p> : null}
        {error ? <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
      </section>

      {sampleData ? (
        <section className="neu-card space-y-4 p-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xl font-semibold">Sample Data</h2>
            <p className="text-sm text-slate-600">Всего после фильтров: {sampleData.total_rows}</p>
          </div>
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
                    <td className="p-2">{truncate(row.content, 160)}</td>
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
          <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
            <p>
              <span className="font-medium">model:</span> {runResult.model}
            </p>
            <p>
              <span className="font-medium">dataset:</span> {runResult.dataset}
            </p>
            <p>
              <span className="font-medium">rows_requested:</span> {runResult.rows_requested}
            </p>
            <p>
              <span className="font-medium">rows_processed:</span> {runResult.rows_processed}
            </p>
            <p>
              <span className="font-medium">batch_size:</span> {runResult.batch_size}
            </p>
            <p>
              <span className="font-medium">batches_processed:</span> {runResult.batches_processed}
            </p>
            <p className="md:col-span-2">
              <span className="font-medium">output_file:</span> {runResult.output_file}
            </p>
          </div>

          {runResult.warnings.length > 0 ? (
            <div className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-700">
              <p className="font-medium">Warnings:</p>
              <ul className="list-disc pl-5">
                {runResult.warnings.map((warning, index) => (
                  <li key={`${warning}-${index}`}>{warning}</li>
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
                {runResult.results.map((row) => (
                  <tr key={row.row_id} className="border-t border-slate-200/70 align-top">
                    <td className="p-2">{row.row_id}</td>
                    <td className="p-2">{row.sentiment}</td>
                    <td className="p-2">{row.issue_type}</td>
                    <td className="p-2">{row.topic}</td>
                    <td className="p-2">{row.urgency}</td>
                    <td className="p-2">{row.summary}</td>
                    <td className="p-2">{row.suggested_action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <details className="neu-inset p-4">
            <summary className="cursor-pointer font-medium">Raw JSON</summary>
            <pre className="mt-3 overflow-x-auto text-xs md:text-sm">{JSON.stringify(runResult, null, 2)}</pre>
          </details>

          <a
            href={`${apiBaseUrl}/lab2/download`}
            className="inline-flex rounded-xl px-4 py-2 text-sm font-medium text-accent underline"
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
