"use client";

import { MessageBlock } from "@/lib/messageBlocks";
import { CodeBlockCard } from "./CodeBlockCard";
import { DataTable } from "./DataTable";
import { ExecutionBlock } from "./ExecutionBlock";
import { MarkdownBlock } from "./MarkdownBlock";

export function MessageBubble({
  role,
  content,
  blocks = []
}: {
  role: "user" | "assistant" | "system";
  content: string;
  blocks?: MessageBlock[];
}) {
  const renderBlocks = blocks.length ? blocks : ([{ type: "markdown", content }] as MessageBlock[]);

  return (
    <div className={`message ${role}`}>
      {role !== "assistant" ? <p>{content}</p> : null}
      {role === "assistant" ? (
        <div className="assistant-blocks">
          {renderBlocks.map((block, i) => {
            if (block.type === "markdown") return <MarkdownBlock key={i} content={block.content} />;
            if (block.type === "code") return <CodeBlockCard key={i} title={`Шаг ${block.step || i + 1}`} meta={block.status} code={block.code} />;
            if (block.type === "execution") return <ExecutionBlock key={i} stdout={block.stdout} stderr={block.stderr} />;
            if (block.type === "table") return <DataTable key={i} columns={block.columns || []} rows={block.rows || []} />;
            if (block.type === "chart") return <img key={i} className="message-chart" src={block.url} alt={block.title || "chart"} />;
            if (block.type === "file") {
              return (
                <article key={i} className="block-card">
                  <strong>{block.title || block.filename || "Файл"}</strong>
                  <span className="muted">{block.path || block.download_url || ""}</span>
                </article>
              );
            }
            if (block.type === "warning") return <details key={i} className="raw compact"><summary>Предупреждение</summary><pre>{block.content}</pre></details>;
            if (block.type === "raw") return <details key={i} className="raw compact"><summary>{block.title || "Raw"}</summary><pre>{JSON.stringify(block.payload, null, 2)}</pre></details>;
            return null;
          })}
        </div>
      ) : null}
    </div>
  );
}
