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
  onOpenDashboard: () => void;
  onOpenAgent: () => void;
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
    onOpenDashboard,
    onOpenAgent,
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
        <input value={search} onChange={(e) => onSearch(e.target.value)} placeholder="Search" />
      </div>

      <section className="sidebar-group">
        <div className="group-head"><h4>Projects</h4></div>
        <div className="mini-list">
          <button className={`mini-item ${section === "dashboard" ? "active" : ""}`} onClick={onOpenDashboard}><strong>Dashboard</strong><span>Overview and history</span></button>
          <button className={`mini-item ${section === "agent" ? "active" : ""}`} onClick={onOpenAgent}><strong>Agent Chats</strong><span>Lab 3 workspace</span></button>
          <button className={`mini-item ${section === "pipeline" ? "active" : ""}`} onClick={onOpenPipeline}><strong><Workflow size={14} /> Lab 2 Pipeline</strong><span>API pipeline runs</span></button>
        </div>
      </section>

      <section className="sidebar-group">
        <div className="group-head">
          <h4>Chats</h4>
          <button className="btn-ghost" onClick={onCreateChat}>New chat</button>
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
          <h4><Database size={14} /> Datasets</h4>
          <label className="btn-ghost upload-label">Upload
            <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => e.target.files?.[0] && onUploadDataset(e.target.files[0])} hidden />
          </label>
        </div>
        <div className="mini-list">
          {filteredDatasets.slice(0, 10).map((dataset) => (
            <div key={dataset.id} className={`mini-item dataset-row ${selectedDatasetId === dataset.id ? "active" : ""}`}>
              <strong>{dataset.name}</strong>
              <span>{dataset.source} · {dataset.rows_count ?? "?"} rows</span>
              <div className="row-actions">
                <button className="link-btn" title="Use in chat" onClick={() => onUseDataset(dataset.id)}>Use</button>
                <button className="link-btn" title="Preview" onClick={() => onPreviewDataset(dataset.id)}>Preview</button>
              </div>
            </div>
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
