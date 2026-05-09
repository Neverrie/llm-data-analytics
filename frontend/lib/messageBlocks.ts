import { ChatMessage, toBackendUrl } from "./api";

export type MessageBlock =
  | { type: "markdown"; content: string }
  | { type: "code"; language: "python"; code: string; status?: string; step?: number }
  | { type: "execution"; step?: number; stdout?: string; stderr?: string; status?: string; elapsed_seconds?: number; files?: Array<Record<string, unknown>> }
  | { type: "table"; artifact_id?: string; columns?: string[]; rows?: Record<string, unknown>[]; title?: string; preview_url?: string; download_url?: string }
  | { type: "chart"; artifact_id?: string; url?: string; preview_url?: string; download_url?: string; mime_type?: string; title?: string }
  | { type: "file"; artifact_id?: string; filename?: string; download_url?: string; preview_url?: string; mime_type?: string; title?: string; path?: string }
  | { type: "warning"; content: string; details?: string; error_type?: string }
  | { type: "raw"; payload: unknown; title?: string };

export function normalizeLab3ResponseToBlocks(response: any): MessageBlock[] {
  const finalAnswer = String(response?.final_answer || "").trim();
  const blocks: MessageBlock[] = [];
  if (finalAnswer) blocks.push({ type: "markdown", content: finalAnswer });

  const artifacts = Array.isArray(response?.stream_artifacts) ? response.stream_artifacts : [];
  for (const item of artifacts) {
    const mime = String(item?.mime_type || "");
    const previewUrl = toBackendUrl(String(item?.preview_url || ""));
    const downloadUrl = toBackendUrl(String(item?.download_url || ""));
    const title = String(item?.title || item?.filename || "artifact");
    if (mime.startsWith("image/")) {
      blocks.push({ type: "chart", artifact_id: item?.artifact_id, title, url: previewUrl, preview_url: previewUrl, download_url: downloadUrl, mime_type: mime });
    } else {
      blocks.push({ type: "file", artifact_id: item?.artifact_id, title, filename: item?.filename || title, preview_url: previewUrl, download_url: downloadUrl, mime_type: mime });
    }
  }
  return blocks.length ? blocks : [{ type: "markdown", content: finalAnswer || "Ответ получен" }];
}

export function getMessageBlocks(message: ChatMessage): MessageBlock[] {
  const sourceBlocks = Array.isArray(message.blocks) && message.blocks.length
    ? (message.blocks as MessageBlock[])
    : [{ type: "markdown", content: message.content || "" } as MessageBlock];

  return sourceBlocks.map((block) => {
    if (block.type === "chart") {
      const src = toBackendUrl(String(block.preview_url || block.url || ""));
      return { ...block, url: src, preview_url: src };
    }
    if (block.type === "file") {
      return {
        ...block,
        preview_url: toBackendUrl(String(block.preview_url || "")),
        download_url: toBackendUrl(String(block.download_url || "")),
      };
    }
    return block;
  });
}
