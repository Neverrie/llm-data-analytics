"use client";

import { ActiveSection } from "./types";

export function AppShell({
  rail,
  sidebar,
  main,
  section
}: {
  rail: React.ReactNode;
  sidebar: React.ReactNode;
  main: React.ReactNode;
  section: ActiveSection;
}) {
  return (
    <div className="workspace-shell" data-section={section}>
      <div className="workspace-rail-slot">{rail}</div>
      <div className="workspace-sidebar-slot">{sidebar}</div>
      <main className="workspace-main">{main}</main>
    </div>
  );
}

