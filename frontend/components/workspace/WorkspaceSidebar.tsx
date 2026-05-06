"use client";

import { Archive, Database, Search, Workflow } from "lucide-react";
import { memo, useMemo, useState } from "react";
import { ArtifactItem, Chat, DatasetItem } from "@/lib/api";
import { ActiveSection } from "./types";

type SidebarProps = {
  user: { display_name: string; email: string; is_demo?: boolean };
  section: ActiveSection;
  search: string;
  onSearch: (v: string) => void;
  chats: Chat[];
  selectedChatId?: string;
  onSelectChat: (id: string) => void;
  onCreateChat: () => void;
  onRenameChat: (id: string, title: string) => void;
  onDeleteChat: (id: string) => void;
  onOpenPipeline: () => void;
  datasets: DatasetItem[];
  selectedDatasetId?: string;
  onUseDataset: (id: string) => void;
  onPreviewDataset: (id: string) => void;
  onUploadDataset: (file: File) => void;
  artifacts: ArtifactItem[];
  onSelectArtifact: (id: string) => void;
};

export function WorkspaceSidebar(props: SidebarProps) {
  const {
    user,
    section,
    search,
    onSearch,
    chats,
    selectedChatId,
    onSelectChat,
    onCreateChat,
    onRenameChat,
    onDeleteChat,
    onOpenPipeline,
    datasets,
    selectedDatasetId,
    onUseDataset,
    onPreviewDataset,
    onUploadDataset,
    artifacts,
    onSelectArtifact
  } = props;

  const q = search.trim().toLowerCase();
  const [showProjects, setShowProjects] = useState(true);
  const [showDatasets, setShowDatasets] = useState(true);
  const [showArtifacts, setShowArtifacts] = useState(true);
  const [collapseProjects, setCollapseProjects] = useState(false);
  const [collapseDatasets, setCollapseDatasets] = useState(false);
  const [collapseArtifacts, setCollapseArtifacts] = useState(false);

  const filteredChats = useMemo(
    () => chats.filter((c) => c.title.toLowerCase().includes(q) || (c.dataset_name || "").toLowerCase().includes(q)),
    [chats, q]
  );
  const filteredDatasets = useMemo(() => datasets.filter((d) => d.name.toLowerCase().includes(q)), [datasets, q]);
  const filteredArtifacts = useMemo(() => artifacts.filter((a) => a.title.toLowerCase().includes(q) || a.filename.toLowerCase().includes(q)), [artifacts, q]);

  return (
    <aside className="sidebar-panel">
      <div className="profile-block">
        <div className="avatar">{user.display_name?.[0]?.toUpperCase() || "U"}</div>
        <div>
          <strong>{user.display_name}</strong>
          <p>{user.email}</p>
          {user.is_demo ? <span className="chip">demo</span> : null}
        </div>
      </div>

      <div className="search-box">
        <Search size={14} />
        <input value={search} onChange={(e) => onSearch(e.target.value)} placeholder="Поиск" />
      </div>

      {showProjects ? <section className="sidebar-group resizable-widget">
        <div className="group-head">
          <h4>Проекты</h4>
          <div className="group-controls">
            <button className="btn-ghost" onClick={() => setCollapseProjects((v) => !v)}>{collapseProjects ? "Развернуть" : "Свернуть"}</button>
            <button className="btn-ghost danger" onClick={() => setShowProjects(false)}>Убрать</button>
            <button className="btn-ghost" onClick={onCreateChat}>Новый</button>
          </div>
        </div>
        {!collapseProjects ? <div className="mini-list">
          {filteredChats.slice(0, 10).map((chat) => (
            <ChatListItem
              key={chat.id}
              chat={chat}
              active={selectedChatId === chat.id}
              onSelect={onSelectChat}
              onRename={onRenameChat}
              onDelete={onDeleteChat}
            />
          ))}
          {!filteredChats.length ? <div className="empty-mini">Нет проектов</div> : null}
        </div> : null}
      </section> : null}

      <section className="sidebar-group pipeline-card">
        <button className={`mini-item ${section === "pipeline" ? "active" : ""}`} onClick={onOpenPipeline}>
          <strong><Workflow size={14} /> Lab 2 Pipeline</strong>
          <span>Классификация отзывов через API</span>
        </button>
      </section>

      {showDatasets ? <section className="sidebar-group resizable-widget">
        <div className="group-head">
          <h4><Database size={14} /> Датасеты</h4>
          <div className="group-controls">
            <button className="btn-ghost" onClick={() => setCollapseDatasets((v) => !v)}>{collapseDatasets ? "Развернуть" : "Свернуть"}</button>
            <button className="btn-ghost danger" onClick={() => setShowDatasets(false)}>Убрать</button>
            <label className="btn-ghost upload-label">Загрузить
            <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => e.target.files?.[0] && onUploadDataset(e.target.files[0])} hidden />
            </label>
          </div>
        </div>
        {!collapseDatasets ? <div className="mini-list">
          {filteredDatasets.slice(0, 10).map((dataset) => (
            <DatasetListItem key={dataset.id} dataset={dataset} active={selectedDatasetId === dataset.id} onUseDataset={onUseDataset} onPreviewDataset={onPreviewDataset} />
          ))}
          {!filteredDatasets.length ? <div className="empty-mini">Нет датасетов</div> : null}
        </div> : null}
      </section> : null}

      {showArtifacts ? <section className="sidebar-group sidebar-bottom resizable-widget">
        <div className="group-head">
          <h4><Archive size={14} /> Артефакты</h4>
          <div className="group-controls">
            <button className="btn-ghost" onClick={() => setCollapseArtifacts((v) => !v)}>{collapseArtifacts ? "Развернуть" : "Свернуть"}</button>
            <button className="btn-ghost danger" onClick={() => setShowArtifacts(false)}>Убрать</button>
          </div>
        </div>
        {!collapseArtifacts ? <div className="mini-list">
          {filteredArtifacts.slice(0, 8).map((artifact) => (
            <ArtifactListItem key={artifact.id} artifact={artifact} onSelectArtifact={onSelectArtifact} />
          ))}
          {!filteredArtifacts.length ? <div className="empty-mini">Нет артефактов</div> : null}
        </div> : null}
      </section> : null}

      {(!showProjects || !showDatasets || !showArtifacts) ? (
        <button className="btn-secondary" onClick={() => { setShowProjects(true); setShowDatasets(true); setShowArtifacts(true); }}>
          Восстановить виджеты
        </button>
      ) : null}
    </aside>
  );
}

