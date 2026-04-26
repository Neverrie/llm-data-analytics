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
  column_mapping: {
    roles: Record<string, RoleMatch>;
    numeric_columns: string[];
    categorical_columns: string[];
  };
  planner_output: { plan: string; tool_calls: Array<{ tool: string; arguments: Record<string, unknown> }> };
  planner_warnings?: string[];
  executed_tools: Array<Record<string, unknown>>;
  final_answer: string;
  critic_review: { passed: boolean; issues: string[]; recommendations: string[] };
  output_files?: Record<string, string>;
};

const ROLE_KEYS = [
  "text_column",
  "rating_column",
  "date_column",
  "version_column",
  "reply_column",
  "reply_date_column"
] as const;

const QUICK_SCENARIOS: Array<{ label: string; question: string }> = [
  { label: "Обзор датасета", question: "Сделай общий обзор датасета и ключевые метрики качества данных." },
  {
    label: "Проблемы пользователей",
    question: "Какие основные проблемы пользователи отмечают в низкооценённых отзывах?"
  },
  { label: "Динамика по времени", question: "Есть ли ухудшение оценок со временем и в какие месяцы?" },
  { label: "Анализ версий", question: "Какие версии приложения выглядят проблемными и почему?" },
  { label: "Негативные отзывы", question: "Какие темы чаще всего встречаются в негативных отзывах?" },
  { label: "Prompt injection check", question: "Есть ли отзывы, похожие на prompt injection?" },
  {
    label: "Полный отчёт",
    question: "Собери полный аналитический отчёт с основными наблюдениями, ограничениями и следующими шагами."
  }
];

export default function Lab3Page() {
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [profile, setProfile] = useState<Lab3Profile | null>(null);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [question, setQuestion] = useState("Какие основные проблемы пользователи отмечают в низкооценённых отзывах?");
  const [maxToolCalls, setMaxToolCalls] = useState(8);
  const [useCritic, setUseCritic] = useState(true);
  const [result, setResult] = useState<AskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [overrides, setOverrides] = useState<Record<string, string | null>>({});

  useEffect(() => {
    const bootstrap = async () => {
      setError(null);
      try {
        const [datasetsResp, toolsResp] = await Promise.all([
          api.getLab3Datasets<{ datasets: DatasetItem[] }>(),
          api.getLab3Tools<{ tools: ToolInfo[] }>()
        ]);
        setDatasets(datasetsResp.datasets);
        setTools(toolsResp.tools);
        if (datasetsResp.datasets.length > 0) {
          setSelectedDataset(datasetsResp.datasets[0].name);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось загрузить данные Lab 3");
      }
    };
    bootstrap();
  }, []);

  const availableColumns = useMemo(() => profile?.columns ?? [], [profile]);

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
        }
      >({
        dataset_name: selectedDataset,
        question,
        column_overrides: cleanedOverrides,
        max_tool_calls: maxToolCalls,
        use_critic: useCritic
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось запустить агента");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Лаба 3 — LLM Analytics Agent">
        <p>
          Универсальный агент анализирует выбранный CSV-датасет, автоматически определяет роли колонок, вызывает
          безопасные Python tools и формирует аналитический отчёт.
        </p>
      </SectionCard>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">Выбор датасета</h2>
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
        <h2 className="text-xl font-semibold">Профиль датасета</h2>
        <button className="neu-btn" onClick={handleProfile} disabled={loadingProfile}>
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
          <h2 className="text-xl font-semibold">Роли колонок</h2>
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
        <h2 className="text-xl font-semibold">Быстрые сценарии</h2>
        <div className="flex flex-wrap gap-2">
          {QUICK_SCENARIOS.map((scenario) => (
            <button key={scenario.label} className="neu-btn text-sm" onClick={() => setQuestion(scenario.question)}>
              {scenario.label}
            </button>
          ))}
        </div>
      </section>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">Запрос к агенту</h2>
        <label className="text-sm font-medium">Задайте вопрос агенту</label>
        <textarea
          className="neu-inset min-h-28 w-full px-3 py-2 text-sm"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-sm font-medium">max_tool_calls</span>
            <input
              type="number"
              min={1}
              max={20}
              value={maxToolCalls}
              onChange={(event) => setMaxToolCalls(Number(event.target.value) || 8)}
              className="neu-inset w-full px-3 py-2 text-sm"
            />
          </label>
          <label className="mt-8 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={useCritic} onChange={(event) => setUseCritic(event.target.checked)} />
            use_critic
          </label>
        </div>
        <button className="neu-btn" onClick={handleAsk} disabled={loading || !selectedDataset}>
          {loading ? "Запуск агента..." : "Запустить агента"}
        </button>
        {error ? <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
      </section>

      <section className="neu-card space-y-4 p-6">
        <h2 className="text-xl font-semibold">Доступные tools</h2>
        <div className="overflow-x-auto">
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
      </section>

      {result ? (
        <section className="neu-card space-y-4 p-6">
          <h2 className="text-xl font-semibold">Результат агента</h2>
          <p className="text-sm">
            <span className="font-medium">plan:</span> {result.planner_output?.plan ?? "-"}
          </p>
          <details className="neu-inset p-4">
            <summary className="cursor-pointer font-medium">Tool calls</summary>
            <pre className="mt-2 overflow-x-auto text-xs md:text-sm">
              {JSON.stringify(result.planner_output?.tool_calls ?? [], null, 2)}
            </pre>
          </details>
          <details className="neu-inset p-4">
            <summary className="cursor-pointer font-medium">Tool results</summary>
            <pre className="mt-2 overflow-x-auto text-xs md:text-sm">{JSON.stringify(result.executed_tools, null, 2)}</pre>
          </details>
          <section className="rounded-xl bg-slate-50 px-4 py-3">
            <h3 className="mb-2 font-semibold">Финальный ответ</h3>
            <p className="whitespace-pre-wrap text-sm">{result.final_answer}</p>
          </section>
          <details className="neu-inset p-4">
            <summary className="cursor-pointer font-medium">Critic review</summary>
            <pre className="mt-2 overflow-x-auto text-xs md:text-sm">{JSON.stringify(result.critic_review, null, 2)}</pre>
          </details>
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
          <details className="neu-inset p-4">
            <summary className="cursor-pointer font-medium">Raw JSON</summary>
            <pre className="mt-2 overflow-x-auto text-xs md:text-sm">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </section>
      ) : null}
    </div>
  );
}
