"use client";

import { Chat } from "@/lib/api";

export function WorkspaceSidebar({
  user,
  chats,
  title,
  onCreate,
  onSelect,
  selectedId
}: {
  user: { display_name: string; email: string };
  chats: Chat[];
  title: string;
  onCreate: () => void;
  onSelect: (id: string) => void;
  selectedId?: string;
}) {
  return (
    <aside className="sidebar-panel">
      <div className="user-card">
        <div className="avatar">{user.display_name[0]?.toUpperCase() || "U"}</div>
        <div>
          <strong>{user.display_name}</strong>
          <p>{user.email}</p>
        </div>
      </div>
      <div className="sidebar-head">
        <h3>{title}</h3>
        <button className="btn-secondary" onClick={onCreate}>Новый</button>
      </div>
      <div className="chat-list">
        {chats.map((chat) => (
          <button key={chat.id} className={`chat-item ${selectedId === chat.id ? "active" : ""}`} onClick={() => onSelect(chat.id)}>
            <strong>{chat.title}</strong>
            <span>{chat.dataset_name || "No dataset"}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}

