"use client";

import { useEffect, useMemo, useState } from "react";
import { SectionCard } from "../../components/SectionCard";
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

type Lab3Profile = {
  dataset_name: string;
  total_rows: number;
  total_columns: number;
  columns: string[];
  dtypes: Record<string, string>;
  missing_values: Record<string, number>;
  sample_values: Record<string, string[]>;
  column_mapping: {
    roles: Record<string, RoleMatch>;
    numeric_columns: string[];
    categorical_columns: string[];
  };
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
  column_mapping: {
    roles: Record<string, RoleMatch>;
    numeric_columns: string[];
    categorical_columns: string[];
  };
  planner_output: { plan: string; tool_calls: Array<{ tool: string; arguments: Record<string, unknown> }> };
  executed_tools: Array<Record<string, unknown>>;
  final_answer: string;
  critic_review?: { passed: boolean; issues: string[]; recommendations: string[] } | null;
  output_files?: Record<string, string>;
};

type UploadResponse = {
  status: string;
  dataset: { name: string; type: string; rows: number; columns: number };
};

const BASE_SCENARIOS: Array<{ label: string; question: string }> = [
  {
    label: "Обзор датасета",
    question: "Сделай краткий обзор датасета: структура, типы колонок, пропуски и первые аналитические наблюдения."
  },
  {
    label: "Качество данных",
    question: "Проверь качество данных: пропуски, дубликаты, подозрительные значения и ограничения анализа."
  },
  {
    label: "Числовой анализ",
    question: "Проанализируй числовые колонки: распределения, средние значения, разброс и возможные выбросы."
  },
  {
    label: "Категориальный анализ",
    question: "Проанализируй категориальные колонки: частые значения, дисбаланс категорий и возможные закономерности."
  },
  {
    label: "Корреляции и зависимости",
    question: "Найди возможные зависимости между числовыми колонками и объясни самые заметные корреляции."
  },
  {
    label: "Аномалии",
    question: "Найди потенциальные аномалии и выбросы в числовых колонках, объясни почему они могут быть важны."
  },
  {
    label: "Prompt injection check",
    question: "Проверь текстовые поля на возможные prompt injection инструкции и объясни, как система от них защищается."
  },
  {
    label: "Итоговый отчёт",
    question:
      "Сформируй итоговый аналитический отчёт по датасету: структура, качество данных, ключевые наблюдения, ограничения и что проверить дальше."
  }
];

const REVIEW_SCENARIOS: Array<{ label: string; question: string }> = [
  { label: "Проблемы пользователей", question: "Какие основные проблемы пользователи отмечают в низкооценённых отзывах?" },
  { label: "Негативные отзывы", question: "Какие темы чаще всего встречаются в негативных отзывах?" },
  { label: "Анализ отзывов по времени", question: "Есть ли ухудшение оценок со временем и в какие периоды?" }
];

const ROLE_KEYS = [
  "id_column",
  "text_column",
  "rating_column",
  "target_column",
  "date_column",
  "version_column",
  "reply_column",
  "reply_date_column"
] as const;

