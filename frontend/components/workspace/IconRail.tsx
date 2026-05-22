"use client";

import { Archive, Database, LogOut, MessageSquare } from "lucide-react";
import { ActiveSection } from "./types";

const items: Array<{ id: ActiveSection; icon: React.ReactNode; title: string }> = [
  { id: "chats", icon: <MessageSquare size={18} />, title: "Чаты" },
  { id: "datasets", icon: <Database size={18} />, title: "Датасеты" },
  { id: "artifacts", icon: <Archive size={18} />, title: "Артефакты" }
];

export function IconRail({ active, onChange, onLogout }: { active: ActiveSection; onChange: (s: ActiveSection) => void; onLogout: () => void }) {
  return (
    <aside className="rail">
      <div className="rail-items">
        {items.map((item) => (
          <button key={item.id} title={item.title} className={`rail-btn ${active === item.id ? "active" : ""}`} onClick={() => onChange(item.id)}>
            {item.icon}
          </button>
        ))}
      </div>
      <div className="rail-bottom">
        <button className="rail-btn" title="Выход" onClick={onLogout}><LogOut size={18} /></button>
      </div>
    </aside>
  );
}
