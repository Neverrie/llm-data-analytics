"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";

const links = [
  { href: "/", label: "Главная" },
  { href: "/lab1", label: "Лаба 1" },
  { href: "/lab2", label: "Лаба 2" },
  { href: "/lab3", label: "Лаба 3" },
];

export function Header() {
  const pathname = usePathname();

  return (
    <header className="app-header mb-6 px-4 py-3">
      <div className="mx-auto flex h-12 max-w-[1400px] items-center justify-between gap-4">
        <Link href="/" className="text-lg font-bold tracking-tight">
          LLM Data Analyst Lab
        </Link>

        <div className="flex items-center gap-2">
          <nav className="hidden flex-wrap items-center gap-2 md:flex">
            {links.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`app-button ${isActive ? "app-button-secondary" : "app-button-ghost"}`}
                  style={isActive ? { color: "var(--primary)", background: "var(--primary-soft)" } : undefined}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
