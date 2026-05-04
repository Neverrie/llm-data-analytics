"use client";

import { ArtifactItem, Chat, DatasetItem } from "@/lib/api";

export function DashboardPanel({
  chats,
  datasets,
  artifacts,
  onOpenChat,
  onOpenPipeline,
  onOpenDatasets,
  onOpenArtifacts
}: {
  chats: Chat[];
  datasets: DatasetItem[];
  artifacts: ArtifactItem[];
  onOpenChat: (id: string) => void;
  onOpenPipeline: () => void;
  onOpenDatasets: () => void;
  onOpenArtifacts: () => void;
}) {
  return (
    <section className="main-panel">
      <div className="metric-grid">
        <article className="metric-card"><h4>Chats</h4><strong>{chats.length}</strong></article>
        <article className="metric-card"><h4>Datasets</h4><strong>{datasets.length}</strong></article>
        <article className="metric-card"><h4>Artifacts</h4><strong>{artifacts.length}</strong></article>
        <article className="metric-card"><h4>Last activity</h4><strong>{chats[0]?.updated_at ? new Date(chats[0].updated_at).toLocaleString() : "No activity"}</strong></article>
      </div>

      <div className="dashboard-grid">
        <article className="dash-card">
          <div className="group-head"><h4>Недавние чаты</h4></div>
          <div className="mini-list">
            {chats.slice(0, 5).map((chat) => (
              <button key={chat.id} className="mini-item" onClick={() => onOpenChat(chat.id)}>
                <strong>{chat.title}</strong>
                <span>{chat.dataset_name || "no dataset"}</span>
              </button>
            ))}
          </div>
        </article>

        <article className="dash-card">
          <h4>Lab 2 Pipeline</h4>
          <p className="muted">CSV → OpenRouter → JSON result</p>
          <button className="btn-secondary" onClick={onOpenPipeline}>Open</button>
        </article>

        <article className="dash-card">
          <h4>Datasets</h4>
          <div className="mini-list">{datasets.slice(0, 5).map((d) => <div key={d.id} className="mini-item"><strong>{d.name}</strong><span>{d.rows_count ?? "?"} rows</span></div>)}</div>
          <button className="btn-secondary" onClick={onOpenDatasets}>Открыть datasets</button>
        </article>

        <article className="dash-card">
          <h4>Artifacts</h4>
          <div className="mini-list">{artifacts.slice(0, 5).map((a) => <div key={a.id} className="mini-item"><strong>{a.title}</strong><span>{a.kind}</span></div>)}</div>
          <button className="btn-secondary" onClick={onOpenArtifacts}>Открыть artifacts</button>
        </article>
      </div>
    </section>
  );
}
