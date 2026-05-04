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
    <section className="main-panel chat-panel workspace-screen">
      {datasetNotice ? <div className="dataset-notice">{datasetNotice}</div> : null}
      <div className="chat-thread-wrap">
        {!messages.length ? <EmptyChatState datasetName={datasetName} onPrompt={onSend} /> : <ChatThread messages={messages} />}
      </div>
      <div className="chat-status-wrap">
        <AgentRunProgress active={loading} />
        {lab3Response?.error ? <article className="block-card"><strong>Ошибка</strong><pre className="code-pre error">{String(lab3Response.error)}</pre></article> : null}
      </div>
      <ChatComposer onSend={onSend} loading={loading} />
    </section>
  );
}
