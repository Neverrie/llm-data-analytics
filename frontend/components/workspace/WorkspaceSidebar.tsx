"use client";

import { Archive, Database, Search, Workflow } from "lucide-react";
import { memo, useMemo } from "react";
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

      <section className="sidebar-group">
        <div className="group-head">
          <h4>Проекты</h4>
          <button className="btn-ghost" onClick={onCreateChat}>Новый</button>
        </div>
        <div className="mini-list">
          {filteredChats.slice(0, 10).map((chat) => (
            <ChatListItem key={chat.id} chat={chat} active={selectedChatId === chat.id} onSelect={onSelectChat} />
          ))}
          {!filteredChats.length ? <div className="empty-mini">Нет проектов</div> : null}
        </div>
      </section>

      <section className="sidebar-group pipeline-card">
        <button className={`mini-item ${section === "pipeline" ? "active" : ""}`} onClick={onOpenPipeline}>
          <strong><Workflow size={14} /> Lab 2 Pipeline</strong>
          <span>Классификация отзывов через API</span>
        </button>
      </section>

      <section className="sidebar-group">
        <div className="group-head">
          <h4><Database size={14} /> Датасеты</h4>
          <label className="btn-ghost upload-label">Загрузить
            <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => e.target.files?.[0] && onUploadDataset(e.target.files[0])} hidden />
          </label>
        </div>
        <div className="mini-list">
          {filteredDatasets.slice(0, 10).map((dataset) => (
            <DatasetListItem key={dataset.id} dataset={dataset} active={selectedDatasetId === dataset.id} onUseDataset={onUseDataset} onPreviewDataset={onPreviewDataset} />
          ))}
          {!filteredDatasets.length ? <div className="empty-mini">Нет датасетов</div> : null}
        </div>
      </section>

      <section className="sidebar-group sidebar-bottom">
        <div className="group-head">
          <h4><Archive size={14} /> Артефакты</h4>
        </div>
        <div className="mini-list">
          {filteredArtifacts.slice(0, 8).map((artifact) => (
            <ArtifactListItem key={artifact.id} artifact={artifact} onSelectArtifact={onSelectArtifact} />
          ))}
          {!filteredArtifacts.length ? <div className="empty-mini">Нет артефактов</div> : null}
        </div>
      </section>
    </aside>
  );
}

const ChatListItem = memo(function ChatListItem({ chat, active, onSelect }: { chat: Chat; active: boolean; onSelect: (id: string) => void }) {
  return (
    <button className={`mini-item ${active ? "active" : ""}`} onClick={() => onSelect(chat.id)}>
      <strong>{chat.title}</strong>
      <span>{chat.dataset_name || "без датасета"} · {new Date(chat.updated_at).toLocaleDateString()}</span>
    </button>
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
          title="Preview"
          onClick={(e) => {
            e.stopPropagation();
            onPreviewDataset(dataset.id);
          }}
        >
          Preview
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
