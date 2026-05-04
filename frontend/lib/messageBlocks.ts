import { ChatMessage } from "./api";

export type MessageBlock =
  | { type: "markdown"; content: string }
  | { type: "code"; language: "python"; code: string; status?: string; step?: number }
  | { type: "execution"; step?: number; stdout?: string; stderr?: string; status?: string; elapsed_seconds?: number }
  | { type: "table"; artifact_id?: string; columns?: string[]; rows?: Record<string, unknown>[]; title?: string }
  | { type: "chart"; artifact_id?: string; url?: string; title?: string }
  | { type: "file"; artifact_id?: string; filename?: string; download_url?: string; title?: string; path?: string }
  | { type: "warning"; content: string }
  | { type: "raw"; payload: unknown; title?: string };

export function normalizeLab3ResponseToBlocks(response: any): MessageBlock[] {
  const blocks: MessageBlock[] = [];
  if (response?.final_answer) blocks.push({ type: "markdown", content: String(response.final_answer) });

  const steps = Array.isArray(response?.code_steps) ? response.code_steps : [];
  steps.forEach((step: any, idx: number) => {
    if (step?.code) {
      blocks.push({ type: "code", language: "python", code: String(step.code), status: step.status, step: idx + 1 });
    }
    blocks.push({
      type: "execution",
      step: idx + 1,
      stdout: step?.stdout ? String(step.stdout) : "",
      stderr: step?.stderr ? String(step.stderr) : "",
      status: step?.status,
      elapsed_seconds: typeof step?.elapsed_seconds === "number" ? step.elapsed_seconds : undefined
    });
  });

  const outputFiles = response?.output_files || {};
  for (const [name, path] of Object.entries(outputFiles)) {
    blocks.push({ type: "file", title: String(name), filename: String(name), path: String(path) });
  }
  (response?.generated_files || []).forEach((file: any) => {
    const path = String(file?.path || file?.name || "");
    if (path.endsWith(".png") || path.endsWith(".jpg") || path.endsWith(".jpeg")) {
      blocks.push({ type: "chart", title: "График", url: path });
      return;
    }
    blocks.push({ type: "file", filename: file?.name || path, title: "Файл", path });
  });

  (response?.warnings || []).forEach((w: string) => blocks.push({ type: "warning", content: String(w) }));
  (response?.debug_warnings || []).forEach((w: string) => blocks.push({ type: "warning", content: String(w) }));
  if (response?.error) blocks.push({ type: "warning", content: String(response.error) });

  blocks.push({ type: "raw", title: "Технический ответ", payload: response || {} });
  return blocks;
}

export function getMessageBlocks(message: ChatMessage): MessageBlock[] {
  if (Array.isArray(message.blocks) && message.blocks.length) return message.blocks as MessageBlock[];
  return [{ type: "markdown", content: message.content || "" }];
}

