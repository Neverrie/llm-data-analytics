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

const ROLE_ORDER_PRIMARY: RoleKey[] = ["id_column", "text_column", "rating_column", "target_column", "date_column"];
const ROLE_ORDER_EXTRA: RoleKey[] = ["version_column", "reply_column", "reply_date_column", "username_column", "image_column"];
const ROLE_ALL: RoleKey[] = [...ROLE_ORDER_PRIMARY, ...ROLE_ORDER_EXTRA];

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
  id_column: "Колонка, которая однозначно идентифицирует строку. Обычно не используется как признак для анализа.",
  text_column:
    "Свободный текст: отзыв, комментарий, описание или сообщение. Нужна для анализа тем, ключевых слов и prompt injection.",
  rating_column:
    "Числовая оценка, рейтинг, score или количество баллов. Нужна для анализа низких/высоких оценок и распределений.",
  target_column:
    "Колонка, которую можно рассматривать как результат или целевой показатель: passed, final_score, churn, label, outcome и т.п.",
  date_column: "Дата или время события. Нужна для динамики по месяцам, трендов и временного анализа.",
  version_column: "Версия приложения, продукта или сборки. Нужна для сравнения версий.",
  reply_column: "Ответ компании или модератора на отзыв. Нужна для анализа реакции на обращения.",
  reply_date_column: "Дата ответа компании. Нужна для расчёта задержки ответа.",
  username_column: "Имя пользователя. Считается чувствительным полем и обычно не передаётся в LLM.",
  image_column: "Ссылка на изображение или аватар. Считается чувствительным/нерелевантным полем и обычно исключается.",
};

const REASON_MAP: Record<string, string> = {
  "no suitable column found": "Подходящая колонка не найдена",
  "id-like column detected": "Похоже на уникальный идентификатор",
  "column has free-text characteristics and matches text-like semantics": "Колонка похожа на свободный текст",
  "no suitable free-text column found": "Свободный текст не найден",
  "numeric score/rating-like column detected": "Название и значения похожи на оценку/рейтинг",
  "date-like object/string column detected": "Похоже на колонку с датой/временем",
  "column name indicates software version": "Название похоже на версию продукта",
  "reply-like column detected": "Похоже на колонку ответа компании",
  "reply-date-like column detected": "Похоже на дату ответа",
  "username-like column detected": "Похоже на имя пользователя",
  "image-like column detected": "Похоже на колонку изображения/аватара",
};

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

const FOLLOW_UP_HINTS = ["Покажи подробнее", "Какие ограничения?", "Что проверить дальше?", "Сформируй вывод для отчёта"];
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

function formatReason(reason: string | undefined): string {
  if (!reason) return "Нет объяснения от backend";
  const normalized = reason.trim().toLowerCase();
  for (const [source, target] of Object.entries(REASON_MAP)) {
    if (normalized === source.toLowerCase()) return target;
  }
  return reason;
}

function normalizeRoleSelection(value: string): string | null {
  return value.trim() ? value : null;
}

