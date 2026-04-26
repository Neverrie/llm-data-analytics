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
  rows_processed: number;
  output_file: string;
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
        setError(err instanceof Error ? err.message : "?? ??????? ???????? ?????? Lab 2");
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
      setError(err instanceof Error ? err.message : "?? ??????? ????????? sample data");
    } finally {
      setLoadingSample(false);
    }
  };

  const handleRunPipeline = async () => {
    setLoadingRun(true);
    setError(null);
    try {
      const data = await api.runLab2Pipeline<Lab2RunResponse, { limit: number; min_score: number | null; max_score: number | null }>(
        {
          limit,
          min_score: parsedMinScore,
          max_score: parsedMaxScore
        }
      );
      setRunResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "?? ??????? ????????? pipeline");
    } finally {
      setLoadingRun(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard title="???? 2 ? API Pipeline">
        <p>
          ???????? ?????? ???????? ?????? ????????????? Uber ?? CSV, ?????????? ?? ? ????????? LLM ????? Ollama API ?
          ????????? ????????????????? JSON ? ?????????????? ???????.
        </p>
      </SectionCard>

      <SectionCard title="???????">
        <ul className="list-disc space-y-1 pl-6">
          <li>Uber Customer Reviews Dataset (2024)</li>
          <li>???????????? ????????? ???????: content</li>
          <li>?????????????? ????: score, thumbsUpCount, reviewCreatedVersion, at, appVersion</li>
          <li>????: {status?.dataset ?? "????????..."}</li>
          <li>??????: {status?.model ?? "????????..."}</li>
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
        <h2 className="text-xl font-semibold">????????? ???????</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label className="space-y-2">
            <span className="text-sm font-medium">limit (?? ????????? 10)</span>
            <input
              type="number"
              min={1}
              max={100}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value) || 10)}
              className="neu-inset w-full px-3 py-2 text-sm"
            />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium">min_score (???????????)</span>
            <input
              type="number"
              min={1}
              max={5}
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              className="neu-inset w-full px-3 py-2 text-sm"
              placeholder="????????, 1"
            />
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium">max_score (???????????)</span>
            <input
              type="number"
              min={1}
              max={5}
              value={maxScore}
              onChange={(e) => setMaxScore(e.target.value)}
              className="neu-inset w-full px-3 py-2 text-sm"
              placeholder="????????, 5"
            />
          </label>
        </div>

        <div className="flex flex-wrap gap-3">
          <button className="neu-btn" onClick={handleLoadSample} disabled={loadingSample || loadingRun}>
            {loadingSample ? "???????? sample data..." : "???????? sample data"}
          </button>
          <button className="neu-btn" onClick={handleRunPipeline} disabled={loadingRun || loadingSample}>
            {loadingRun ? "?????? pipeline..." : "????????? pipeline"}
          </button>
        </div>

        {loadingStatus ? <p className="text-sm text-slate-600">???????? ??????? Lab 2...</p> : null}
        {error ? <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
      </section>

      {sampleData ? (
        <section className="neu-card space-y-4 p-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xl font-semibold">Sample Data</h2>
            <p className="text-sm text-slate-600">????? ????? ????????: {sampleData.total_rows}</p>
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
          <h2 className="text-xl font-semibold">????????? pipeline</h2>
          <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
            <p>
              <span className="font-medium">model:</span> {runResult.model}
            </p>
            <p>
              <span className="font-medium">dataset:</span> {runResult.dataset}
            </p>
            <p>
              <span className="font-medium">rows_processed:</span> {runResult.rows_processed}
            </p>
            <p>
              <span className="font-medium">output_file:</span> {runResult.output_file}
            </p>
          </div>

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
            ??????? result.json
          </a>
        </section>
      ) : null}
    </div>
  );
}
