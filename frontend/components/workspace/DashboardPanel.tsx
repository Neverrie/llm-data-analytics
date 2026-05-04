"use client";

import { ArtifactItem, Chat, DatasetItem } from "@/lib/api";

export function DashboardPanel({
  chats,
  datasets,
  artifacts,
  onOpenChat,
  onCreateChat,
  onOpenPipeline,
  onOpenDatasets,
  onOpenArtifacts
}: {
  chats: Chat[];
  datasets: DatasetItem[];
  artifacts: ArtifactItem[];
  onOpenChat: (id: string) => void;
  onCreateChat: () => void;
  onOpenPipeline: () => void;
  onOpenDatasets: () => void;
  onOpenArtifacts: () => void;
}) {
  return (
    <section className="main-panel workspace-screen">
      <div className="screen-body-scroll">
      <article className="dash-card hero-card">
        <h3>Dashboard</h3>
        <p className="muted">Последние анализы, датасеты и запуски pipeline</p>
        <div className="panel-row">
          <button className="btn-primary" onClick={onCreateChat}>Новый анализ</button>
          <button className="btn-secondary" onClick={onOpenPipeline}>Открыть Lab 2 Pipeline</button>
          <button className="btn-secondary" onClick={onOpenDatasets}>Загрузить датасет</button>
        </div>
      </article>

      <div className="dashboard-grid">
        <article className="dash-card">
          <div className="group-head"><h4>Недавние проекты</h4></div>
          <div className="mini-list">
            {chats.slice(0, 5).map((chat) => (
              <button key={chat.id} className="mini-item" onClick={() => onOpenChat(chat.id)}>
                <strong>{chat.title}</strong>
                <span>{chat.dataset_name || "без датасета"} · {new Date(chat.updated_at).toLocaleString()}</span>
              </button>
            ))}
          </div>
        </article>

        <article className="dash-card pipeline-hero">
          <h4>Lab 2 Pipeline</h4>
          <p className="muted">CSV → OpenRouter → JSON-классификация отзывов</p>
          <button className="btn-secondary" onClick={onOpenPipeline}>Открыть pipeline</button>
        </article>

        <article className="dash-card">
          <h4>Датасеты</h4>
          <div className="mini-list">{datasets.slice(0, 5).map((d) => <div key={d.id} className="mini-item"><strong>{d.name}</strong><span>{d.rows_count ?? "?"} rows</span></div>)}</div>
          <button className="btn-secondary" onClick={onOpenDatasets}>Открыть датасеты</button>
        </article>

        <article className="dash-card">
          <h4>Артефакты</h4>
          <div className="mini-list">{artifacts.slice(0, 5).map((a) => <div key={a.id} className="mini-item"><strong>{a.title}</strong><span>{a.kind}</span></div>)}</div>
          <button className="btn-secondary" onClick={onOpenArtifacts}>Открыть артефакты</button>
        </article>
      </div>
      </div>
    </section>
  );
}
