type StatusBadgeProps = {
  status: "Каркас готов" | "В разработке";
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const accent = status === "Каркас готов" ? "bg-mint/20 text-mint" : "bg-accent/20 text-accent";

  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${accent}`}>
      {status}
    </span>
  );
}

