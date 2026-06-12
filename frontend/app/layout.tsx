import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LLM Data Analyst Workspace",
  description: "Анализ датасетов с LLM-агентом и изолированным Python sandbox"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}

