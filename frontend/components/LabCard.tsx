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
    <Link href={href} className="neu-card block p-6 transition-transform duration-200 hover:-translate-y-1">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{number}</p>
          <h3 className="text-lg font-semibold text-ink">{title}</h3>
        </div>
        <StatusBadge status={status} />
      </div>
      <p className="mb-4 text-sm text-slate-700">{goal}</p>
      <p className="text-sm font-medium text-slate-600">Макс. балл: {maxScore}</p>
    </Link>
  );
}

