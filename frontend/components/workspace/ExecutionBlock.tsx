"use client";

export function ExecutionBlock({ stdout, stderr, status }: { stdout?: string; stderr?: string; status?: string }) {
  return (
    <article className="block-card">
      <div className="block-head"><strong>Execution</strong><span>{status || ""}</span></div>
      {stdout ? <pre className="code-pre">{stdout}</pre> : null}
      {stderr ? <pre className="code-pre error">{stderr}</pre> : null}
      {!stdout && !stderr ? <p className="muted">No stdout/stderr</p> : null}
    </article>
  );
}
