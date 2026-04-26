import type { Metadata } from "next";
import "./globals.css";
import { Header } from "../components/Header";

export const metadata: Metadata = {
  title: "LLM Data Analyst Lab",
  description: "Учебный dashboard для лабораторных работ по LLM"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <main className="mx-auto min-h-screen max-w-6xl px-4 py-6 md:px-6">
          <Header />
          {children}
        </main>
      </body>
    </html>
  );
}