export default function Lab3Page() {
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>("");
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
  const hasReviewRoles = Boolean(
    (manualRoles.text_column ?? autoRoles.text_column) && (manualRoles.rating_column ?? autoRoles.rating_column),
  );

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

  const applyProfileRoles = (mapping: ColumnMapping) => {
    const auto: Record<RoleKey, string | null> = {} as Record<RoleKey, string | null>;
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
      applyProfileRoles(profileResp.column_mapping);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось построить профиль датасета");
    } finally {
      setLoadingProfile(false);
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
      const roleOverrides = Object.fromEntries(ROLE_ALL.map((role) => [role, normalizeRoleSelection(manualRoles[role] ?? "")]));
      const body = {
        dataset_name: selectedDataset,
        question: q.trim(),
        column_overrides: roleOverrides,
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

  const roleSummary = useMemo(() => {
    const text = manualRoles.text_column ?? autoRoles.text_column ?? "не выбрано";
    const rating = manualRoles.rating_column ?? autoRoles.rating_column ?? "не выбрано";
    const date = manualRoles.date_column ?? autoRoles.date_column ?? "не выбрано";
    const target = manualRoles.target_column ?? autoRoles.target_column ?? "не выбрано";
    return `Текст: ${text} · Оценка: ${rating} · Дата: ${date} · Цель: ${target}`;
  }, [manualRoles, autoRoles]);

  const renderRoleControl = (role: RoleKey) => {
    const currentValue = manualRoles[role] ?? "";
    const autoValue = autoRoles[role] ?? null;
    const roleInfo = profile?.column_mapping.roles?.[role];
    const selectedManually = (currentValue || null) !== autoValue;

    return (
      <div key={role} className="space-y-2 rounded-xl p-3" style={{ border: "1px solid var(--border)", background: "var(--panel-strong)" }}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-semibold app-text">{ROLE_LABELS[role]}</p>
          <span className="text-[11px] muted-text">{role}</span>
        </div>

        <select
          className="neu-inset w-full px-2 py-2 text-sm"
          value={currentValue}
          onChange={(event) => setManualRoles((prev) => ({ ...prev, [role]: normalizeRoleSelection(event.target.value) }))}
        >
          {roleOptions.map((option) => (
            <option key={`${role}-${option || "empty"}`} value={option}>
              {option || "(не выбрано)"}
            </option>
          ))}
        </select>

        <div className="space-y-1 text-xs muted-text">
          <p>Уверенность: {roleInfo?.confidence ?? 0}</p>
          <p>Причина: {formatReason(roleInfo?.reason)}</p>
          <p>{ROLE_HELP[role]}</p>
          {!currentValue ? <p>Не выбрано — tools, которым нужна эта роль, будут пропущены.</p> : null}
        </div>

        {selectedManually ? <span className="badge-manual inline-flex px-2 py-1 text-[11px]">Выбрано вручную</span> : null}
      </div>
    );
  };

  const renderAssistantMessage = (
    message: Extract<ChatMessage, { role: "assistant" }>,
    isLastAssistant: boolean,
  ) => {
    const payload = message.payload;
    const active = activeTabs[message.id] ?? "answer";

    return (
      <div className="neu-card space-y-4 p-4" key={message.id}>
        <div className="accent-chip inline-flex px-3 py-1 text-xs">
          {modeLabel[payload.analysis_mode]} · {payload.elapsed_seconds} сек · {payload.llm_calls_count} LLM-вызовов · {payload.executed_tools.length} tools ·{" "}
          {payload.dataset} · {shortSession(payload.session_id)}
        </div>

        <div className="flex flex-wrap gap-2">
          {(["answer", "plan", "tools", "columns", "files", "raw"] as ResultTab[]).map((tab) => (
            <button
              key={tab}
              className="neu-btn px-3 py-1 text-xs"
              style={active === tab ? { borderColor: "var(--accent)" } : undefined}
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
              <div className="warning-box mt-3 px-3 py-2 text-xs">
                {payload.warnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
              </div>
            ) : null}
            {payload.critic_review ? (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-medium app-text">Critic review</summary>
                <pre className="json-block mt-2 overflow-x-auto p-3 text-xs">{JSON.stringify(payload.critic_review, null, 2)}</pre>
              </details>
            ) : null}
          </div>
        ) : null}

        {active === "plan" ? <pre className="json-block overflow-x-auto p-3 text-xs">{JSON.stringify(payload.planner_output, null, 2)}</pre> : null}

        {active === "tools" ? (
          <div className="space-y-2">
            {payload.executed_tools.map((tool, idx) => (
              <details key={`${message.id}-tool-${idx}`} className="neu-inset p-3">
                <summary className="cursor-pointer text-sm font-medium app-text">
                  {String(tool.tool ?? "tool")} · {String(tool.status ?? "status")}
                </summary>
                <pre className="json-block mt-2 overflow-x-auto p-3 text-xs">{JSON.stringify(tool, null, 2)}</pre>
              </details>
            ))}
          </div>
        ) : null}

        {active === "columns" ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead>
                <tr className="muted-text">
                  <th className="soft-border border-b p-2">Роль</th>
                  <th className="soft-border border-b p-2">Колонка</th>
                  <th className="soft-border border-b p-2">Уверенность</th>
                  <th className="soft-border border-b p-2">Причина</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(payload.column_mapping.roles).map(([role, info]) => (
                  <tr key={`${message.id}-${role}`} className="soft-border border-b">
                    <td className="p-2">{ROLE_LABELS[role as RoleKey] ?? role}</td>
                    <td className="p-2">{info.column ?? "-"}</td>
                    <td className="p-2">{info.confidence}</td>
                    <td className="p-2">{formatReason(info.reason)}</td>
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
                  <span className="font-semibold">{key}</span>: {value}
                </p>
              ))
            ) : (
              <p>Файлы не сгенерированы.</p>
            )}
            <a href={`${apiBaseUrl}/lab3/download-report`} target="_blank" rel="noreferrer" className="font-medium underline" style={{ color: "var(--accent)" }}>
              Скачать отчёт markdown
            </a>
          </div>
        ) : null}

        {active === "raw" ? (
          <details className="neu-inset p-3">
            <summary className="cursor-pointer text-sm font-medium app-text">Raw JSON ответа</summary>
            <pre className="json-block mt-2 max-h-96 overflow-auto p-3 text-xs">{JSON.stringify(payload, null, 2)}</pre>
          </details>
        ) : null}

        {isLastAssistant ? (
          <div className="flex flex-wrap gap-2">
            {FOLLOW_UP_HINTS.map((hint) => (
              <button key={`${message.id}-${hint}`} className="neu-btn px-3 py-1 text-xs" onClick={() => setQuestion(hint)}>
                {hint}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div className="space-y-5">
      <section className="neu-card space-y-3 p-5">
        <h1 className="text-2xl font-bold app-text">Лаба 3 — LLM Analytics Agent</h1>
        <p className="text-sm muted-text">
          Универсальный workspace для анализа CSV/XLSX: определение ролей колонок, безопасные tools и диалог с контекстом.
        </p>
        <div className="flex flex-wrap gap-2 text-xs">
          {["Universal CSV/XLSX", "Safe tools", "Local Ollama", "Fast mode"].map((badge) => (
            <span key={badge} className="accent-chip px-3 py-1">
              {badge}
            </span>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[400px_minmax(0,1fr)]">
        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <section className="neu-card space-y-3 p-4">
            <h2 className="text-base font-semibold app-text">Выбор датасета</h2>
            <select className="neu-inset w-full px-3 py-2 text-sm" value={selectedDataset} onChange={(event) => setSelectedDataset(event.target.value)}>
              {datasets.map((dataset) => (
                <option key={dataset.name} value={dataset.name}>
                  {dataset.name} ({dataset.type})
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                className="neu-inset w-full px-2 py-1 text-xs"
                onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
              />
              <button className="neu-btn px-3 py-1 text-xs" onClick={handleUpload} disabled={uploading || !uploadFile}>
                {uploading ? "..." : "Загрузить"}
              </button>
            </div>
            <button className="neu-btn w-full text-sm" onClick={handleRefreshDatasets}>
              Обновить список
            </button>
          </section>

          <section className="neu-card space-y-3 p-4">
            <h2 className="text-base font-semibold app-text">Профиль датасета</h2>
            <button className="neu-btn w-full text-sm" onClick={handleProfile} disabled={loadingProfile || !selectedDataset}>
              {loadingProfile ? "Анализ..." : "Проанализировать структуру"}
            </button>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="neu-inset p-2 text-center">
                <p className="font-semibold app-text">{profile?.total_rows ?? "-"}</p>
                <p className="muted-text">rows</p>
              </div>
              <div className="neu-inset p-2 text-center">
                <p className="font-semibold app-text">{profile?.total_columns ?? "-"}</p>
                <p className="muted-text">columns</p>
              </div>
              <div className="neu-inset p-2 text-center">
                <p className="font-semibold app-text">{shortSession(sessionId)}</p>
                <p className="muted-text">session</p>
              </div>
            </div>
          </section>

          <section className="neu-card p-4">
            <details open>
              <summary className="cursor-pointer text-base font-semibold app-text">Роли колонок</summary>
              <p className="mt-2 text-xs muted-text">{roleSummary}</p>

              <details className="mt-3">
                <summary className="cursor-pointer text-xs font-medium app-text">Зачем нужны роли колонок?</summary>
                <p className="mt-2 text-xs muted-text">
                  Агент не привязан к конкретным названиям колонок. Сначала он пытается понять, какая колонка является текстом, рейтингом, датой или целевой переменной. Это
                  позволяет использовать один и тот же набор tools для разных CSV/XLSX. Если автоопределение ошиблось, роль можно исправить вручную.
                </p>
              </details>

              <div className="mt-3 space-y-3">
                <h3 className="text-sm font-semibold app-text">Основные</h3>
                {ROLE_ORDER_PRIMARY.map((role) => renderRoleControl(role))}

                <h3 className="pt-2 text-sm font-semibold app-text">Дополнительные</h3>
                {ROLE_ORDER_EXTRA.map((role) => renderRoleControl(role))}
              </div>

              <button className="neu-btn mt-3 w-full px-3 py-2 text-sm" onClick={handleResetRoles}>
                Сбросить ручной выбор
              </button>
            </details>
          </section>

          <section className="neu-card space-y-3 p-4">
            <h2 className="text-base font-semibold app-text">Настройки</h2>
            <label className="space-y-1 text-xs">
              <span className="muted-text">Режим анализа</span>
              <select className="neu-inset w-full px-2 py-1" value={analysisMode} onChange={(event) => setAnalysisMode(event.target.value as AskResult["analysis_mode"])}>
                <option value="fast">Быстрый</option>
                <option value="balanced">Сбалансированный</option>
                <option value="full">Полный</option>
              </select>
            </label>
            <label className="space-y-1 text-xs">
              <span className="muted-text">max_tool_calls</span>
              <input
                type="number"
                min={1}
                max={20}
                className="neu-inset w-full px-2 py-1"
                value={maxToolCalls}
                onChange={(event) => setMaxToolCalls(Number(event.target.value) || 6)}
              />
            </label>
            <label className="flex items-center gap-2 text-xs app-text">
              <input type="checkbox" checked={useCritic} onChange={(event) => setUseCritic(event.target.checked)} />
              use_critic
            </label>
            <p className="text-[11px] muted-text">Быстрый режим использует эвристики и один LLM-вызов для финального ответа.</p>
          </section>

          <section className="neu-card space-y-3 p-4">
            <h2 className="text-base font-semibold app-text">Быстрые сценарии</h2>
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
          <section className="neu-card flex min-h-[620px] flex-col p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold app-text">Аналитический чат</h2>
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
                <div className="neu-inset space-y-2 p-4 text-sm">
                  <p className="font-semibold app-text">Выберите сценарий или задайте вопрос</p>
                  <p className="muted-text">Примеры:</p>
                  <ul className="list-disc space-y-1 pl-5 muted-text">
                    <li>Сделай обзор датасета</li>
                    <li>Найди пропуски и ограничения</li>
                    <li>Какие числовые колонки выглядят важными?</li>
                  </ul>
                </div>
              ) : null}

              {chat.map((message, index) => {
                if (message.role === "user") {
                  return (
                    <div key={message.id} className="flex justify-end">
                      <div className="rounded-2xl px-4 py-2 text-sm app-text" style={{ maxWidth: "85%", background: "var(--panel-strong)", border: "1px solid var(--border)" }}>
                        {message.content}
                      </div>
                    </div>
                  );
                }
                const isLastAssistant = !chat.slice(index + 1).some((item) => item.role === "assistant");
                return renderAssistantMessage(message, isLastAssistant);
              })}
            </div>

            <div className="mt-4 space-y-3 border-t soft-border pt-3">
              <textarea
                className="neu-inset min-h-24 w-full px-3 py-2 text-sm"
                placeholder="Задайте вопрос агенту"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
              />
              <div className="flex flex-wrap items-center gap-2">
                <button className="neu-btn px-4 py-2" onClick={() => void submitQuestion(question)} disabled={loadingAsk || !selectedDataset}>
                  {loadingAsk ? "Отправка..." : "Отправить агенту"}
                </button>
                <span className="accent-chip px-3 py-1 text-xs">Session: {shortSession(sessionId)} · history: {sessionState?.history_length ?? 0}</span>
              </div>
              {error ? <p className="error-box px-3 py-2 text-sm">{error}</p> : null}
            </div>
          </section>

          <details className="neu-card p-4">
            <summary className="cursor-pointer text-base font-semibold app-text">Advanced: доступные tools</summary>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead>
                  <tr className="muted-text">
                    <th className="soft-border border-b p-2">tool</th>
                    <th className="soft-border border-b p-2">description</th>
                    <th className="soft-border border-b p-2">required roles</th>
                  </tr>
                </thead>
                <tbody>
                  {tools.map((tool) => (
                    <tr key={tool.tool} className="soft-border border-b">
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
