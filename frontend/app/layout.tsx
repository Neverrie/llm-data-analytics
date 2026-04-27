import type { Metadata } from "next";
import "./globals.css";
import { Header } from "../components/Header";

export const metadata: Metadata = {
  title: "LLM Data Analyst Lab",
  description: "Учебный dashboard для лабораторных работ по LLM",
};

const themeInitScript = `
(() => {
  try {
    const key = "app_theme";
    const stored = window.localStorage.getItem(key);
    const theme = stored === "dark" || stored === "light"
      ? stored
      : (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
  } catch (_e) {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="page-bg">
        <main className="mx-auto min-h-screen max-w-6xl px-4 py-6 md:px-6">
          <Header />
          {children}
        </main>
      </body>
    </html>
  );
}
