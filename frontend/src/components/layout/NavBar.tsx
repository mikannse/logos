"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search, Zap, History } from "lucide-react";
import ThemeToggle from "./ThemeToggle";

export default function NavBar() {
  const pathname = usePathname();
  const isCompact = pathname.startsWith("/search");

  return (
    <header
      className={`sticky top-0 z-50 w-full border-b border-border-default bg-surface/80 backdrop-blur-sm ${
        isCompact ? "h-14" : "h-16"
      }`}
    >
      <div className="mx-auto flex h-full items-center gap-4 px-4 max-w-7xl">
        {isCompact ? (
          <>
            <Link
              href="/"
              className="flex items-center gap-2 font-bold text-surface-foreground shrink-0"
            >
              <Zap className="w-5 h-5 text-brand-accent" />
              <span className="hidden sm:inline text-sm">Logos</span>
            </Link>
            <div className="flex-1 max-w-lg">
              {/* Compact search bar for search page - handled inline */}
            </div>
          </>
        ) : (
          <Link
            href="/"
            className="flex items-center gap-2 font-bold text-lg text-surface-foreground"
          >
            <Zap className="w-6 h-6 text-brand-accent" />
            Logos
          </Link>
        )}

        <div className="flex-1" />

        <nav className="flex items-center gap-2">
          <Link
            href="/search"
            className="flex items-center gap-2 px-3 py-2 text-sm text-surface-muted-foreground hover:text-surface-foreground transition-colors"
            aria-label="搜索名词"
          >
            <Search className="w-4 h-4" />
            <span className="hidden sm:inline">搜索</span>
          </Link>
          <Link
            href="/history"
            className="flex items-center gap-2 px-3 py-2 text-sm text-surface-muted-foreground hover:text-surface-foreground transition-colors"
            aria-label="搜索历史"
          >
            <History className="w-4 h-4" />
            <span className="hidden sm:inline">历史</span>
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
