"use client";

import { MessageBlock } from "@/lib/messageBlocks";
import { api } from "@/lib/api";
import { AuthenticatedImage } from "./AuthenticatedImage";
import { CodeBlockCard } from "./CodeBlockCard";
import { DataTable } from "./DataTable";
import { ExecutionBlock } from "./ExecutionBlock";
import { MarkdownBlock } from "./MarkdownBlock";

async function downloadArtifact(artifactId: string, filename?: string) {
  const resp = await api.fetchArtifactDownload(artifactId);
  if (!resp.ok) throw new Error("Не удалось скачать артефакт");
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "artifact";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

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
            if (block.type === "execution") return <ExecutionBlock key={i} stdout={block.stdout} stderr={block.stderr} status={block.status} />;
            if (block.type === "table") return <DataTable key={i} columns={block.columns || []} rows={block.rows || []} />;
            if (block.type === "chart") {
              if (block.artifact_id) {
                return <AuthenticatedImage key={i} artifactId={block.artifact_id} className="message-chart" alt={block.title || "chart"} />;
              }
              return <img key={i} className="message-chart" src={block.preview_url || block.url} alt={block.title || "chart"} />;
            }
            if (block.type === "file") {
              return (
                <article key={i} className="block-card">
                  <strong>{block.title || block.filename || "Файл"}</strong>
                  {block.artifact_id ? (
                    <button
                      type="button"
                      className="muted"
                      onClick={() => void downloadArtifact(block.artifact_id as string, block.filename || block.title || "artifact")}
                    >
                      Скачать
                    </button>
                  ) : block.download_url ? (
                    <a href={block.download_url} target="_blank" rel="noreferrer" className="muted">Скачать</a>
                  ) : (
                    <span className="muted">{block.path || ""}</span>
                  )}
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
