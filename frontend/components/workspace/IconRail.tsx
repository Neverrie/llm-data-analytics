"use client";

import { Archive, Bot, Database, Home, LogOut, Settings2, Workflow } from "lucide-react";
import { ActiveSection } from "./types";

const items: Array<{ id: ActiveSection; icon: React.ReactNode; title: string }> = [
  { id: "dashboard", icon: <Home size={20} />, title: "Dashboard" },
  { id: "agent", icon: <Bot size={20} />, title: "Lab 3 Agent" },
  { id: "pipeline", icon: <Workflow size={20} />, title: "Lab 2 Pipeline" },
  { id: "datasets", icon: <Database size={20} />, title: "Datasets" },
  { id: "artifacts", icon: <Archive size={20} />, title: "Artifacts" }
];

export function IconRail({ active, onChange, onLogout }: { active: ActiveSection; onChange: (s: ActiveSection) => void; onLogout: () => void }) {
  return (
    <aside className="rail">
      <div className="rail-logo">LLM</div>
      <div className="rail-items">
        {items.map((item) => (
          <button key={item.id} title={item.title} className={`rail-btn ${active === item.id ? "active" : ""}`} onClick={() => onChange(item.id)}>
            {item.icon}
          </button>
        ))}
      </div>
      <div className="rail-bottom">
        <button className={`rail-btn ${active === "settings" ? "active" : ""}`} title="Settings" onClick={() => onChange("settings")}><Settings2 size={18} /></button>
        <button className="rail-btn" title="Logout" onClick={onLogout}><LogOut size={18} /></button>
      </div>
    </aside>
  );
}
