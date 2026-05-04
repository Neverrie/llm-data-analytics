"use client";

import { useState } from "react";

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
  const [draft, setDraft] = useState("");

  return (
    <section className="main-panel chat-panel workspace-screen">
      {datasetNotice ? <div className="dataset-notice">{datasetNotice}</div> : null}
      <div className="chat-thread-wrap">
        {!messages.length ? <EmptyChatState datasetName={datasetName} onPrompt={setDraft} /> : <ChatThread messages={messages} />}
      </div>
      <div className="chat-status-wrap">
        <AgentRunProgress
          active={loading}
          stats={
            lab3Response
              ? {
                  provider: lab3Response.provider,
                  model: lab3Response.model,
                  llm_calls_count: lab3Response.llm_calls_count,
                  successful_executions_count: lab3Response.successful_executions_count,
                  elapsed_seconds: lab3Response.elapsed_seconds
                }
              : null
          }
        />
        {lab3Response?.error ? <article className="block-card"><strong>Ошибка</strong><pre className="code-pre error">{String(lab3Response.error)}</pre></article> : null}
      </div>
      <ChatComposer onSend={onSend} loading={loading} draft={draft} onDraftChange={setDraft} />
    </section>
  );
}

