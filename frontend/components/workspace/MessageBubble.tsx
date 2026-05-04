"use client";

import { MarkdownBlock } from "./MarkdownBlock";

export function MessageBubble({ role, content }: { role: "user" | "assistant" | "system"; content: string }) {
  return (
    <div className={`message ${role}`}>
      {role === "assistant" ? <MarkdownBlock content={content} /> : <p>{content}</p>}
    </div>
  );
}

