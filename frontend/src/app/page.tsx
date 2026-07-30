"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";
import SearchBar from "@/components/search/SearchBar";

const POPULAR_TERMS = ["爱因斯坦", "区块链", "CRISPR", "神经网络", "相对论"];

export default function Home() {
  return (
    <div className="flex flex-col flex-1">
      {/* Hero: Just search */}
      <section className="flex flex-col items-center justify-center px-4 flex-1 min-h-[60vh]">
        {/* Logo / Tagline */}
        <div className="flex items-center gap-2 mb-2">
          <Sparkles className="w-6 h-6 text-brand-accent" />
          <span className="text-xl font-bold text-surface-foreground font-heading tracking-tight">
            Logos
          </span>
        </div>
        <p className="text-sm text-surface-muted-foreground mb-8">
          搜一个名词，看它的关系网络和演化故事
        </p>

        {/* Search bar — the only real CTA */}
        <div className="w-full max-w-lg">
          <SearchBar />
        </div>

        {/* Quick links */}
        <div className="mt-6 flex flex-wrap gap-2 justify-center">
          <span className="text-xs text-surface-muted-foreground self-center">
            热门：
          </span>
          {POPULAR_TERMS.map((term) => (
            <Link
              key={term}
              href={`/search?q=${encodeURIComponent(term)}`}
              className="px-3 py-1 text-sm rounded-full border border-border-default text-surface-muted-foreground hover:border-brand-accent hover:text-brand-accent transition-colors duration-150"
            >
              {term}
            </Link>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="py-6 text-center text-xs text-surface-muted-foreground border-t border-border-default">
        Logos &copy; 2026
      </footer>
    </div>
  );
}
