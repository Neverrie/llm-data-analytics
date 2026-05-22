"use client";

import { MessageBlock } from "@/lib/messageBlocks";

type StepView = {
  step: number;
  code?: string;
  status?: string;
  stdout?: string;
  stderr?: string;
  elapsedSeconds?: number;
  files?: Array<Record<string, unknown>>;
};

function preview(text: string, max = 220) {
  const clean = (text || "").trim();
  if (!clean) return "";
  return clean.length > max ? `${clean.slice(0, max)}...` : clean;
}

function normalizeStatus(status?: string) {
  const s = String(status || "").toLowerCase();
  if (!s) return "pending";
  if (s === "success") return "success";
  if (s === "error" || s === "timeout") return s;
  if (s === "llm_tool_plan") return "planned";
  return s;
}

export function ExecutionStepsAccordion({ blocks }: { blocks: MessageBlock[] }) {
  const stepMap = new Map<number, StepView>();
  for (const b of blocks) {
    if (b.type !== "code" && b.type !== "execution") continue;
    const step = Number((b as any).step || 0) || 1;
    const curr = stepMap.get(step) || { step };
    if (b.type === "code") {
      curr.code = b.code;
      curr.status = curr.status || b.status;
    }
    if (b.type === "execution") {
      curr.stdout = b.stdout || "";
      curr.stderr = b.stderr || "";
      curr.status = b.status || curr.status;
      curr.elapsedSeconds = b.elapsed_seconds;
      curr.files = (b.files as Array<Record<string, unknown>> | undefined) || [];
    }
    stepMap.set(step, curr);
  }
  const steps = Array.from(stepMap.values()).sort((a, b) => a.step - b.step);
  if (!steps.length) return null;

  return (
    <section className="execution-steps">
      <details className="block-card">
        <summary className="step-summary">
          <strong>Выполненный код</strong>
          <span>{steps.length} шагов</span>
          <em>{steps.map((s) => normalizeStatus(s.status)).join(", ")}</em>
        </summary>
        {steps.map((s) => {
          const topPreview = s.stderr ? preview(s.stderr) : preview(s.stdout || "");
          const status = normalizeStatus(s.status);
          return (
            <article key={s.step} className="raw compact">
              <div className="step-summary">
                <strong>Шаг {s.step}</strong>
                <span>{status}</span>
                {topPreview ? <em>{topPreview}</em> : null}
              </div>
              {s.code ? <pre className="code-pre">{s.code}</pre> : null}
              {s.stdout ? <pre className="code-pre">{s.stdout}</pre> : null}
              {s.stderr ? <pre className="code-pre error">{s.stderr}</pre> : null}
              {typeof s.elapsedSeconds === "number" ? <div className="muted">elapsed: {s.elapsedSeconds}s</div> : null}
              {Array.isArray(s.files) && s.files.length ? (
                <ul className="muted">
                  {s.files.slice(0, 10).map((f, idx) => <li key={idx}>{String((f as any).filename || (f as any).path || "file")}</li>)}
                </ul>
              ) : null}
            </article>
          );
        })}
      </details>
    </section>
  );
}
