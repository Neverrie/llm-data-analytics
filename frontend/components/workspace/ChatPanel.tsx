"use client";

import { ChatMessage } from "@/lib/api";
import { ArtifactPreviewCard } from "./ArtifactPreviewCard";
import { ChatComposer } from "./ChatComposer";
import { ChatThread } from "./ChatThread";
import { CodeBlockCard } from "./CodeBlockCard";
import { EmptyChatState } from "./EmptyChatState";
import { ExecutionBlock } from "./ExecutionBlock";

const progressSteps = ["Отправляем вопрос", "Модель генерирует код", "Sandbox выполняет Python", "Готовим итоговый ответ"];

export function ChatPanel({
  messages,
  onSend,
  loading,
  lab3Response,
  datasetName
}: {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  loading: boolean;
  lab3Response: any;
  datasetName?: string;
}) {
  const hasAssistantData = Boolean(lab3Response && (lab3Response.error || lab3Response.final_answer || (lab3Response.code_steps && lab3Response.code_steps.length)));
  return (
    <section className="main-panel chat-panel">
      {!messages.length ? <EmptyChatState datasetName={datasetName} onPrompt={onSend} /> : <ChatThread messages={messages} />}

      {loading ? (
        <div className="progress-card">
          <strong>Агент выполняет анализ...</strong>
          <ul>{progressSteps.map((s) => <li key={s}>{s}</li>)}</ul>
        </div>
      ) : null}

      {lab3Response?.error ? <article className="block-card"><strong>Ошибка</strong><pre className="code-pre error">{String(lab3Response.error)}</pre></article> : null}
      {lab3Response?.code_steps?.map((step: any, i: number) => <CodeBlockCard key={i} title={`Step ${i + 1}`} meta={`${step.status || "unknown"} · ${step.source || "llm"}`} code={step.code || ""} />)}
      {lab3Response?.code_steps?.map((step: any, i: number) => <ExecutionBlock key={`exec-${i}`} stdout={step.stdout} stderr={step.stderr} />)}
      {lab3Response?.generated_files?.map((f: any, i: number) => <ArtifactPreviewCard key={i} title="Generated file" value={String(f?.path || f?.name || "unknown")} />)}

      {hasAssistantData ? (
        <details className="raw compact"><summary>Raw response</summary><pre>{JSON.stringify(lab3Response || {}, null, 2)}</pre></details>
      ) : null}
      <ChatComposer onSend={onSend} loading={loading} />
    </section>
  );
}
