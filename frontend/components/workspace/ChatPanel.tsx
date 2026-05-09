"use client";

import { useState } from "react";

import { ChatMessage } from "@/lib/api";
import { ChatComposer } from "./ChatComposer";
import { ChatThread } from "./ChatThread";
import { EmptyChatState } from "./EmptyChatState";

export function ChatPanel({
  messages,
  onSend,
  onStop,
  loading,
  lab3Response,
  datasetName,
  datasetNotice,
  interruptedRequest,
  onRetryInterrupted
}: {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  onStop?: () => void;
  loading: boolean;
  lab3Response: any;
  datasetName?: string;
  datasetNotice?: string;
  interruptedRequest?: { text: string } | null;
  onRetryInterrupted?: (text: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const streamLogs = Array.isArray(lab3Response?.logs) ? lab3Response.logs : Array.isArray(lab3Response?.stream_logs) ? lab3Response.stream_logs : [];
  const statusLine = streamLogs.length ? String(streamLogs[streamLogs.length - 1]) : "Обрабатываю запрос...";

  return (
    <section className="workspace-page agent-chat-page">
      {datasetNotice ? <div className="dataset-notice">{datasetNotice}</div> : null}
      <div className="agent-chat-feed workspace-screen-scroll">
        {interruptedRequest ? (
          <article className="workspace-section">
            <strong>Предупреждение</strong>
            <p className="muted">Предыдущий запрос мог быть прерван при перезагрузке страницы.</p>
            <button
              type="button"
              className="btn-secondary"
              disabled={loading}
              onClick={() => {
                if (!onRetryInterrupted) return;
                onRetryInterrupted(interruptedRequest.text);
              }}
            >
              Повторить запрос
            </button>
          </article>
        ) : null}
        {!messages.length ? <EmptyChatState datasetName={datasetName} onPrompt={setDraft} /> : <ChatThread messages={messages} />}
        {loading ? <div className="agent-status-line muted">{statusLine}</div> : null}
        {lab3Response?.error ? <article className="workspace-section"><strong>Ошибка</strong><pre className="code-pre error">{String(lab3Response.error)}</pre></article> : null}
      </div>
      <div className="agent-chat-composer">
        <article className="workspace-section">
          <ChatComposer onSend={onSend} onStop={onStop} loading={loading} draft={draft} onDraftChange={setDraft} />
        </article>
      </div>
    </section>
  );
}
