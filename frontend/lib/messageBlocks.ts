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
  steps.forEach((step: any) => {
    const stepNumber = typeof step?.step === "number" ? step.step : undefined;
    const execution = step?.execution || {};

    if (step?.code) {
      blocks.push({
        type: "code",
        language: "python",
        code: String(step.code),
        status: execution?.status || step?.status,
        step: stepNumber
      });
    }

    if (execution?.stdout || execution?.stderr || execution?.status) {
      blocks.push({
        type: "execution",
        step: stepNumber,
        stdout: execution?.stdout ? String(execution.stdout) : "",
        stderr: execution?.stderr ? String(execution.stderr) : "",
        status: execution?.status || step?.status,
        elapsed_seconds: typeof execution?.elapsed_seconds === "number" ? execution.elapsed_seconds : undefined
      });
    }
  });

  const outputFiles = response?.output_files || {};
  for (const [name, path] of Object.entries(outputFiles)) {
    blocks.push({ type: "file", title: String(name), filename: String(name), path: String(path) });
  }

  (response?.generated_files || []).forEach((file: any) => {
    const path = String(file?.path || file?.name || "");
    const publicPath = `/api/lab3/generated-file?path=${encodeURIComponent(path)}`;
    if (/\.(png|jpg|jpeg)$/i.test(path)) {
      blocks.push({ type: "chart", title: "График", url: publicPath });
      return;
    }
    blocks.push({ type: "file", filename: file?.name || path, title: "Файл", path });
  });

  (response?.warnings || []).forEach((w: string) => blocks.push({ type: "warning", content: String(w) }));
  if (Array.isArray(response?.debug_warnings) && response.debug_warnings.length) {
    blocks.push({ type: "raw", title: "Debug warnings", payload: response.debug_warnings });
  }
  if (response?.error) blocks.push({ type: "warning", content: String(response.error) });

  blocks.push({ type: "raw", title: "Технический ответ", payload: response || {} });
  return blocks;
}

export function getMessageBlocks(message: ChatMessage): MessageBlock[] {
  if (Array.isArray(message.blocks) && message.blocks.length) return message.blocks as MessageBlock[];
  return [{ type: "markdown", content: message.content || "" }];
}
