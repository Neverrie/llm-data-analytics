"use client";

import { Archive, ChevronDown, Database } from "lucide-react";
import { memo, useMemo, useState } from "react";
import { ArtifactItem, Chat, DatasetItem } from "@/lib/api";
import { ActiveSection } from "./types";

type SidebarProps = {
  user: { display_name: string; email: string; is_demo?: boolean };
  section: ActiveSection;
  chats: Chat[];
  selectedChatId?: string;
  onSelectChat: (id: string) => void;
  onCreateChat: () => void;
  onRenameChat: (id: string, title: string) => void;
  onDeleteChat: (id: string) => void;
  datasets: DatasetItem[];
  selectedDatasetId?: string;
  onUseDataset: (id: string) => void;
  onPreviewDataset: (id: string) => void;
  onDeleteDataset: (id: string) => void;
  onUploadDataset: (file: File) => void;
  artifacts: ArtifactItem[];
  onSelectArtifact: (id: string) => void;
  onDeleteArtifact: (id: string) => void;
  onLogout: () => void;
  theme: "dark" | "light";
  onToggleTheme: () => void;
};

function SectionCard({ title, collapsed, onToggle, children, actions, className = "" }: { title: string; collapsed: boolean; onToggle: () => void; children: React.ReactNode; actions?: React.ReactNode; className?: string }) {
  return (
    <section className={`sidebar-group resizable-pane ${className}`}>
      <div className="group-head">
        <button className="group-toggle" onClick={onToggle}>
          <ChevronDown size={14} className={collapsed ? "rotated" : ""} />
          <h4>{title}</h4>
        </button>
        <div className="group-controls">{actions}</div>
      </div>
      {!collapsed ? <div className="mini-list">{children}</div> : null}
    </section>
  );
}

export function WorkspaceSidebar(props: SidebarProps) {
  const {
    user,
    chats,
    selectedChatId,
    onSelectChat,
    onCreateChat,
    onRenameChat,
    onDeleteChat,
    datasets,
    selectedDatasetId,
    onUseDataset,
    onPreviewDataset,
    onDeleteDataset,
    onUploadDataset,
    artifacts,
    onSelectArtifact,
    onDeleteArtifact,
    onLogout,
    theme,
    onToggleTheme,
  } = props;

  const [collapsedChats, setCollapsedChats] = useState(false);
  const [collapsedDatasets, setCollapsedDatasets] = useState(false);
  const [collapsedArtifacts, setCollapsedArtifacts] = useState(false);

  const topArtifacts = useMemo(() => artifacts.slice(0, 30), [artifacts]);

  return (
    <aside className="sidebar-panel">
      <div className="profile-block">
        <div className="avatar">{user.display_name?.[0]?.toUpperCase() || "U"}</div>
        <div className="profile-main">
          <strong>{user.display_name}</strong>
          <p>{user.email}</p>
          {user.is_demo ? <span className="chip">demo</span> : null}
        </div>
      </div>

      <div className="profile-actions">
        <button className="btn-secondary" onClick={onToggleTheme}>{theme === "dark" ? "Светлая" : "Тёмная"} тема</button>
        <button className="btn-ghost" onClick={onLogout}>Выйти</button>
      </div>

      <SectionCard
        title="Чаты"
        collapsed={collapsedChats}
        onToggle={() => setCollapsedChats((v) => !v)}
        actions={<button className="btn-ghost" onClick={onCreateChat}>Новый</button>}
      >
        {chats.map((chat) => (
          <ChatListItem key={chat.id} chat={chat} active={selectedChatId === chat.id} onSelect={onSelectChat} onRename={onRenameChat} onDelete={onDeleteChat} />
        ))}
        {!chats.length ? <div className="empty-mini">Нет чатов</div> : null}
      </SectionCard>

      <SectionCard
        title="Датасеты"
        collapsed={collapsedDatasets}
        onToggle={() => setCollapsedDatasets((v) => !v)}
        actions={<label className="btn-ghost upload-label">Загрузить<input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => e.target.files?.[0] && onUploadDataset(e.target.files[0])} hidden /></label>}
      >
        {datasets.map((dataset) => (
          <DatasetListItem key={dataset.id} dataset={dataset} active={selectedDatasetId === dataset.id} onUseDataset={onUseDataset} onPreviewDataset={onPreviewDataset} onDeleteDataset={onDeleteDataset} />
        ))}
        {!datasets.length ? <div className="empty-mini">Нет датасетов</div> : null}
      </SectionCard>

      <SectionCard
        title="Артефакты"
        collapsed={collapsedArtifacts}
        onToggle={() => setCollapsedArtifacts((v) => !v)}
        className="sidebar-bottom"
      >
        {topArtifacts.map((artifact) => (
          <ArtifactListItem key={artifact.id} artifact={artifact} onSelectArtifact={onSelectArtifact} onDeleteArtifact={onDeleteArtifact} />
        ))}
        {!topArtifacts.length ? <div className="empty-mini">Нет артефактов</div> : null}
      </SectionCard>
    </aside>
  );
}

