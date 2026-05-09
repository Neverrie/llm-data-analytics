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
  return clean.length > max ? `${clean.slice(0, max)}…` : clean;
}

export function ExecutionStepsAccordion({ blocks }: { blocks: MessageBlock[] }) {
  const stepMap = new Map<number, StepView>();
  for (const b of blocks) {
    if (b.type !== "code" && b.type !== "execution") continue;
    const step = Number((b as any).step || 0) || 1;
    const curr = stepMap.get(step) || { step };
    if (b.type === "code") {
      curr.code = b.code;
      curr.status = b.status || curr.status;
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
      {steps.map((s) => {
        const topPreview = s.stderr ? preview(s.stderr) : preview(s.stdout || "");
        return (
          <details key={s.step} className="block-card">
            <summary className="step-summary">
              <strong>Шаг {s.step}</strong>
              <span>{s.status || "unknown"}</span>
              {topPreview ? <em>{topPreview}</em> : null}
            </summary>
            {s.code ? (
              <details className="raw compact">
                <summary>Показать код</summary>
                <pre className="code-pre">{s.code}</pre>
              </details>
            ) : null}
            {s.stdout ? (
              <details className="raw compact">
                <summary>stdout</summary>
                <pre className="code-pre">{s.stdout}</pre>
              </details>
            ) : null}
            {s.stderr ? (
              <details className="raw compact">
                <summary>stderr</summary>
                <pre className="code-pre error">{s.stderr}</pre>
              </details>
            ) : null}
            {typeof s.elapsedSeconds === "number" ? <div className="muted">elapsed: {s.elapsedSeconds}s</div> : null}
            {Array.isArray(s.files) && s.files.length ? (
              <ul className="muted">
                {s.files.slice(0, 10).map((f, idx) => <li key={idx}>{String((f as any).name || (f as any).path || "file")}</li>)}
              </ul>
            ) : null}
          </details>
        );
      })}
    </section>
  );
}

