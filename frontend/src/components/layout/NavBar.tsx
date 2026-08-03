"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { Search, History } from "lucide-react";
import ThemeToggle from "./ThemeToggle";

export default function NavBar() {
  const pathname = usePathname();
  const isCompact = pathname.startsWith("/search");

  return (
    <header
      className={`sticky top-0 z-50 w-full border-b border-border-default bg-surface/70 backdrop-blur-md ${
        isCompact ? "h-14" : "h-16"
      }`}
    >
      <div className="mx-auto flex h-full items-center gap-4 px-4 max-w-7xl">
        <Link
          href="/"
          className="group flex items-center gap-2 font-bold text-surface-foreground shrink-0"
          aria-label="Logos 首页"
        >
          <Image
            src="/logo.png"
            alt="Logos"
            width={isCompact ? 28 : 34}
            height={isCompact ? 28 : 34}
            className="rounded-xl transition-all duration-300 group-hover:scale-105 group-hover:shadow-[0_0_16px_rgba(56,189,248,0.35)]"
          />
          <span className={`font-heading tracking-tight ${isCompact ? "hidden sm:inline text-sm" : "text-lg"}`}>
            Logos
          </span>
          <span className="hidden lg:inline-block mt-0.5 text-[10px] font-mono uppercase tracking-widest text-surface-muted-foreground/60">
            知识图谱
          </span>
        </Link>

        <div className="flex-1" />

        <nav className="flex items-center gap-1">
          <Link
            href="/search"
            className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted/70 transition-colors"
            aria-label="搜索名词"
          >
            <Search className="w-4 h-4" />
            <span className="hidden sm:inline">搜索</span>
          </Link>
          <Link
            href="/history"
            className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted/70 transition-colors"
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