const ChatListItem = memo(function ChatListItem({ chat, active, onSelect, onRename, onDelete }: { chat: Chat; active: boolean; onSelect: (id: string) => void; onRename: (id: string, title: string) => void; onDelete: (id: string) => void; }) {
  return (
    <div className={`mini-item ${active ? "active" : ""}`} role="button" tabIndex={0} onClick={() => onSelect(chat.id)}>
      <strong>{chat.title}</strong>
      <span>{chat.dataset_name || "без датасета"}</span>
      <div className="row-actions">
        <button className="link-btn" onClick={() => onSelect(chat.id)}>Открыть</button>
        <button className="link-btn" onClick={(e) => { e.stopPropagation(); const next = window.prompt("Новое название чата", chat.title)?.trim(); if (next && next !== chat.title) onRename(chat.id, next); }}>Переименовать</button>
        <button className="link-btn danger" onClick={(e) => { e.stopPropagation(); if (window.confirm(`Удалить чат \"${chat.title}\"?`)) onDelete(chat.id); }}>Удалить</button>
      </div>
    </div>
  );
});

const DatasetListItem = memo(function DatasetListItem({ dataset, active, onUseDataset, onPreviewDataset, onDeleteDataset }: { dataset: DatasetItem; active: boolean; onUseDataset: (id: string) => void; onPreviewDataset: (id: string) => void; onDeleteDataset: (id: string) => void; }) {
  const canDelete = dataset.source === "uploaded" || dataset.source === "upload";
  return (
    <div
      className={`mini-item dataset-row ${active ? "active" : ""}`}
      role="button"
      tabIndex={0}
      onClick={() => onUseDataset(dataset.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onUseDataset(dataset.id);
        }
      }}
    >
      <strong>{dataset.name}</strong>
      <span>{dataset.source} · {dataset.rows_count ?? "?"} rows</span>
      <div className="row-actions">
        {active ? <span className="chip tiny">выбран</span> : null}
        <button className="link-btn" title="Превью" onClick={(e) => { e.stopPropagation(); onPreviewDataset(dataset.id); }}>Превью</button>
        {canDelete ? <button className="link-btn danger" title="Удалить" onClick={(e) => { e.stopPropagation(); if (window.confirm(`Удалить датасет \"${dataset.name}\"?`)) onDeleteDataset(dataset.id); }}>Удалить</button> : null}
      </div>
    </div>
  );
});

const ArtifactListItem = memo(function ArtifactListItem({ artifact, onSelectArtifact, onDeleteArtifact }: { artifact: ArtifactItem; onSelectArtifact: (id: string) => void; onDeleteArtifact: (id: string) => void; }) {
  return (
    <div
      className="mini-item"
      role="button"
      tabIndex={0}
      onClick={() => onSelectArtifact(artifact.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelectArtifact(artifact.id);
        }
      }}
    >
      <strong>{artifact.title}</strong>
      <span>{artifact.kind} · {artifact.filename}</span>
      <div className="row-actions">
        <button className="link-btn danger" title="Удалить" onClick={(e) => { e.stopPropagation(); if (window.confirm(`Удалить артефакт \"${artifact.title}\"?`)) onDeleteArtifact(artifact.id); }}>Удалить</button>
      </div>
    </div>
  );
});
