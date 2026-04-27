import { ReactNode } from "react";

type SectionCardProps = {
  title: string;
  children: ReactNode;
};

export function SectionCard({ title, children }: SectionCardProps) {
  return (
    <section className="app-card p-6">
      <h2 className="app-section-title mb-3">{title}</h2>
      <div className="space-y-3 text-sm app-muted">{children}</div>
    </section>
  );
}