const ChatListItem = memo(function ChatListItem({
  chat,
  active,
  onSelect,
  onRename,
  onDelete
}: {
  chat: Chat;
  active: boolean;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className={`mini-item ${active ? "active" : ""}`} role="button" tabIndex={0} onClick={() => onSelect(chat.id)}>
      <strong>{chat.title}</strong>
      <span>{chat.dataset_name || "без датасета"} · {new Date(chat.updated_at).toLocaleDateString()}</span>
      <div className="row-actions">
        <button className="link-btn" onClick={() => onSelect(chat.id)}>
          Открыть
        </button>
        <button
          className="link-btn"
          onClick={(e) => {
            e.stopPropagation();
            const next = window.prompt("Новое название чата", chat.title)?.trim();
            if (next && next !== chat.title) onRename(chat.id, next);
          }}
        >
          Переименовать
        </button>
        <button
          className="link-btn danger"
          onClick={(e) => {
            e.stopPropagation();
            if (window.confirm(`Удалить чат "${chat.title}"?`)) onDelete(chat.id);
          }}
        >
          Удалить
        </button>
      </div>
    </div>
  );
});

const DatasetListItem = memo(function DatasetListItem({
  dataset,
  active,
  onUseDataset,
  onPreviewDataset
}: {
  dataset: DatasetItem;
  active: boolean;
  onUseDataset: (id: string) => void;
  onPreviewDataset: (id: string) => void;
}) {
  return (
    <button className={`mini-item dataset-row ${active ? "active" : ""}`} onClick={() => onUseDataset(dataset.id)}>
      <strong>{dataset.name}</strong>
      <span>{dataset.source} · {dataset.rows_count ?? "?"} rows</span>
      <div className="row-actions">
        {active ? <span className="chip tiny">выбран</span> : null}
        <button
          className="link-btn"
          title="Превью"
          onClick={(e) => {
            e.stopPropagation();
            onPreviewDataset(dataset.id);
          }}
        >
          Превью
        </button>
      </div>
    </button>
  );
});

const ArtifactListItem = memo(function ArtifactListItem({
  artifact,
  onSelectArtifact
}: {
  artifact: ArtifactItem;
  onSelectArtifact: (id: string) => void;
}) {
  return (
    <button className="mini-item" onClick={() => onSelectArtifact(artifact.id)}>
      <strong>{artifact.title}</strong>
      <span>{artifact.kind} · {artifact.filename}</span>
    </button>
  );
});
