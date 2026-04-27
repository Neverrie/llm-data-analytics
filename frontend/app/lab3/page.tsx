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
  | { id: string; role: "user"; content: string }
  | { id: string; role: "assistant"; content: string; payload: AskResult };

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
type RoleKey =
  | "id_column"
  | "text_column"
  | "rating_column"
  | "target_column"
  | "date_column"
  | "version_column"
  | "reply_column"
  | "reply_date_column"
  | "username_column"
  | "image_column";

const ROLE_PRIMARY: RoleKey[] = ["id_column", "text_column", "rating_column", "target_column", "date_column"];
const ROLE_EXTRA: RoleKey[] = ["version_column", "reply_column", "reply_date_column", "username_column", "image_column"];
const ROLE_ALL: RoleKey[] = [...ROLE_PRIMARY, ...ROLE_EXTRA];
const STORAGE_KEY = "lab3_session_id";

const ROLE_LABELS: Record<RoleKey, string> = {
  id_column: "ID / уникальный идентификатор",
  text_column: "Текстовая колонка",
  rating_column: "Оценка / рейтинг",
  target_column: "Целевая переменная",
  date_column: "Дата / время",
  version_column: "Версия продукта",
  reply_column: "Ответ компании",
  reply_date_column: "Дата ответа",
  username_column: "Имя пользователя",
  image_column: "Изображение / аватар",
};

const ROLE_HELP: Record<RoleKey, string> = {
  id_column: "Колонка, которая однозначно идентифицирует строку. Обычно не используется как признак.",
  text_column: "Свободный текст: отзыв, комментарий, описание. Нужен для тем, ключевых слов и prompt injection.",
  rating_column: "Числовая оценка/рейтинг. Нужна для анализа распределений и low/high сегментов.",
  target_column: "Колонка результата: passed, final_score, churn, label, outcome и т.п.",
  date_column: "Дата или время события. Нужна для динамики по времени и трендов.",
  version_column: "Версия приложения/сборки. Нужна для сравнения версий.",
  reply_column: "Ответ компании/модератора на отзыв. Нужен для анализа реакции.",
  reply_date_column: "Дата ответа компании. Нужна для оценки скорости ответа.",
  username_column: "Имя пользователя. Чувствительное поле, обычно не передаётся в LLM.",
  image_column: "Изображение/аватар. Чувствительное или нерелевантное поле.",
};

const REASON_MAP: Record<string, string> = {
  "no suitable column found": "Подходящая колонка не найдена",
  "id-like column detected": "Похоже на уникальный идентификатор",
  "column has free-text characteristics and matches text-like semantics": "Колонка похожа на свободный текст",
  "no suitable free-text column found": "Свободный текст не найден",
  "numeric score/rating-like column detected": "Название и значения похожи на рейтинг",
  "date-like object/string column detected": "Похоже на дату/время",
  "column name indicates software version": "Похоже на версию продукта",
  "reply-like column detected": "Похоже на колонку с ответом компании",
  "reply-date-like column detected": "Похоже на дату ответа",
  "username-like column detected": "Похоже на имя пользователя",
  "image-like column detected": "Похоже на изображение/аватар",
};

const BASE_SCENARIOS: Array<{ label: string; question: string }> = [
  { label: "Обзор датасета", question: "Сделай краткий обзор датасета: структура, типы колонок, пропуски и первые аналитические наблюдения." },
  { label: "Качество данных", question: "Проверь качество данных: пропуски, дубликаты, подозрительные значения и ограничения анализа." },
  { label: "Числовой анализ", question: "Проанализируй числовые колонки: распределения, средние значения, разброс и возможные выбросы." },
  { label: "Категориальный анализ", question: "Проанализируй категориальные колонки: частые значения, дисбаланс категорий и закономерности." },
  { label: "Корреляции", question: "Найди зависимости между числовыми колонками и объясни заметные корреляции." },
  { label: "Аномалии", question: "Найди потенциальные аномалии и выбросы в числовых колонках." },
  { label: "Prompt injection", question: "Проверь текстовые поля на возможные prompt injection инструкции и объясни защиту системы." },
  { label: "Итоговый отчёт", question: "Сформируй итоговый аналитический отчёт: структура, качество данных, наблюдения, ограничения и следующие шаги." },
];

