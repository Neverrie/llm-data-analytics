import Link from "next/link";
import { StatusBadge } from "./StatusBadge";

type LabCardProps = {
  href: string;
  number: string;
  title: string;
  goal: string;
  maxScore: number;
  status: "Каркас готов" | "В разработке";
};

export function LabCard({ href, number, title, goal, maxScore, status }: LabCardProps) {
  return (
    <Link href={href} className="app-card block p-5 transition-shadow hover:shadow-[var(--shadow-md)]">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.15em] app-muted">{number}</p>
          <h3 className="text-lg font-semibold">{title}</h3>
        </div>
        <StatusBadge status={status} />
      </div>
      <p className="mb-4 text-sm app-muted">{goal}</p>
      <p className="text-sm font-medium app-muted">Макс. балл: {maxScore}</p>
    </Link>
  );
}
