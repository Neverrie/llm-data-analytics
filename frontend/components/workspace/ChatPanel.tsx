"use client";

import { ChatMessage, DatasetItem } from "@/lib/api";
import { ArtifactPreviewCard } from "./ArtifactPreviewCard";
import { ChatComposer } from "./ChatComposer";
import { ChatThread } from "./ChatThread";
import { CodeBlockCard } from "./CodeBlockCard";
import { EmptyState } from "./EmptyState";
import { ExecutionBlock } from "./ExecutionBlock";

export function ChatPanel({
  messages,
  selectedDataset,
  datasets,
  onDataset,
  onSend,
  loading,
  lab3Response
}: {
  messages: ChatMessage[];
  selectedDataset: string;
  datasets: DatasetItem[];
  onDataset: (value: string) => void;
  onSend: (text: string) => void;
  loading: boolean;
  lab3Response: any;
}) {
  if (!messages.length) {
    return <EmptyState title="Чат не выбран" description="Создайте чат слева и отправьте первый вопрос." />;
  }

  return (
    <section className="main-panel">
      <div className="panel-row">
        <label>Dataset</label>
        <select value={selectedDataset} onChange={(e) => onDataset(e.target.value)}>
          {datasets.map((dataset) => <option key={dataset.id} value={dataset.name}>{dataset.name}</option>)}
        </select>
      </div>
      <ChatThread messages={messages} />
      {loading ? <div className="loading-card">Агент анализирует датасет... Формируем ответ.</div> : null}
      {lab3Response?.code_steps?.map((step: any, index: number) => (
        <CodeBlockCard key={index} title={`Step ${index + 1}`} meta={`${step.status || "unknown"} / ${step.source || "llm"}`} code={step.code || ""} />
      ))}
      {lab3Response?.code_steps?.map((step: any, index: number) => (
        <ExecutionBlock key={`exec-${index}`} stdout={step.stdout} stderr={step.stderr} />
      ))}
      {lab3Response?.generated_files?.map((file: any, index: number) => (
        <ArtifactPreviewCard key={index} title="Generated file" value={String(file?.path || file?.name || "unknown")} />
      ))}
      <ChatComposer onSend={onSend} loading={loading} />
    </section>
  );
}