const FOLLOW_UP_HINTS = ["Покажи подробнее", "Какие ограничения?", "Что проверить дальше?", "Сформируй вывод для отчёта"];

const MODE_LABEL: Record<AskResult["analysis_mode"], string> = {
  fast: "Быстрый",
  balanced: "Сбалансированный",
  full: "Полный",
};

function shortSession(sessionId: string | null) {
  if (!sessionId) return "-";
  return `${sessionId.slice(0, 8)}...`;
}

function formatReason(reason?: string) {
  if (!reason) return "Нет пояснения";
  const key = reason.trim().toLowerCase();
  for (const [src, dst] of Object.entries(REASON_MAP)) {
    if (src.toLowerCase() === key) return dst;
  }
  return reason;
}

function normalizeSelection(value: string) {
  return value.trim() ? value : null;
}

export default function Lab3Page() {
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [selectedDataset, setSelectedDataset] = useState("");
  const [profile, setProfile] = useState<Lab3Profile | null>(null);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [question, setQuestion] = useState("Сделай обзор датасета");
  const [analysisMode, setAnalysisMode] = useState<"fast" | "balanced" | "full">("fast");
  const [maxToolCalls, setMaxToolCalls] = useState(6);
  const [useCritic, setUseCritic] = useState(false);
  const [manualRoles, setManualRoles] = useState<Record<RoleKey, string | null>>({} as Record<RoleKey, string | null>);
  const [autoRoles, setAutoRoles] = useState<Record<RoleKey, string | null>>({} as Record<RoleKey, string | null>);
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
  const roleOptions = useMemo(() => ["", ...availableColumns], [availableColumns]);
  const hasReviewRoles = Boolean((manualRoles.text_column ?? autoRoles.text_column) && (manualRoles.rating_column ?? autoRoles.rating_column));

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
    void fetchInitialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const syncRoleStateFromProfile = (mapping: ColumnMapping) => {
    const auto = {} as Record<RoleKey, string | null>;
    ROLE_ALL.forEach((role) => {
      auto[role] = mapping.roles?.[role]?.column ?? null;
    });
    setAutoRoles(auto);
    setManualRoles(auto);
  };

  const handleProfile = async () => {
    if (!selectedDataset) return;
    setLoadingProfile(true);
    setError(null);
    try {
      const profileResp = await api.getLab3Profile<Lab3Profile>(selectedDataset);
      setProfile(profileResp);
      syncRoleStateFromProfile(profileResp.column_mapping);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось построить профиль датасета");
    } finally {
      setLoadingProfile(false);
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

  const handleResetRoles = () => {
    setManualRoles(autoRoles);
  };

  const handleNewDialog = () => {
    setChat([]);
    setSessionState(null);
    setSessionId(null);
    if (typeof window !== "undefined") window.localStorage.removeItem(STORAGE_KEY);
  };

  const handleResetContext = async () => {
    if (!sessionId) return handleNewDialog();
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
    setChat((prev) => [...prev, { id: `u-${Date.now()}`, role: "user", content: q.trim() }]);

    try {
      const column_overrides = Object.fromEntries(ROLE_ALL.map((role) => [role, normalizeSelection(manualRoles[role] ?? "")]));
      const body = {
        dataset_name: selectedDataset,
        question: q.trim(),
        column_overrides,
        max_tool_calls: maxToolCalls,
        use_critic: useCritic,
        analysis_mode: analysisMode,
        session_id: sessionId,
        include_history: true,
        reset_session: false,
      };
      const response = await api.askLab3Agent<AskResult, typeof body>(body);
      const assistantId = `a-${Date.now()}`;
      setChat((prev) => [...prev, { id: assistantId, role: "assistant", content: response.final_answer, payload: response }]);
      setActiveTabs((prev) => ({ ...prev, [assistantId]: "answer" }));
      setQuestion("");
      setSessionId(response.session_id);
      window.localStorage.setItem(STORAGE_KEY, response.session_id);
      await refreshSession(response.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось получить ответ агента");
    } finally {
      setLoadingAsk(false);
    }
  };

  const roleSummary = useMemo(() => {
    const text = manualRoles.text_column ?? autoRoles.text_column ?? "не выбрано";
    const rating = manualRoles.rating_column ?? autoRoles.rating_column ?? "не выбрано";
    const date = manualRoles.date_column ?? autoRoles.date_column ?? "не выбрано";
    const target = manualRoles.target_column ?? autoRoles.target_column ?? "не выбрано";
    return `Текст: ${text} · Оценка: ${rating} · Дата: ${date} · Цель: ${target}`;
  }, [manualRoles, autoRoles]);

  const renderRoleControl = (role: RoleKey) => {
    const current = manualRoles[role] ?? "";
    const auto = autoRoles[role] ?? null;
    const roleInfo = profile?.column_mapping.roles?.[role];
    const manual = (current || null) !== auto;

    return (
      <div key={role} className="app-card-compact space-y-2 p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold">{ROLE_LABELS[role]}</p>
          <span className="text-[11px] app-muted">{role}</span>
        </div>
        <select className="app-select" value={current} onChange={(event) => setManualRoles((prev) => ({ ...prev, [role]: normalizeSelection(event.target.value) }))}>
          {roleOptions.map((option) => (
            <option key={`${role}-${option || "empty"}`} value={option}>
              {option || "(не выбрано)"}
            </option>
          ))}
        </select>
        <p className="text-xs app-muted">Уверенность: {roleInfo?.confidence ?? 0}</p>
        <p className="text-xs app-muted">Причина: {formatReason(roleInfo?.reason)}</p>
        <p className="text-xs app-muted">{ROLE_HELP[role]}</p>
        {!current ? <p className="text-xs app-muted">Не выбрано — tools, которым нужна эта роль, будут пропущены.</p> : null}
        {manual ? <span className="app-badge app-badge-primary">Выбрано вручную</span> : null}
      </div>
    );
  };

  const renderAssistantMessage = (message: Extract<ChatMessage, { role: "assistant" }>, isLastAssistant: boolean) => {
    const payload = message.payload;
    const active = activeTabs[message.id] ?? "answer";

    return (
      <div key={message.id} className="app-card space-y-4 p-4">
        <div className="app-badge app-badge-muted">
          {MODE_LABEL[payload.analysis_mode]} · {payload.elapsed_seconds} сек · {payload.llm_calls_count} LLM · {payload.executed_tools.length} tools · {payload.dataset}
        </div>

        <div className="app-tabs">
          {(["answer", "plan", "tools", "columns", "files", "raw"] as ResultTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              className={`app-tab ${active === tab ? "app-tab-active" : ""}`}
              onClick={() => setActiveTabs((prev) => ({ ...prev, [message.id]: tab }))}
            >
              {tab === "answer" ? "Ответ" : tab === "plan" ? "План" : tab === "tools" ? "Tools" : tab === "columns" ? "Колонки" : tab === "files" ? "Файлы" : "Raw"}
            </button>
          ))}
        </div>

        {active === "answer" ? (
          <div className="space-y-3">
            <MarkdownMessage content={payload.final_answer} />
            {payload.warnings.length > 0 ? (
              <div className="rounded-lg px-3 py-2 text-xs" style={{ background: "color-mix(in srgb, var(--warning) 14%, transparent)", color: "var(--warning)" }}>
                {payload.warnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
              </div>
            ) : null}
            {payload.critic_review ? (
              <details className="app-expansion">
                <summary>Critic review</summary>
                <pre className="app-code-block m-3">{JSON.stringify(payload.critic_review, null, 2)}</pre>
              </details>
            ) : null}
          </div>
        ) : null}

        {active === "plan" ? <pre className="app-code-block">{JSON.stringify(payload.planner_output, null, 2)}</pre> : null}
        {active === "tools" ? (
          <div className="space-y-2">
            {payload.executed_tools.map((tool, idx) => (
              <details key={`${message.id}-tool-${idx}`} className="app-expansion">
                <summary>
                  {String(tool.tool ?? "tool")} · {String(tool.status ?? "status")}
                </summary>
                <pre className="app-code-block m-3">{JSON.stringify(tool, null, 2)}</pre>
              </details>
            ))}
          </div>
        ) : null}
        {active === "columns" ? (
          <div className="overflow-x-auto">
            <table className="app-table text-xs">
              <thead>
                <tr>
                  <th>Роль</th>
                  <th>Колонка</th>
                  <th>Уверенность</th>
                  <th>Причина</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(payload.column_mapping.roles).map(([role, info]) => (
                  <tr key={`${message.id}-${role}`}>
                    <td>{ROLE_LABELS[role as RoleKey] ?? role}</td>
                    <td>{info.column ?? "-"}</td>
                    <td>{info.confidence}</td>
                    <td>{formatReason(info.reason)}</td>
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
                  <strong>{key}</strong>: {value}
                </p>
              ))
            ) : (
              <p>Файлы не сгенерированы.</p>
            )}
            <a href={`${apiBaseUrl}/lab3/download-report`} target="_blank" rel="noreferrer" className="font-semibold underline" style={{ color: "var(--primary)" }}>
              Скачать отчёт markdown
            </a>
          </div>
        ) : null}
        {active === "raw" ? <pre className="app-code-block">{JSON.stringify(payload, null, 2)}</pre> : null}

        {isLastAssistant ? (
          <div className="flex flex-wrap gap-2">
            {FOLLOW_UP_HINTS.map((hint) => (
              <button key={`${message.id}-${hint}`} className="app-button app-button-secondary" onClick={() => setQuestion(hint)}>
                {hint}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <section className="app-card space-y-3 p-6">
        <h1 className="text-2xl font-bold">Лаба 3 — LLM Analytics Agent</h1>
        <p className="text-sm app-muted">
          Универсальный агент анализирует выбранный CSV/XLSX-датасет, определяет роли колонок, вызывает безопасные tools и формирует аналитический ответ.
        </p>
        <div className="flex flex-wrap gap-2">
          {["Universal CSV/XLSX", "Safe tools", "Local Ollama", "Fast mode"].map((badge) => (
            <span key={badge} className="app-badge app-badge-muted">
              {badge}
            </span>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <aside className="space-y-4 xl:sticky xl:top-4 xl:self-start">
          <section className="app-card min-h-[240px] space-y-3 p-4">
            <h2 className="app-section-title text-base">Выбор датасета</h2>
            <select className="app-select" value={selectedDataset} onChange={(event) => setSelectedDataset(event.target.value)}>
              {datasets.map((dataset) => (
                <option key={dataset.name} value={dataset.name}>
                  {dataset.name} ({dataset.type})
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <input type="file" accept=".csv,.xlsx,.xls" className="app-input" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
              <button className="app-button app-button-secondary" onClick={handleUpload} disabled={uploading || !uploadFile}>
                {uploading ? "..." : "Загрузить"}
              </button>
            </div>
            <button className="app-button app-button-secondary" onClick={fetchInitialData}>
              Обновить список
            </button>
          </section>

          <section className="app-card space-y-3 p-4">
            <h2 className="app-section-title text-base">Профиль</h2>
            <button className="app-button app-button-primary" onClick={handleProfile} disabled={loadingProfile || !selectedDataset}>
              {loadingProfile ? "Анализ..." : "Проанализировать структуру"}
            </button>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="app-card-compact p-2 text-center">
                <p className="font-semibold">{profile?.total_rows ?? "-"}</p>
                <p className="app-muted">rows</p>
              </div>
              <div className="app-card-compact p-2 text-center">
                <p className="font-semibold">{profile?.total_columns ?? "-"}</p>
                <p className="app-muted">columns</p>
              </div>
              <div className="app-card-compact p-2 text-center">
                <p className="font-semibold">{shortSession(sessionId)}</p>
                <p className="app-muted">session</p>
              </div>
            </div>
          </section>

          <section className="app-card p-4">
            <details className="app-expansion" open>
              <summary>Роли колонок</summary>
              <div className="space-y-3 p-3">
                <p className="text-xs app-muted">{roleSummary}</p>
                <details className="app-expansion">
                  <summary>Зачем нужны роли колонок?</summary>
                  <p className="p-3 text-xs app-muted">
                    Агент не привязан к названиям колонок. Он определяет роли (текст, рейтинг, дата, целевая переменная), чтобы применять один набор tools к разным датасетам.
                    Если автоопределение ошиблось, роль можно исправить вручную.
                  </p>
                </details>

                <h3 className="text-sm font-semibold">Основные</h3>
                {ROLE_PRIMARY.map((role) => renderRoleControl(role))}
                <h3 className="text-sm font-semibold">Дополнительные</h3>
                {ROLE_EXTRA.map((role) => renderRoleControl(role))}

                <button className="app-button app-button-secondary w-full" onClick={handleResetRoles}>
                  Сбросить ручной выбор
                </button>
              </div>
            </details>
          </section>

          <section className="app-card space-y-3 p-4">
            <h2 className="app-section-title text-base">Настройки</h2>
            <label className="space-y-1">
              <span className="text-xs app-muted">Режим анализа</span>
              <select className="app-select" value={analysisMode} onChange={(event) => setAnalysisMode(event.target.value as AskResult["analysis_mode"])}>
                <option value="fast">Быстрый</option>
                <option value="balanced">Сбалансированный</option>
                <option value="full">Полный</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-xs app-muted">max_tool_calls</span>
              <input type="number" min={1} max={20} className="app-input" value={maxToolCalls} onChange={(event) => setMaxToolCalls(Number(event.target.value) || 6)} />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={useCritic} onChange={(event) => setUseCritic(event.target.checked)} />
              use_critic
            </label>
          </section>

          <section className="app-card space-y-3 p-4">
            <h2 className="app-section-title text-base">Сценарии</h2>
            <div className="flex flex-wrap gap-2">
              {scenarios.map((scenario) => (
                <button key={scenario.label} className="app-button app-button-secondary" onClick={() => setQuestion(scenario.question)}>
                  {scenario.label}
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className="space-y-4">
          <section className="app-card flex min-h-[640px] flex-col p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="app-section-title">Аналитический чат</h2>
              <div className="flex gap-2">
                <button className="app-button app-button-ghost" onClick={handleNewDialog}>
                  Новый диалог
                </button>
                <button className="app-button app-button-ghost" onClick={handleResetContext}>
                  Очистить контекст
                </button>
              </div>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto pr-1">
              {chat.length === 0 ? (
                <div className="app-card-compact space-y-2 p-4">
                  <p className="font-semibold">Выберите сценарий или задайте вопрос</p>
                  <ul className="list-disc space-y-1 pl-5 text-sm app-muted">
                    <li>Сделай обзор датасета</li>
                    <li>Найди пропуски и ограничения</li>
                    <li>Какие числовые колонки выглядят важными?</li>
                  </ul>
                </div>
              ) : null}

              {chat.map((message, idx) => {
                if (message.role === "user") {
                  return (
                    <div key={message.id} className="flex justify-end">
                      <div className="max-w-[85%] rounded-xl px-4 py-2 text-sm" style={{ background: "var(--primary-soft)", border: "1px solid color-mix(in srgb, var(--primary) 30%, var(--border))" }}>
                        {message.content}
                      </div>
                    </div>
                  );
                }
                const isLastAssistant = !chat.slice(idx + 1).some((item) => item.role === "assistant");
                return renderAssistantMessage(message, isLastAssistant);
              })}
            </div>

            <div className="mt-4 space-y-3 border-t pt-3" style={{ borderColor: "var(--border)" }}>
              <textarea className="app-textarea min-h-24" placeholder="Задайте вопрос агенту" value={question} onChange={(event) => setQuestion(event.target.value)} />
              <div className="flex flex-wrap items-center gap-2">
                <button className="app-button app-button-primary" onClick={() => void submitQuestion(question)} disabled={loadingAsk || !selectedDataset}>
                  {loadingAsk ? "Отправка..." : "Отправить агенту"}
                </button>
                <span className="app-badge app-badge-muted">Session: {shortSession(sessionId)} · history: {sessionState?.history_length ?? 0}</span>
              </div>
              {error ? (
                <p className="rounded-lg px-3 py-2 text-sm" style={{ background: "color-mix(in srgb, var(--danger) 14%, transparent)", color: "var(--danger)" }}>
                  {error}
                </p>
              ) : null}
            </div>
          </section>

          <details className="app-expansion">
            <summary>Advanced: доступные tools</summary>
            <div className="p-3">
              <div className="overflow-x-auto">
                <table className="app-table text-xs">
                  <thead>
                    <tr>
                      <th>tool</th>
                      <th>description</th>
                      <th>required roles</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tools.map((tool) => (
                      <tr key={tool.tool}>
                        <td>{tool.tool}</td>
                        <td>{tool.description}</td>
                        <td>{tool.required_roles.join(", ") || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </details>
        </section>
      </div>
    </div>
  );
}
