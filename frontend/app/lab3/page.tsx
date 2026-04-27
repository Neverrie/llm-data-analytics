"use client";

import { useEffect, useMemo, useState } from "react";
import { MarkdownMessage } from "../../components/MarkdownMessage";
import { api, apiBaseUrl } from "../../lib/api";

type DatasetItem = {
  name: string;
  path: string;
  type: string;
};

type RoleMatch = {
  column: string | null;
  confidence: number;
  reason: string;
};

type ColumnMapping = {
  roles: Record<string, RoleMatch>;
  numeric_columns: string[];
  categorical_columns: string[];
};

type Lab3Profile = {
  dataset_name: string;
  total_rows: number;
  total_columns: number;
  columns: string[];
  column_mapping: ColumnMapping;
};

type ToolInfo = {
  tool: string;
  description: string;
  required_roles: string[];
};

type AskResult = {
  lab: number;
  status: string;
  dataset: string;
  question: string;
  analysis_mode: "fast" | "balanced" | "full";
  llm_calls_count: number;
  elapsed_seconds: number;
  warnings: string[];
  session_id: string;
  history_length: number;
  conversation_summary: string;
  column_mapping: ColumnMapping;
  planner_output: { plan: string; tool_calls: Array<{ tool: string; arguments: Record<string, unknown> }> };
  executed_tools: Array<Record<string, unknown>>;
  final_answer: string;
  critic_review?: { passed: boolean; issues: string[]; recommendations: string[] } | null;
  output_files?: Record<string, string>;
};

type ChatMessage =
  | { id: string; role: "user"; content: string; createdAt: string }
  | { id: string; role: "assistant"; content: string; createdAt: string; payload: AskResult };

type UploadResponse = {
  status: string;
  dataset: { name: string; type: string; rows: number; columns: number };
};

type SessionSnapshot = {
  session_id: string;
  dataset_name: string;
  history_length: number;
  conversation_summary: string;
  turns: Array<{ question: string; answer_summary: string }>;
};

type ResultTab = "answer" | "plan" | "tools" | "columns" | "files" | "raw";

const ROLE_KEYS = [
  "id_column",
  "text_column",
  "rating_column",
  "target_column",
  "date_column",
  "version_column",
  "reply_column",
  "reply_date_column",
] as const;

const BASE_SCENARIOS: Array<{ label: string; question: string }> = [
  { label: "Обзор датасета", question: "Сделай краткий обзор датасета: структура, типы колонок, пропуски и первые аналитические наблюдения." },
  { label: "Качество данных", question: "Проверь качество данных: пропуски, дубликаты, подозрительные значения и ограничения анализа." },
  { label: "Числовой анализ", question: "Проанализируй числовые колонки: распределения, средние значения, разброс и возможные выбросы." },
  { label: "Категориальный анализ", question: "Проанализируй категориальные колонки: частые значения, дисбаланс категорий и возможные закономерности." },
  { label: "Корреляции", question: "Найди возможные зависимости между числовыми колонками и объясни самые заметные корреляции." },
  { label: "Аномалии", question: "Найди потенциальные аномалии и выбросы в числовых колонках, объясни почему они могут быть важны." },
  { label: "Prompt injection", question: "Проверь текстовые поля на возможные prompt injection инструкции и объясни, как система от них защищается." },
  { label: "Итоговый отчёт", question: "Сформируй итоговый аналитический отчёт по датасету: структура, качество данных, ключевые наблюдения, ограничения и что проверить дальше." },
];

const FOLLOW_UP_HINTS = ["Покажи подробнее", "Какие есть ограничения?", "Что проверить дальше?"];
const STORAGE_KEY = "lab3_session_id";

const modeLabel: Record<AskResult["analysis_mode"], string> = {
  fast: "Быстрый",
  balanced: "Сбалансированный",
  full: "Полный",
};

function shortSession(sessionId: string | null): string {
  if (!sessionId) return "-";
  return `${sessionId.slice(0, 8)}...`;
}