export default function Lab3Page() {
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [profile, setProfile] = useState<Lab3Profile | null>(null);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [question, setQuestion] = useState(BASE_SCENARIOS[0].question);
  const [analysisMode, setAnalysisMode] = useState<"fast" | "balanced" | "full">("fast");
  const [maxToolCalls, setMaxToolCalls] = useState(6);
  const [useCritic, setUseCritic] = useState(false);
  const [result, setResult] = useState<AskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadInfo, setUploadInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [overrides, setOverrides] = useState<Record<string, string | null>>({});

  const loadDatasetsAndTools = async () => {
    const [datasetsResp, toolsResp] = await Promise.all([
      api.getLab3Datasets<{ datasets: DatasetItem[] }>(),
      api.getLab3Tools<{ tools: ToolInfo[] }>()
    ]);
    setDatasets(datasetsResp.datasets);
    setTools(toolsResp.tools);
    if (!selectedDataset && datasetsResp.datasets.length > 0) {
      setSelectedDataset(datasetsResp.datasets[0].name);
    }
  };

  useEffect(() => {
    const bootstrap = async () => {
      setError(null);
      try {
        await loadDatasetsAndTools();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось загрузить данные Lab 3");
      }
    };
    bootstrap();
  }, []);

  const availableColumns = useMemo(() => profile?.columns ?? [], [profile]);

  const hasReviewContext = useMemo(() => {
    const roles = profile?.column_mapping?.roles;
    return Boolean(roles?.text_column?.column && roles?.rating_column?.column);
  }, [profile]);

  const handleUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadInfo(null);
    setError(null);
    try {
      const response = await api.uploadLab3Dataset<UploadResponse>(uploadFile);
      await loadDatasetsAndTools();
      setSelectedDataset(response.dataset.name);
      setUploadInfo(`Загружен файл ${response.dataset.name} (${response.dataset.rows} строк, ${response.dataset.columns} колонок)`);
      setUploadFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить файл");
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
      const nextOverrides: Record<string, string | null> = {};
      ROLE_KEYS.forEach((role) => {
        nextOverrides[role] = profileResp.column_mapping.roles?.[role]?.column ?? null;
      });
      setOverrides(nextOverrides);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось построить профиль датасета");
    } finally {
      setLoadingProfile(false);
    }
  };

  const handleAsk = async () => {
    if (!selectedDataset) return;
    setLoading(true);
    setError(null);
    try {
      const cleanedOverrides = Object.fromEntries(
        Object.entries(overrides).map(([key, value]) => [key, value && value.length > 0 ? value : null])
      );
      const data = await api.askLab3Agent<
        AskResult,
        {
          dataset_name: string;
          question: string;
          column_overrides: Record<string, string | null>;
          max_tool_calls: number;
          use_critic: boolean;
          analysis_mode: "fast" | "balanced" | "full";
        }
      >({
        dataset_name: selectedDataset,
        question,
        column_overrides: cleanedOverrides,
        max_tool_calls: maxToolCalls,
        use_critic: useCritic,
        analysis_mode: analysisMode
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось запустить агента");
    } finally {
      setLoading(false);
    }
  };

  const scenarioButtons = [...BASE_SCENARIOS, ...(hasReviewContext ? REVIEW_SCENARIOS : [])];

  return (
    <div className="space-y-6">
      <SectionCard title="Лаба 3 — LLM Analytics Agent">
        <p>
          Универсальный агент анализирует выбранный CSV/XLSX-датасет, автоматически определяет роли колонок,
          вызывает безопасные инструменты и формирует аналитический отчёт.
        </p>
      </SectionCard>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">1. Выбор датасета</h2>
        <select
          value={selectedDataset}
          onChange={(event) => setSelectedDataset(event.target.value)}
          className="neu-inset w-full px-3 py-2 text-sm"
        >
          {datasets.map((dataset) => (
            <option key={dataset.name} value={dataset.name}>
              {dataset.name} ({dataset.type})
            </option>
          ))}
        </select>
      </section>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">2. Загрузить свой датасет</h2>
        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
          className="neu-inset w-full px-3 py-2 text-sm"
        />
        <button className="neu-btn" onClick={handleUpload} disabled={uploading || !uploadFile}>
          {uploading ? "Загрузка..." : "Загрузить"}
        </button>
        {uploadInfo ? <p className="text-sm text-emerald-700">{uploadInfo}</p> : null}
      </section>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">3. Профиль датасета</h2>
        <button className="neu-btn" onClick={handleProfile} disabled={loadingProfile || !selectedDataset}>
          {loadingProfile ? "Анализ..." : "Проанализировать структуру"}
        </button>
        {profile ? (
          <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
            <p>
              <span className="font-medium">Rows:</span> {profile.total_rows}
            </p>
            <p>
              <span className="font-medium">Columns:</span> {profile.total_columns}
            </p>
            <p>
              <span className="font-medium">Dataset:</span> {profile.dataset_name}
            </p>
          </div>
        ) : null}
      </section>

      {profile ? (
        <section className="neu-card space-y-4 p-6">
          <h2 className="text-xl font-semibold">4. Роли колонок</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {ROLE_KEYS.map((role) => (
              <div key={role} className="space-y-2">
                <label className="text-sm font-medium">{role}</label>
                <select
                  className="neu-inset w-full px-3 py-2 text-sm"
                  value={overrides[role] ?? ""}
                  onChange={(event) => setOverrides((prev) => ({ ...prev, [role]: event.target.value || null }))}
                >
                  <option value="">(не выбрано)</option>
                  {availableColumns.map((column) => (
                    <option key={`${role}-${column}`} value={column}>
                      {column}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-slate-600">
                  confidence: {profile.column_mapping.roles?.[role]?.confidence ?? 0} | reason:{" "}
                  {profile.column_mapping.roles?.[role]?.reason ?? "n/a"}
                </p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">5. Быстрые универсальные сценарии</h2>
        <div className="flex flex-wrap gap-2">
          {scenarioButtons.map((scenario) => (
            <button key={scenario.label} className="neu-btn text-sm" onClick={() => setQuestion(scenario.question)}>
              {scenario.label}
            </button>
          ))}
        </div>
      </section>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">6. Вопрос к агенту</h2>
        <label className="text-sm font-medium">Задайте вопрос</label>
        <textarea
          className="neu-inset min-h-28 w-full px-3 py-2 text-sm"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <label className="space-y-2">
            <span className="text-sm font-medium">analysis_mode</span>
            <select
              className="neu-inset w-full px-3 py-2 text-sm"
              value={analysisMode}
              onChange={(event) => setAnalysisMode(event.target.value as "fast" | "balanced" | "full")}
            >
              <option value="fast">Быстрый</option>
              <option value="balanced">Сбалансированный</option>
              <option value="full">Полный</option>
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-sm font-medium">max_tool_calls</span>
            <input
              type="number"
              min={1}
              max={20}
              value={maxToolCalls}
              onChange={(event) => setMaxToolCalls(Number(event.target.value) || 6)}
              className="neu-inset w-full px-3 py-2 text-sm"
            />
          </label>
          <label className="mt-8 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={useCritic} onChange={(event) => setUseCritic(event.target.checked)} />
            use_critic
          </label>
        </div>
        <p className="text-sm text-slate-600">
          Быстрый режим использует эвристики и один LLM-вызов для финального ответа. Полный режим дополнительно
          включает LLM-планировщик и critic, поэтому работает дольше.
        </p>
        <button className="neu-btn" onClick={handleAsk} disabled={loading || !selectedDataset}>
          {loading ? "Запуск агента..." : "Запустить агента"}
        </button>
        {error ? <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
      </section>

      {result ? (
        <section className="neu-card space-y-4 p-6">
          <h2 className="text-xl font-semibold">7. Результат</h2>

          <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
            <p>analysis_mode: {result.analysis_mode}</p>
            <p>elapsed_seconds: {result.elapsed_seconds}</p>
            <p>llm_calls_count: {result.llm_calls_count}</p>
            <p>dataset: {result.dataset}</p>
          </div>

          {result.warnings?.length ? (
            <div className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <p className="font-medium">warnings:</p>
              <ul className="list-disc pl-5">
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <section className="rounded-xl bg-slate-50 px-4 py-3">
            <h3 className="mb-2 font-semibold">Финальный ответ</h3>
            <p className="whitespace-pre-wrap text-sm">{result.final_answer}</p>
          </section>

          <details className="neu-inset p-4">
            <summary className="cursor-pointer font-medium">План и tool calls</summary>
            <pre className="mt-2 overflow-x-auto text-xs md:text-sm">{JSON.stringify(result.planner_output, null, 2)}</pre>
          </details>

          <details className="neu-inset p-4">
            <summary className="cursor-pointer font-medium">Column mapping</summary>
            <pre className="mt-2 overflow-x-auto text-xs md:text-sm">{JSON.stringify(result.column_mapping, null, 2)}</pre>
          </details>

          <details className="neu-inset p-4">
            <summary className="cursor-pointer font-medium">Подробные результаты tools</summary>
            <pre className="mt-2 overflow-x-auto text-xs md:text-sm">{JSON.stringify(result.executed_tools, null, 2)}</pre>
          </details>

          {result.critic_review ? (
            <details className="neu-inset p-4">
              <summary className="cursor-pointer font-medium">Critic review</summary>
              <pre className="mt-2 overflow-x-auto text-xs md:text-sm">{JSON.stringify(result.critic_review, null, 2)}</pre>
            </details>
          ) : null}

          {result.output_files ? (
            <div className="space-y-1 text-sm">
              <p className="font-medium">Файлы:</p>
              {Object.entries(result.output_files).map(([key, value]) => (
                <p key={key}>
                  {key}: {value}
                </p>
              ))}
              <a
                href={`${apiBaseUrl}/lab3/download-report`}
                className="inline-flex rounded-xl px-2 py-1 font-medium text-accent underline"
                target="_blank"
                rel="noreferrer"
              >
                Скачать lab3_report.md
              </a>
            </div>
          ) : null}
        </section>
      ) : null}

      <details className="neu-card p-6">
        <summary className="cursor-pointer text-xl font-semibold">Advanced: доступные tools</summary>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
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
    </div>
  );
}
