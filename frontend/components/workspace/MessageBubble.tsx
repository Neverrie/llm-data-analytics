"use client";

import { MessageBlock } from "@/lib/messageBlocks";
import { api } from "@/lib/api";
import { AuthenticatedImage } from "./AuthenticatedImage";
import { DataTable } from "./DataTable";
import { ExecutionStepsAccordion } from "./ExecutionStepsAccordion";
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
  const hasChart = renderBlocks.some((b) => b.type === "chart");
  const stepBlocks = renderBlocks.filter((b) => b.type === "code" || b.type === "execution");
  const primaryBlocks = renderBlocks.filter((b) => b.type !== "code" && b.type !== "execution");
  const stripMdImages = (text: string) => text.replace(/!\[[^\]]*\]\([^)]+\)/g, "").replace(/^\s*!\[[^\]]*\]\s*$/gm, "").trim();

  return (
    <div className={`message ${role}`}>
      {role !== "assistant" ? <p>{content}</p> : null}
      {role === "assistant" ? (
        <div className="assistant-blocks">
          {primaryBlocks.map((block, i) => {
            if (block.type === "markdown") return <MarkdownBlock key={i} content={hasChart ? stripMdImages(block.content) : block.content} />;
            if (block.type === "table") return <DataTable key={i} columns={block.columns || []} rows={block.rows || []} />;
            if (block.type === "chart") {
              if (block.artifact_id) {
                return (
                  <article key={i} className="block-card">
                    <AuthenticatedImage artifactId={block.artifact_id} className="message-chart" alt={block.title || "chart"} />
                    {block.artifact_id ? (
                      <button type="button" className="muted" onClick={() => void downloadArtifact(block.artifact_id as string, block.title || "chart")}>
                        Скачать
                      </button>
                    ) : null}
                  </article>
                );
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
            if (block.type === "warning") {
              return (
                <article key={i} className="block-card warning-card">
                  <strong>Предупреждение</strong>
                  <pre className="code-pre error">{String(block.content || "Неизвестная ошибка")}</pre>
                  {block.details ? (
                    <details className="raw compact">
                      <summary>Показать детали</summary>
                      <pre className="code-pre">{block.details}</pre>
                    </details>
                  ) : null}
                </article>
              );
            }
            if (block.type === "raw") return <details key={i} className="raw compact"><summary>{block.title || "Raw"}</summary><pre>{JSON.stringify(block.payload, null, 2)}</pre></details>;
            return null;
          })}
          <ExecutionStepsAccordion blocks={stepBlocks} />
        </div>
      ) : null}
    </div>
  );
}
