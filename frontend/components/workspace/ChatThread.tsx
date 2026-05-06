"use client";

import { memo, useEffect, useRef } from "react";
import { ChatMessage } from "@/lib/api";
import { getMessageBlocks } from "@/lib/messageBlocks";
import { MessageBubble } from "./MessageBubble";

export const ChatThread = memo(function ChatThread({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <div className="chat-thread chat-thread-scroll">
      {messages.map((message) => (
        <MessageBubble key={message.id} role={message.role} content={message.content} blocks={getMessageBlocks(message)} />
      ))}
      <div ref={endRef} style={{ height: 1, scrollMarginBottom: 180 }} />
    </div>
  );
});
