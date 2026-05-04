"use client";

import { useEffect, useState } from "react";
import { MarkdownMessage } from "../../components/MarkdownMessage";
import { api, apiBaseUrl } from "../../lib/api";

type DatasetItem = { name: string; path: string; type: string };
type Lab3Profile = { dataset_name: string; total_rows: number; total_columns: number; columns: string[]; column_mapping: { roles: Record<string, { column: string | null; confidence: number; reason: string }> } };
type ToolInfo = { tool: string; description: string; required_roles: string[] };
type AskResult = {
  dataset: string;
  question: string;
  analysis_mode: "fast" | "balanced" | "full" | "code_interpreter";
  provider?: string;
  model?: string;
  llm_calls_count: number;
  elapsed_seconds: number;
  warnings: string[];
  planner_output: { plan: string; tool_calls: Array<{ tool: string; arguments: Record<string, unknown> }> };
  executed_tools: Array<Record<string, unknown>>;
  code_steps?: Array<Record<string, unknown>>;
  generated_files?: Array<{ name?: string; path?: string; size?: number }>;
  final_answer: string;
  output_files?: Record<string, string>;
};

type ResultTab = "answer" | "plan" | "tools" | "code" | "files" | "raw";

const MODE_LABEL: Record<AskResult["analysis_mode"], string> = {
  code_interpreter: "Code Interpreter",
  fast: "Fast tools (legacy)",
  balanced: "Balanced tools (legacy)",
  full: "Full tools (legacy)",
};

