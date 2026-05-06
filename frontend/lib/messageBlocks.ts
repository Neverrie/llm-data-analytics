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

function cleanFinalTags(text: string): string {
  return String(text || "")
    .replace(/<\s*FINAL\s*>/gi, "")
    .replace(/<\s*\/\s*FINAL\s*>/gi, "")
    .trim();
}

function normalizePseudoTable(text: string): string {
  const source = cleanFinalTags(text);
  if (!source.includes("||")) return source;
  const rows = source
    .split("||")
    .map((r) => r.trim())
    .filter(Boolean);
  if (rows.length < 2) return source;
  const tableRows = rows.filter((r) => r.includes("|"));
  if (!tableRows.length) return source;
  const withLines = tableRows.join("\n");
  return source.replace(rows.join(" || "), withLines);
}

function parseMarkdownTable(text: string): { columns: string[]; rows: Record<string, unknown>[] } | null {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const start = lines.findIndex((line, idx) => line.includes("|") && idx + 1 < lines.length && /^[:\-\|\s]+$/.test(lines[idx + 1]));
  if (start === -1) return null;
  const header = lines[start]
    .split("|")
    .map((s) => s.trim())
    .filter(Boolean);
  if (!header.length) return null;
  const rows: Record<string, unknown>[] = [];
  for (let i = start + 2; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.includes("|")) break;
    const cells = line.split("|").map((s) => s.trim()).filter((_, idx, arr) => !(idx === 0 && arr[idx] === "")).filter(Boolean);
    if (!cells.length) continue;
    const row: Record<string, unknown> = {};
    header.forEach((h, idx) => {
      row[h] = cells[idx] ?? "";
    });
    rows.push(row);
  }
  if (!rows.length) return null;
  return { columns: header, rows };
}

function parseCompactPipeTable(text: string): { columns: string[]; rows: Record<string, unknown>[] } | null {
  const src = String(text || "");
  if (!src.includes("||")) return null;

  const groups = src
    .split("||")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((chunk) => chunk.split("|").map((v) => v.trim()).filter(Boolean));

  if (groups.length < 2) return null;
  const maybeHeader = groups.find((g) => g.length >= 2 && g.every((v) => /[A-Za-zА-Яа-я_]/.test(v)));
  if (!maybeHeader) return null;
  const columns = maybeHeader;
  const rows: Record<string, unknown>[] = [];

  groups.forEach((g) => {
    if (g.length !== columns.length) return;
    if (g.join("|") === columns.join("|")) return;
    const row: Record<string, unknown> = {};
    columns.forEach((c, idx) => {
      row[c] = g[idx] ?? "";
    });
    rows.push(row);
  });

  return rows.length ? { columns, rows } : null;
}

function stripPseudoTableNoise(text: string): string {
  const compactRow = /^\s*[^|\n]+(\s*\|\s*[^|\n]+){2,}\s*$/;
  return text
    .split("\n")
    .filter((line) => {
      const trimmed = line.trim();
      if (!trimmed) return true;
      const pipeCount = (trimmed.match(/\|/g) || []).length;
      if (trimmed.includes("||")) return false;
      if (/^[\|\-\:\s]+$/.test(trimmed) && pipeCount > 2) return false;
      if (pipeCount >= 2 && compactRow.test(trimmed)) return false;
      return true;
    })
    .join("\n")
    .trim();
}

function stripPipeDenseLines(text: string): string {
  return String(text || "")
    .split("\n")
    .filter((line) => {
      const trimmed = line.trim();
      if (!trimmed) return true;
      const pipeCount = (trimmed.match(/\|/g) || []).length;
      return pipeCount < 2;
    })
    .join("\n")
    .trim();
}

function rewriteMarkdownImageLinks(text: string, imageLinks: Record<string, string>): string {
  return String(text || "").replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_m, alt, src) => {
    const raw = String(src || "").trim();
    const fileName = raw.split("/").pop() || raw;
    const mapped = imageLinks[raw] || imageLinks[fileName];
    if (!mapped) return `![${alt}](${raw})`;
    return `![${alt}](${mapped})`;
  });
}

function extractImageNames(text: string): string[] {
  return Array.from(
    new Set(
      Array.from(String(text || "").matchAll(/([A-Za-z0-9_\-]+?\.(png|jpg|jpeg|webp))/gi)).map((m) => String(m[1] || ""))
    )
  );
}

