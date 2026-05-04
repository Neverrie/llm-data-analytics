"use client";

import { memo } from "react";
import { ChatMessage } from "@/lib/api";
import { getMessageBlocks } from "@/lib/messageBlocks";
import { MessageBubble } from "./MessageBubble";

export const ChatThread = memo(function ChatThread({ messages }: { messages: ChatMessage[] }) {
  return (
    <div className="chat-thread">
      {messages.map((message) => (
        <MessageBubble key={message.id} role={message.role} content={message.content} blocks={getMessageBlocks(message)} />
      ))}
    </div>
  );
});
