type StatusBadgeProps = {
  status: "\u041a\u0430\u0440\u043a\u0430\u0441 \u0433\u043e\u0442\u043e\u0432" | "\u0412 \u0440\u0430\u0437\u0440\u0430\u0431\u043e\u0442\u043a\u0435";
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const isReady = status === "\u041a\u0430\u0440\u043a\u0430\u0441 \u0433\u043e\u0442\u043e\u0432";
  const style = isReady
    ? { backgroundColor: "rgba(52, 211, 153, 0.2)", color: "var(--success)" }
    : { backgroundColor: "rgba(96, 165, 250, 0.2)", color: "var(--accent)" };

  return (
    <span className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold" style={style}>
      {status}
    </span>
  );
}
