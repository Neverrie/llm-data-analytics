import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

const links = [
  { href: "/", label: "Главная" },
  { href: "/lab1", label: "Лаба 1" },
  { href: "/lab2", label: "Лаба 2" },
  { href: "/lab3", label: "Лаба 3" },
];

export function Header() {
  return (
    <header className="neu-panel mb-8 px-5 py-4">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
        <Link href="/" className="text-lg font-semibold tracking-tight app-text">
          LLM Data Analyst Lab
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <nav className="flex flex-wrap gap-3">
            {links.map((link) => (
              <Link key={link.href} href={link.href} className="neu-inset px-4 py-2 text-sm font-medium app-text transition hover:text-[var(--accent)]">
                {link.label}
              </Link>
            ))}
          </nav>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
