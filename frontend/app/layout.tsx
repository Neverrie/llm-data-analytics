import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LLM Data Analyst Workspace",
  description: "AI-аналитика датасетов с Code Interpreter и API Pipeline"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}