export default function Lab3Page() {
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [selectedDataset, setSelectedDataset] = useState("");
  const [profile, setProfile] = useState<Lab3Profile | null>(null);
  const [analysisMode, setAnalysisMode] = useState<AskResult["analysis_mode"]>("code_interpreter");
  const [maxToolCalls, setMaxToolCalls] = useState(6);
  const [maxCodeSteps, setMaxCodeSteps] = useState(5);
  const [useCritic, setUseCritic] = useState(false);
  const [question, setQuestion] = useState("Сделай краткий обзор датасета: строки, колонки, пропуски и 3 главных наблюдения.");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResult | null>(null);
  const [tab, setTab] = useState<ResultTab>("answer");

  const getFriendlyError = (message: string) => {
    if (message.toLowerCase().includes("did not contain usable text")) {
      return "Модель вернула ответ в нестандартном формате. Попробуйте повторить запрос или сменить модель в .env.";
    }
    if (message.toLowerCase().includes("at capacity")) {
      return "Free provider сейчас перегружен. Повторите запрос или используйте fallback-модель.";
    }
    return message;
  };

  const fetchInitial = async () => {
    const [ds, ts] = await Promise.all([
      api.getLab3Datasets<{ datasets: DatasetItem[] }>(),
      api.getLab3Tools<{ tools: ToolInfo[] }>(),
    ]);
    setDatasets(ds.datasets);
    setTools(ts.tools);
    if (!selectedDataset && ds.datasets.length > 0) setSelectedDataset(ds.datasets[0].name);
  };

  useEffect(() => { void fetchInitial(); }, []);

  const handleProfile = async () => {
    if (!selectedDataset) return;
    setLoading(true); setError(null);
    try { setProfile(await api.getLab3Profile<Lab3Profile>(selectedDataset)); }
    catch (err) { setError(err instanceof Error ? err.message : "Ошибка профиля датасета"); }
    finally { setLoading(false); }
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    setLoading(true); setError(null);
    try { await api.uploadLab3Dataset(uploadFile); await fetchInitial(); setUploadFile(null); }
    catch (err) { setError(err instanceof Error ? err.message : "Ошибка загрузки файла"); }
    finally { setLoading(false); }
  };

  const runAgent = async () => {
    if (!selectedDataset || !question.trim()) return;
    setLoading(true); setError(null);
    try {
      const data = await api.askLab3Agent<AskResult, Record<string, unknown>>({
        dataset_name: selectedDataset,
        question,
        column_overrides: {},
        max_tool_calls: maxToolCalls,
        max_code_steps: maxCodeSteps,
        use_critic: analysisMode === "code_interpreter" ? false : useCritic,
        analysis_mode: analysisMode,
        include_history: true,
        reset_session: false,
      });
      setResult(data); setTab("answer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка запуска агента");
    } finally { setLoading(false); }
  };

  return (
    <div className="space-y-6">
      <section className="app-card space-y-3 p-6">
        <h1 className="text-2xl font-bold">Лаба 3 — OpenRouter Code Interpreter Agent</h1>
        <p className="text-sm app-muted">По умолчанию используется Code Interpreter: LLM пишет Python-код, backend выполняет его в sandbox и возвращает результат модели.</p>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="app-badge app-badge-primary">OpenRouter</span>
          <span className="app-badge app-badge-muted">Code Interpreter</span>
          <span className="app-badge app-badge-muted">Python sandbox</span>
          <span className="app-badge app-badge-muted">CSV/XLSX</span>
          <span className="app-badge app-badge-muted">Agent loop</span>
        </div>
      </section>

      <section className="app-card space-y-3 p-4">
        <h2 className="app-section-title">Датасет</h2>
        <div className="flex flex-wrap gap-2">
          <select className="app-select" value={selectedDataset} onChange={(e) => setSelectedDataset(e.target.value)}>
            {datasets.map((d) => <option key={d.name} value={d.name}>{d.name} ({d.type})</option>)}
          </select>
          <button className="app-button app-button-secondary" onClick={handleProfile} disabled={loading}>Проанализировать структуру</button>
        </div>
        <div className="flex flex-wrap gap-2">
          <input type="file" accept=".csv,.xlsx,.xls" className="app-input" onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)} />
          <button className="app-button app-button-secondary" onClick={handleUpload} disabled={loading || !uploadFile}>Загрузить</button>
        </div>
        {profile ? <p className="text-sm app-muted">Rows: {profile.total_rows} · Columns: {profile.total_columns}</p> : null}
      </section>

      <section className="app-card space-y-3 p-4">
        <h2 className="app-section-title">Настройки</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <label className="space-y-1">
            <span className="text-xs app-muted">analysis_mode</span>
            <select className="app-select" value={analysisMode} onChange={(e) => setAnalysisMode(e.target.value as AskResult["analysis_mode"])}>
              <option value="code_interpreter">Code Interpreter</option>
              <option value="fast">Fast tools (legacy)</option>
              <option value="balanced">Balanced tools (legacy)</option>
              <option value="full">Full tools (legacy)</option>
            </select>
          </label>

          {analysisMode === "code_interpreter" ? (
            <>
              <label className="space-y-1">
                <span className="text-xs app-muted">max_code_steps</span>
                <input type="number" min={1} max={10} value={maxCodeSteps} onChange={(e) => setMaxCodeSteps(Number(e.target.value) || 5)} className="app-input" />
              </label>
              <div className="text-xs app-muted md:col-span-2">LLM сама генерирует и выполняет код шаг за шагом.</div>
            </>
          ) : (
            <details className="app-expansion md:col-span-2">
              <summary>Legacy tools mode настройки</summary>
              <div className="p-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                <label className="space-y-1"><span className="text-xs app-muted">max_tool_calls</span><input type="number" min={1} max={20} value={maxToolCalls} onChange={(e) => setMaxToolCalls(Number(e.target.value) || 6)} className="app-input" /></label>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={useCritic} onChange={(e) => setUseCritic(e.target.checked)} /> use_critic</label>
              </div>
            </details>
          )}
        </div>
      </section>

      <section className="app-card space-y-3 p-4">
        <h2 className="app-section-title">Вопрос</h2>
        <textarea className="app-textarea min-h-24" value={question} onChange={(e) => setQuestion(e.target.value)} />
        <button className="app-button app-button-primary" onClick={runAgent} disabled={loading}>{loading ? "Запуск..." : "Отправить агенту"}</button>
        {!result ? <p className="text-xs app-muted">В этом режиме модель сама пишет Python-код, backend выполняет его в sandbox и возвращает результат модели.</p> : null}
        {error ? (
          <div className="app-card p-4" style={{ borderColor: "color-mix(in srgb, var(--danger) 45%, var(--border))", background: "color-mix(in srgb, var(--danger) 8%, var(--surface))" }}>
            <p className="font-semibold" style={{ color: "var(--danger)" }}>Не удалось получить ответ от OpenRouter.</p>
            <p className="text-sm mt-1">{getFriendlyError(error)}</p>
          </div>
        ) : null}
      </section>

      {result ? (
        <section className="app-card space-y-4 p-4">
          <div className="app-badge app-badge-muted">{MODE_LABEL[result.analysis_mode]} · {result.elapsed_seconds} сек · {result.llm_calls_count} LLM · Provider: {result.provider ?? "-"} · Model: {result.model ?? "-"}</div>

          <div className="app-tabs">
            {(["answer", "plan", "tools", "code", "files", "raw"] as ResultTab[]).map((t) => (
              <button key={t} className={`app-tab ${tab === t ? "app-tab-active" : ""}`} onClick={() => setTab(t)}>
                {t === "answer" ? "Ответ" : t === "plan" ? "План" : t === "tools" ? "Tools" : t === "code" ? "Код" : t === "files" ? "Файлы" : "Raw"}
              </button>
            ))}
          </div>

          {tab === "answer" ? <MarkdownMessage content={result.final_answer} /> : null}
          {tab === "plan" ? <pre className="app-code-block">{JSON.stringify(result.planner_output, null, 2)}</pre> : null}
          {tab === "tools" ? <pre className="app-code-block">{JSON.stringify(result.executed_tools, null, 2)}</pre> : null}
          {tab === "code" ? <pre className="app-code-block">{JSON.stringify(result.code_steps ?? [], null, 2)}</pre> : null}
          {tab === "files" ? (
            <div className="space-y-2 text-sm">
              {(result.generated_files ?? []).map((f, idx) => <p key={idx}>{f.name} · {f.size} bytes · {f.path}</p>)}
              <a href={`${apiBaseUrl}/lab3/download-report`} target="_blank" rel="noreferrer" className="font-semibold underline" style={{ color: "var(--primary)" }}>Скачать report.md</a>
            </div>
          ) : null}
          {tab === "raw" ? <pre className="app-code-block">{JSON.stringify(result, null, 2)}</pre> : null}

          {result.warnings.length > 0 ? <div className="text-xs app-muted">{result.warnings.map((w) => <p key={w}>{w}</p>)}</div> : null}
        </section>
      ) : null}

      <details className="app-expansion">
        <summary>Legacy tools mode</summary>
        <div className="p-3 overflow-x-auto">
          <table className="app-table text-xs">
            <thead><tr><th>tool</th><th>description</th><th>required_roles</th></tr></thead>
            <tbody>{tools.map((tool) => <tr key={tool.tool}><td>{tool.tool}</td><td>{tool.description}</td><td>{tool.required_roles.join(", ") || "-"}</td></tr>)}</tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
