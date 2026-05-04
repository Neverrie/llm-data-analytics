"use client";

import ReactMarkdown from "react-markdown";

export function MarkdownBlock({ content }: { content: string }) {
  return <div className="markdown-block"><ReactMarkdown>{content}</ReactMarkdown></div>;
}

