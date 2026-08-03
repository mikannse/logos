"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const preferred = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = stored === "dark" || (!stored && preferred);
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.classList.toggle("light", !isDark);
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    document.documentElement.classList.toggle("light", !next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  return (
    <button
      onClick={toggle}
      className="p-2 rounded-lg text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted/70 hover:shadow-[var(--shadow-glow-sm)] transition-all duration-300 cursor-pointer"
      aria-label={dark ? "切换到浅色模式" : "切换到深色模式"}
    >
      <span
        className={`block transition-transform duration-300 ${dark ? "" : "rotate-0"}`}
      >
        {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
      </span>
    </button>
  );
}