export default function Lab3Page() {
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [profile, setProfile] = useState<Lab3Profile | null>(null);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [question, setQuestion] = useState("Сделай краткий обзор датасета");
  const [analysisMode, setAnalysisMode] = useState<"fast" | "balanced" | "full">("fast");
  const [maxToolCalls, setMaxToolCalls] = useState(6);
  const [useCritic, setUseCritic] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, string | null>>({});
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [loadingAsk, setLoadingAsk] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionState, setSessionState] = useState<SessionSnapshot | null>(null);
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [activeTabs, setActiveTabs] = useState<Record<string, ResultTab>>({});

  const availableColumns = profile?.columns ?? [];
  const hasReviewRoles = Boolean(profile?.column_mapping.roles.text_column?.column && profile?.column_mapping.roles.rating_column?.column);
  const roleOptions = useMemo(() => ["", ...availableColumns], [availableColumns]);

  const scenarios = useMemo(() => {
    if (!hasReviewRoles) return BASE_SCENARIOS;
    return [
      ...BASE_SCENARIOS,
      { label: "Проблемы пользователей", question: "Какие основные проблемы пользователи отмечают в низкооценённых отзывах?" },
      { label: "Негативные отзывы", question: "Какие темы чаще всего встречаются в негативных отзывах?" },
      { label: "Отзывы по времени", question: "Есть ли ухудшение оценок со временем?" },
    ];
  }, [hasReviewRoles]);

  const fetchInitialData = async () => {
    const [datasetsResp, toolsResp] = await Promise.all([
      api.getLab3Datasets<{ datasets: DatasetItem[] }>(),
      api.getLab3Tools<{ tools: ToolInfo[] }>(),
    ]);
    setDatasets(datasetsResp.datasets);
    setTools(toolsResp.tools);
    if (!selectedDataset && datasetsResp.datasets.length > 0) {
      setSelectedDataset(datasetsResp.datasets[0].name);
    }
  };

  const refreshSession = async (id: string) => {
    try {
      const snapshot = await api.getLab3Session<SessionSnapshot>(id);
      setSessionState(snapshot);
    } catch {
      setSessionState(null);
    }
  };

  useEffect(() => {
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    if (saved) {
      setSessionId(saved);
      void refreshSession(saved);
    }
    const bootstrap = async () => {
      setError(null);
      try {
        await fetchInitialData();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось загрузить Lab 3");
      }
    };
    void bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRefreshDatasets = async () => {
    setError(null);
    try {
      await fetchInitialData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось обновить список датасетов");
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setError(null);
    try {
      const uploaded = await api.uploadLab3Dataset<UploadResponse>(uploadFile);
      await fetchInitialData();
      setSelectedDataset(uploaded.dataset.name);
      setUploadFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки датасета");
    } finally {
      setUploading(false);
    }
  };

  const handleProfile = async () => {
    if (!selectedDataset) return;
    setLoadingProfile(true);
    setError(null);
    try {
      const profileResp = await api.getLab3Profile<Lab3Profile>(selectedDataset);
      setProfile(profileResp);
      const next: Record<string, string | null> = {};
      ROLE_KEYS.forEach((key) => {
        next[key] = profileResp.column_mapping.roles?.[key]?.column ?? null;
      });
      setOverrides(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось построить профиль датасета");
    } finally {
      setLoadingProfile(false);
    }
  };

  const handleNewDialog = () => {
    setChat([]);
    setSessionState(null);
    setSessionId(null);
    if (typeof window !== "undefined") window.localStorage.removeItem(STORAGE_KEY);
  };

  const handleResetContext = async () => {
    if (!sessionId) {
      handleNewDialog();
      return;
    }
    try {
      await api.resetLab3Session<{ status: string }, { session_id: string }>({ session_id: sessionId });
      await refreshSession(sessionId);
      setChat([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось очистить контекст");
    }
  };

  const submitQuestion = async (q: string) => {
    if (!selectedDataset || !q.trim()) return;
    setLoadingAsk(true);
    setError(null);
    const userMessage: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: q.trim(),
      createdAt: new Date().toISOString(),
    };
    setChat((prev) => [...prev, userMessage]);

    try {
      const body = {
        dataset_name: selectedDataset,
        question: q.trim(),
        column_overrides: Object.fromEntries(Object.entries(overrides).map(([k, v]) => [k, v || null])),
        max_tool_calls: maxToolCalls,
        use_critic: useCritic,
        analysis_mode: analysisMode,
        session_id: sessionId,
        include_history: true,
        reset_session: false,
      };
      const response = await api.askLab3Agent<AskResult, typeof body>(body);
      const assistant: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: response.final_answer,
        createdAt: new Date().toISOString(),
        payload: response,
      };
      setChat((prev) => [...prev, assistant]);
      setActiveTabs((prev) => ({ ...prev, [assistant.id]: "answer" }));
      setQuestion("");
      setSessionId(response.session_id);
      if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, response.session_id);
      await refreshSession(response.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось получить ответ агента");
    } finally {
      setLoadingAsk(false);
    }
  };

  const renderAssistantMessage = (message: Extract<ChatMessage, { role: "assistant" }>) => {
    const payload = message.payload;
    const active = activeTabs[message.id] ?? "answer";

    return (
      <div className="neu-card space-y-4 p-4" key={message.id}>
        <div className="text-xs text-slate-600">
          {modeLabel[payload.analysis_mode]} · {payload.elapsed_seconds} сек · {payload.llm_calls_count} LLM ·{" "}
          {payload.executed_tools.length} tools · {payload.dataset} · session {shortSession(payload.session_id)}
        </div>

        <div className="flex flex-wrap gap-2">
          {(["answer", "plan", "tools", "columns", "files", "raw"] as ResultTab[]).map((tab) => (
            <button
              key={tab}
              className={`neu-btn px-3 py-1 text-xs ${active === tab ? "ring-2 ring-slate-300" : ""}`}
              onClick={() => setActiveTabs((prev) => ({ ...prev, [message.id]: tab }))}
            >
              {tab === "answer" ? "Ответ" : tab === "plan" ? "План" : tab === "tools" ? "Tools" : tab === "columns" ? "Колонки" : tab === "files" ? "Файлы" : "Raw"}
            </button>
          ))}
        </div>

        {active === "answer" ? (
          <div className="neu-inset p-4">
            <MarkdownMessage content={payload.final_answer} />
            {payload.warnings.length > 0 ? (
              <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">
                {payload.warnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
              </div>
            ) : null}
            {payload.critic_review ? (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-medium">Critic review</summary>
                <pre className="mt-2 overflow-x-auto rounded-xl bg-slate-100 p-3 text-xs">
                  {JSON.stringify(payload.critic_review, null, 2)}
                </pre>
              </details>
            ) : null}
          </div>
        ) : null}

        {active === "plan" ? (
          <pre className="overflow-x-auto rounded-xl bg-slate-100 p-3 text-xs">{JSON.stringify(payload.planner_output, null, 2)}</pre>
        ) : null}

        {active === "tools" ? (
          <div className="space-y-2">
            {payload.executed_tools.map((tool, idx) => (
              <details key={`${message.id}-tool-${idx}`} className="neu-inset p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  {String(tool.tool ?? "tool")} · {String(tool.status ?? "status")}
                </summary>
                <pre className="mt-2 overflow-x-auto text-xs">{JSON.stringify(tool, null, 2)}</pre>
              </details>
            ))}
          </div>
        ) : null}

        {active === "columns" ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead>
                <tr className="text-slate-600">
                  <th className="p-2">role</th>
                  <th className="p-2">column</th>
                  <th className="p-2">confidence</th>
                  <th className="p-2">reason</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(payload.column_mapping.roles).map(([role, info]) => (
                  <tr key={`${message.id}-${role}`} className="border-t border-slate-200/70">
                    <td className="p-2">{role}</td>
                    <td className="p-2">{info.column ?? "-"}</td>
                    <td className="p-2">{info.confidence}</td>
                    <td className="p-2">{info.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {active === "files" ? (
          <div className="space-y-2 text-sm">
            {payload.output_files ? (
              Object.entries(payload.output_files).map(([key, value]) => (
                <p key={`${message.id}-${key}`}>
                  <span className="font-medium">{key}</span>: {value}
                </p>
              ))
            ) : (
              <p>Файлы не сгенерированы.</p>
            )}
            <a href={`${apiBaseUrl}/lab3/download-report`} target="_blank" rel="noreferrer" className="text-accent underline">
              Скачать отчёт markdown
            </a>
          </div>
        ) : null}

        {active === "raw" ? (
          <details open={false} className="neu-inset p-3">
            <summary className="cursor-pointer text-sm font-medium">Raw JSON ответа</summary>
            <pre className="mt-2 max-h-96 overflow-auto text-xs">{JSON.stringify(payload, null, 2)}</pre>
          </details>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {FOLLOW_UP_HINTS.map((hint) => (
            <button key={`${message.id}-${hint}`} className="neu-btn px-3 py-1 text-xs" onClick={() => setQuestion(hint)}>
              {hint}
            </button>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-5">
      <section className="neu-card space-y-3 p-5">
        <h1 className="text-2xl font-bold">Лаба 3 — LLM Analytics Agent</h1>
        <p className="text-sm text-slate-700">
          Универсальный workspace для анализа CSV/XLSX: определение ролей колонок, безопасные tools и диалог с контекстом.
        </p>
        <div className="flex flex-wrap gap-2 text-xs">
          {["Universal CSV/XLSX", "Safe tools", "Local Ollama", "Fast mode"].map((badge) => (
            <span key={badge} className="rounded-full bg-slate-100 px-3 py-1 text-slate-700 shadow-neu-inset">
              {badge}
            </span>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[390px_minmax(0,1fr)]">
        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <section className="neu-card space-y-3 p-4">
            <h2 className="text-base font-semibold">Датасет</h2>
            <select className="neu-inset w-full px-3 py-2 text-sm" value={selectedDataset} onChange={(e) => setSelectedDataset(e.target.value)}>
              {datasets.map((dataset) => (
                <option key={dataset.name} value={dataset.name}>
                  {dataset.name} ({dataset.type})
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <input type="file" accept=".csv,.xlsx,.xls" className="neu-inset w-full px-2 py-1 text-xs" onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)} />
              <button className="neu-btn px-3 py-1 text-xs" onClick={handleUpload} disabled={uploading || !uploadFile}>
                {uploading ? "..." : "Загрузить"}
              </button>
            </div>
            <button className="neu-btn w-full text-sm" onClick={handleRefreshDatasets}>
              Обновить список
            </button>
          </section>

          <section className="neu-card space-y-3 p-4">
            <h2 className="text-base font-semibold">Профиль</h2>
            <button className="neu-btn w-full text-sm" onClick={handleProfile} disabled={loadingProfile || !selectedDataset}>
              {loadingProfile ? "Анализ..." : "Проанализировать структуру"}
            </button>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="neu-inset p-2 text-center">
                <p className="font-semibold">{profile?.total_rows ?? "-"}</p>
                <p>rows</p>
              </div>
              <div className="neu-inset p-2 text-center">
                <p className="font-semibold">{profile?.total_columns ?? "-"}</p>
                <p>columns</p>
              </div>
              <div className="neu-inset p-2 text-center">
                <p className="font-semibold">{shortSession(sessionId)}</p>
                <p>session</p>
              </div>
            </div>
          </section>

          <section className="neu-card p-4">
            <details open>
              <summary className="cursor-pointer text-base font-semibold">Роли колонок</summary>
              <div className="mt-3 space-y-3">
                {ROLE_KEYS.map((role) => (
                  <div key={role} className="space-y-1">
                    <label className="text-xs font-medium">{role}</label>
                    <select
                      className="neu-inset w-full px-2 py-1 text-xs"
                      value={overrides[role] ?? ""}
                      onChange={(e) => setOverrides((prev) => ({ ...prev, [role]: e.target.value || null }))}
                    >
                      {roleOptions.map((option) => (
                        <option key={`${role}-${option || "empty"}`} value={option}>
                          {option || "(не выбрано)"}
                        </option>
                      ))}
                    </select>
                    <p className="text-[11px] text-slate-600">
                      conf: {profile?.column_mapping.roles?.[role]?.confidence ?? 0} · {profile?.column_mapping.roles?.[role]?.reason ?? "n/a"}
                    </p>
                  </div>
                ))}
              </div>
            </details>
          </section>

          <section className="neu-card space-y-3 p-4">
            <h2 className="text-base font-semibold">Настройки</h2>
            <label className="space-y-1 text-xs">
              <span>Режим анализа</span>
              <select className="neu-inset w-full px-2 py-1" value={analysisMode} onChange={(e) => setAnalysisMode(e.target.value as AskResult["analysis_mode"])}>
                <option value="fast">Быстрый</option>
                <option value="balanced">Сбалансированный</option>
                <option value="full">Полный</option>
              </select>
            </label>
            <label className="space-y-1 text-xs">
              <span>max_tool_calls</span>
              <input type="number" min={1} max={20} className="neu-inset w-full px-2 py-1" value={maxToolCalls} onChange={(e) => setMaxToolCalls(Number(e.target.value) || 6)} />
            </label>
            <label className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={useCritic} onChange={(e) => setUseCritic(e.target.checked)} />
              use_critic
            </label>
            <p className="text-[11px] text-slate-600">
              Быстрый режим использует эвристики и один LLM-вызов для финального ответа.
            </p>
          </section>

          <section className="neu-card space-y-3 p-4">
            <h2 className="text-base font-semibold">Сценарии</h2>
            <div className="flex flex-wrap gap-2">
              {scenarios.map((scenario) => (
                <button key={scenario.label} className="neu-btn px-2 py-1 text-xs" onClick={() => setQuestion(scenario.question)}>
                  {scenario.label}
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className="space-y-4">
          <section className="neu-card flex min-h-[560px] flex-col p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Аналитический чат</h2>
              <div className="flex gap-2">
                <button className="neu-btn px-3 py-1 text-xs" onClick={handleNewDialog}>
                  Новый диалог
                </button>
                <button className="neu-btn px-3 py-1 text-xs" onClick={handleResetContext}>
                  Очистить контекст
                </button>
              </div>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto pr-1">
              {chat.length === 0 ? (
                <div className="neu-inset p-4 text-sm text-slate-600">
                  Диалог пуст. Выберите сценарий или задайте свой вопрос, чтобы запустить анализ.
                </div>
              ) : null}
              {chat.map((message) =>
                message.role === "user" ? (
                  <div key={message.id} className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl bg-slate-100 px-4 py-2 text-sm text-slate-800 shadow-neu-inset">{message.content}</div>
                  </div>
                ) : (
                  renderAssistantMessage(message)
                )
              )}
            </div>

            <div className="mt-4 space-y-3 border-t border-slate-200/70 pt-3">
              <textarea
                className="neu-inset min-h-24 w-full px-3 py-2 text-sm"
                placeholder="Задайте вопрос агенту"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
              <div className="flex flex-wrap items-center gap-2">
                <button className="neu-btn" onClick={() => void submitQuestion(question)} disabled={loadingAsk || !selectedDataset}>
                  {loadingAsk ? "Отправка..." : "Отправить агенту"}
                </button>
                <p className="text-xs text-slate-600">
                  Session: {shortSession(sessionId)} · history: {sessionState?.history_length ?? 0}
                </p>
              </div>
              {error ? <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
            </div>
          </section>

          <details className="neu-card p-4">
            <summary className="cursor-pointer text-base font-semibold">Advanced: доступные tools</summary>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-600">
                    <th className="p-2">tool</th>
                    <th className="p-2">description</th>
                    <th className="p-2">required roles</th>
                  </tr>
                </thead>
                <tbody>
                  {tools.map((tool) => (
                    <tr key={tool.tool} className="border-t border-slate-200/70">
                      <td className="p-2">{tool.tool}</td>
                      <td className="p-2">{tool.description}</td>
                      <td className="p-2">{tool.required_roles.join(", ") || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </section>
      </div>
    </div>
  );
}