export function normalizeLab3ResponseToBlocks(response: any): MessageBlock[] {
  const blocks: MessageBlock[] = [];
  const pendingFiles: MessageBlock[] = [];
  const imageLinks: Record<string, string> = {};
  const chartByName = new Map<string, { title: string; url: string }>();
  const seenFilePaths = new Set<string>();
  const rawFinal = String(response?.final_answer || "");
  const markdownImageRefs = new Set(
    Array.from(rawFinal.matchAll(/!\[[^\]]*\]\(([^)]+)\)/g)).map((m) => String(m[1] || "").split("/").pop() || String(m[1] || ""))
  );
  const isMentionedInFinal = (path: string) => {
    const name = String(path || "").split("/").pop() || String(path || "");
    return markdownImageRefs.has(name);
  };
  const upsertChart = (pathOrName: string, title?: string) => {
    const name = String(pathOrName || "").split("/").pop() || String(pathOrName || "");
    if (!name) return;
    if (chartByName.has(name)) return;
    chartByName.set(name, {
      title: title || name,
      url: `/api/lab3/generated-file?path=${encodeURIComponent(pathOrName)}`,
    });
  };

  const outputFiles = response?.output_files || {};
  for (const [name, path] of Object.entries(outputFiles)) {
    const pathStr = String(path);
    if (/\.(png|jpg|jpeg|webp)$/i.test(pathStr)) {
      const url = `/api/lab3/generated-file?path=${encodeURIComponent(pathStr)}`;
      imageLinks[pathStr] = url;
      imageLinks[pathStr.split("/").pop() || pathStr] = url;
      if (!isMentionedInFinal(pathStr)) upsertChart(pathStr, String(name));
    }
    if (!seenFilePaths.has(pathStr)) {
      seenFilePaths.add(pathStr);
      pendingFiles.push({ type: "file", title: String(name), filename: String(name), path: pathStr });
    }
  }

  const generatedFiles = response?.generated_files || [];
  if (Array.isArray(generatedFiles)) {
    generatedFiles.forEach((file: any) => {
      const path = String(file?.path || file?.name || "");
      if (!path) return;
      const publicPath = `/api/lab3/generated-file?path=${encodeURIComponent(path)}`;
      if (/\.(png|jpg|jpeg|webp)$/i.test(path)) {
        imageLinks[path] = publicPath;
        imageLinks[path.split("/").pop() || path] = publicPath;
        if (!isMentionedInFinal(path)) upsertChart(path, file?.title || file?.name || "График");
        return;
      }
      if (!seenFilePaths.has(path)) {
        seenFilePaths.add(path);
        pendingFiles.push({ type: "file", filename: file?.name || path, title: file?.title || "Файл", path });
      }
    });
  }

  const streamArtifacts = Array.isArray(response?.stream_artifacts) ? response.stream_artifacts : [];
  streamArtifacts.forEach((item: any) => {
    const path = String(item?.path || item?.name || item?.title || "");
    if (!path) return;
    const url = `/api/lab3/generated-file?path=${encodeURIComponent(path)}`;
    if (/\.(png|jpg|jpeg|webp)$/i.test(path)) {
      imageLinks[path] = url;
      imageLinks[path.split("/").pop() || path] = url;
      if (!isMentionedInFinal(path)) upsertChart(path, item?.title || item?.name || "График");
      return;
    }
    if (!seenFilePaths.has(path)) {
      seenFilePaths.add(path);
      pendingFiles.push({ type: "file", title: item?.title || item?.name || "Файл", filename: item?.name || path, path });
    }
  });

  let parsedTable: { columns: string[]; rows: Record<string, unknown>[] } | null = null;
  if (response?.final_answer) {
    const normalized = normalizePseudoTable(String(response.final_answer));
    parsedTable = parseMarkdownTable(normalized) || parseCompactPipeTable(normalized);
    const markdownBase = parsedTable ? stripPipeDenseLines(stripPseudoTableNoise(normalized)) : stripPseudoTableNoise(normalized);
    const cleaned = rewriteMarkdownImageLinks(markdownBase, imageLinks);
    blocks.push({ type: "markdown", content: cleaned });
    if (parsedTable) {
      blocks.push({ type: "table", title: "Таблица", columns: parsedTable.columns, rows: parsedTable.rows });
    }

    // If model mentioned image names in text, add charts only for names we can resolve to real links.
    extractImageNames(normalized).forEach((name) => {
      const mapped = imageLinks[name];
      if (mapped) upsertChart(name, name);
    });
  }
  chartByName.forEach((chart) => {
    blocks.push({ type: "chart", title: chart.title, url: chart.url });
  });

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

  (response?.warnings || []).forEach((w: string) => blocks.push({ type: "warning", content: String(w) }));
  if (Array.isArray(response?.debug_warnings) && response.debug_warnings.length) {
    blocks.push({ type: "raw", title: "Debug warnings", payload: response.debug_warnings });
  }
  if (response?.error) blocks.push({ type: "warning", content: String(response.error) });
  blocks.push(...pendingFiles);

  return blocks;
}

export function getMessageBlocks(message: ChatMessage): MessageBlock[] {
  const sourceBlocks = Array.isArray(message.blocks) && message.blocks.length
    ? (message.blocks as MessageBlock[])
    : [{ type: "markdown", content: message.content || "" } as MessageBlock];

  const normalized: MessageBlock[] = [];
  sourceBlocks.forEach((block) => {
    if (block.type !== "markdown") {
      normalized.push(block);
      return;
    }
    const content = String(block.content || "");
    const dataUrlMatches = Array.from(
      content.matchAll(/data:image\/(?:png|jpeg|jpg|webp);base64,[A-Za-z0-9+/=]+/gi)
    ).map((m) => String(m[0] || ""));
    if (!dataUrlMatches.length) {
      normalized.push(block);
      return;
    }
    const cleaned = content
      .replace(/<img[^>]*>/gi, "")
      .replace(/src\s*=\s*["']data:image\/(?:png|jpeg|jpg|webp);base64,[A-Za-z0-9+/=]+["']/gi, "")
      .trim();
    if (cleaned) normalized.push({ type: "markdown", content: cleaned });
    dataUrlMatches.forEach((url, idx) => normalized.push({ type: "chart", title: `image_${idx + 1}`, url }));
  });

  return normalized;
}
