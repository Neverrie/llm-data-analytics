"use client";

import { ChatMessage } from "@/lib/api";
import { ArtifactPreviewCard } from "./ArtifactPreviewCard";
import { ChatComposer } from "./ChatComposer";
import { ChatThread } from "./ChatThread";
import { CodeBlockCard } from "./CodeBlockCard";
import { EmptyState } from "./EmptyState";
import { ExecutionBlock } from "./ExecutionBlock";

const progressSteps = [
  "Отправляем вопрос",
  "Модель генерирует код",
  "Sandbox выполняет Python",
  "Формируем ответ"
];

export function ChatPanel({
  messages,
  onSend,
  loading,
  lab3Response
}: {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  loading: boolean;
  lab3Response: any;
}) {
  if (!messages.length) {
    return <EmptyState title="Чат пуст" description="Выберите чат или создайте новый анализ слева." />;
  }

  return (
    <section className="main-panel chat-panel">
      <ChatThread messages={messages} />

      {loading ? (
        <div className="progress-card">
          <strong>Агент анализирует датасет...</strong>
          <ul>
            {progressSteps.map((step) => <li key={step}>{step}</li>)}
          </ul>
        </div>
      ) : null}

      {lab3Response?.final_answer ? <div className="assistant-summary">Ответ подготовлен и сохранён в чат.</div> : null}
      {lab3Response?.code_steps?.map((step: any, index: number) => (
        <CodeBlockCard key={index} title={`Step ${index + 1}`} meta={`${step.status || "unknown"} · ${step.source || "llm"}`} code={step.code || ""} />
      ))}
      {lab3Response?.code_steps?.map((step: any, index: number) => (
        <ExecutionBlock key={`exec-${index}`} stdout={step.stdout} stderr={step.stderr} />
      ))}
      {lab3Response?.generated_files?.map((file: any, index: number) => (
        <ArtifactPreviewCard key={index} title="Generated file" value={String(file?.path || file?.name || "unknown")} />
      ))}

      <details className="raw compact"><summary>Raw response</summary><pre>{JSON.stringify(lab3Response || {}, null, 2)}</pre></details>
      <ChatComposer onSend={onSend} loading={loading} />
    </section>
  );
}
