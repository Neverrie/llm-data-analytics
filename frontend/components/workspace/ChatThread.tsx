"use client";

import { ChatMessage } from "@/lib/api";
import { MessageBubble } from "./MessageBubble";

export function ChatThread({ messages }: { messages: ChatMessage[] }) {
  return (
    <div className="chat-thread">
      {messages.map((message) => (
        <MessageBubble key={message.id} role={message.role} content={message.content} />
      ))}
    </div>
  );
}

