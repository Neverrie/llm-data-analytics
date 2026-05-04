"use client";

export function ErrorBanner({ message }: { message?: string }) {
  if (!message) return null;
  return <div className="error-banner">{message}</div>;
}

