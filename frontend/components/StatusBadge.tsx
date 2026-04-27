type StatusBadgeProps = {
  status: "Каркас готов" | "В разработке";
};

export function StatusBadge({ status }: StatusBadgeProps) {
  if (status === "Каркас готов") {
    return (
      <span className="app-badge" style={{ background: "color-mix(in srgb, var(--success) 16%, transparent)", color: "var(--success)", border: "1px solid color-mix(in srgb, var(--success) 30%, var(--border))" }}>
        {status}
      </span>
    );
  }

  return <span className="app-badge app-badge-primary">{status}</span>;
}
