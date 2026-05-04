"use client";

import { ChatMessage } from "@/lib/api";
import { AgentRunProgress } from "./AgentRunProgress";
import { ChatComposer } from "./ChatComposer";
import { ChatThread } from "./ChatThread";
import { EmptyChatState } from "./EmptyChatState";

export function ChatPanel({
  messages,
  onSend,
  loading,
  lab3Response,
  datasetName,
  datasetNotice
}: {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  loading: boolean;
  lab3Response: any;
  datasetName?: string;
  datasetNotice?: string;
}) {
  return (
    <section className="main-panel chat-panel">
      {datasetNotice ? <div className="dataset-notice">{datasetNotice}</div> : null}
      {!messages.length ? <EmptyChatState datasetName={datasetName} onPrompt={onSend} /> : <ChatThread messages={messages} />}
      <AgentRunProgress active={loading} />
      {lab3Response?.error ? <article className="block-card"><strong>Ошибка</strong><pre className="code-pre error">{String(lab3Response.error)}</pre></article> : null}
      <ChatComposer onSend={onSend} loading={loading} />
    </section>
  );
}
