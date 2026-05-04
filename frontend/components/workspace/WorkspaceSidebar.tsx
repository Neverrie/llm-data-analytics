"use client";

import { Archive, Database, Search, Workflow } from "lucide-react";
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
  onSelectDataset: (id: string) => void;
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
    onSelectDataset,
    onUploadDataset,
    artifacts,
    onSelectArtifact
  } = props;

  const q = search.trim().toLowerCase();
  const filteredChats = chats.filter((c) => c.title.toLowerCase().includes(q) || (c.dataset_name || "").toLowerCase().includes(q));
  const filteredDatasets = datasets.filter((d) => d.name.toLowerCase().includes(q));
  const filteredArtifacts = artifacts.filter((a) => a.title.toLowerCase().includes(q) || a.filename.toLowerCase().includes(q));

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
        <input value={search} onChange={(e) => onSearch(e.target.value)} placeholder="Search chats, files, datasets" />
      </div>

      <section className="sidebar-group">
        <div className="group-head">
          <h4>Chats</h4>
          <button className="btn-ghost" onClick={onCreateChat}>Новый чат</button>
        </div>
        <div className="mini-list">
          {filteredChats.slice(0, 8).map((chat) => (
            <button key={chat.id} className={`mini-item ${selectedChatId === chat.id ? "active" : ""}`} onClick={() => onSelectChat(chat.id)}>
              <strong>{chat.title}</strong>
              <span>{chat.dataset_name || "no dataset"}</span>
            </button>
          ))}
          {!filteredChats.length ? <div className="empty-mini">Нет чатов</div> : null}
        </div>
      </section>

      <section className="sidebar-group">
        <div className="group-head">
          <h4>Pipeline</h4>
          <button className={`mode-chip ${section === "pipeline" ? "active" : ""}`} onClick={onOpenPipeline}><Workflow size={14} /> Lab 2</button>
        </div>
      </section>

      <section className="sidebar-group">
        <div className="group-head">
          <h4><Database size={14} /> Datasets</h4>
          <label className="btn-ghost upload-label">Upload
            <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => e.target.files?.[0] && onUploadDataset(e.target.files[0])} hidden />
          </label>
        </div>
        <div className="mini-list">
          {filteredDatasets.slice(0, 10).map((dataset) => (
            <button key={dataset.id} className={`mini-item ${selectedDatasetId === dataset.id ? "active" : ""}`} onClick={() => onSelectDataset(dataset.id)}>
              <strong>{dataset.name}</strong>
              <span>{dataset.source} · {dataset.rows_count ?? "?"} rows</span>
            </button>
          ))}
          {!filteredDatasets.length ? <div className="empty-mini">Нет датасетов</div> : null}
        </div>
      </section>

      <section className="sidebar-group sidebar-bottom">
        <div className="group-head">
          <h4><Archive size={14} /> Artifacts</h4>
        </div>
        <div className="mini-list">
          {filteredArtifacts.slice(0, 10).map((artifact) => (
            <button key={artifact.id} className="mini-item" onClick={() => onSelectArtifact(artifact.id)}>
              <strong>{artifact.title}</strong>
              <span>{artifact.kind} · {artifact.filename}</span>
            </button>
          ))}
          {!filteredArtifacts.length ? <div className="empty-mini">Нет артефактов</div> : null}
        </div>
      </section>
    </aside>
  );
}
