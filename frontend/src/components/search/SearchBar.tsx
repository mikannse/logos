"use client";

import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { useState, useCallback, FormEvent } from "react";

export default function SearchBar({ initialQuery = "" }: { initialQuery?: string }) {
  const [query, setQuery] = useState(initialQuery);
  const router = useRouter();

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (trimmed.length >= 2) {
        router.push(`/search?q=${encodeURIComponent(trimmed)}`);
      }
    },
    [query, router]
  );

  return (
    <form onSubmit={handleSubmit} className="relative w-full">
      <div className="relative flex items-center">
        <Search className="absolute left-4 w-5 h-5 text-surface-muted-foreground pointer-events-none" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="输入名词探索..."
          className="w-full h-12 pl-12 pr-4 bg-surface-card border border-border-default rounded-xl text-surface-foreground placeholder:text-surface-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-transparent transition-shadow duration-150"
          aria-label="搜索名词"
          minLength={2}
        />
        <button
          type="submit"
          disabled={query.trim().length < 2}
          className="absolute right-2 h-8 px-4 bg-brand-accent text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
          aria-label="搜索"
        >
          搜索
        </button>
      </div>
      {query.trim().length > 0 && query.trim().length < 2 && (
        <p className="mt-1 text-xs text-surface-muted-foreground pl-4">
          请输入至少 2 个字符
        </p>
      )}
    </form>
  );
}
