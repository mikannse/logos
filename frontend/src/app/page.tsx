"use client";

import Link from "next/link";
import Image from "next/image";
import { Sparkles, Search } from "lucide-react";
import SearchBar from "@/components/search/SearchBar";

const POPULAR_TERMS = ["爱因斯坦", "区块链", "CRISPR", "神经网络", "相对论"];

export default function Home() {
  return (
    <div className="flex flex-col flex-1">
      {/* Hero: Just search */}
      <section className="flex flex-col items-center justify-center px-4 flex-1 min-h-[60vh]">
        {/* Logo / Tagline */}
        <div className="flex flex-col items-center mb-7">
          <Image
            src="/logo.png"
            alt="Logos"
            width={80}
            height={80}
            priority
            className="animate-float mb-5 rounded-2xl shadow-[0_0_32px_rgba(56,189,248,0.25)]"
          />
          <h1 className="text-4xl sm:text-5xl font-heading font-bold tracking-tight text-center">
            <span className="text-surface-foreground">探索任何名词的</span>
            <br className="sm:hidden" />
            <span className="text-gradient">知识图谱</span>
          </h1>
          <p className="mt-4 max-w-lg text-center text-base leading-relaxed text-surface-muted-foreground">
            输入一个名词，自动构建它周围复杂的关系网络与演化时间轴，
            <span className="hidden sm:inline">让好奇心有迹可循。</span>
          </p>
        </div>

        {/* Search bar — the only real CTA */}
        <div className="w-full max-w-xl">
          <SearchBar />
        </div>

        {/* Quick links */}
        <div className="mt-6 flex flex-wrap gap-2 justify-center items-center">
          <span className="flex items-center gap-1 text-xs text-surface-muted-foreground">
            <Sparkles className="w-3.5 h-3.5" /> 试试
          </span>
          {POPULAR_TERMS.map((term) => (
            <Link
              key={term}
              href={`/search?q=${encodeURIComponent(term)}`}
              className="group inline-flex items-center gap-1 px-3 py-1 text-sm rounded-full border border-border-default bg-surface-card/50 text-surface-muted-foreground backdrop-blur-md transition-colors duration-200 hover:border-brand-accent/60 hover:text-surface-foreground hover:bg-brand-accent/5"
            >
              <Search className="w-3 h-3 text-surface-muted-foreground/60 group-hover:text-brand-accent" />
              {term}
            </Link>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="py-6 text-center text-xs text-surface-muted-foreground border-t border-border-default">
        Logos &copy; 2026 · 让知识的关系可见
      </footer>
    </div>
  );
}
