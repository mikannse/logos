"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { Search, Loader2, Settings, ArrowRight, CornerDownLeft } from "lucide-react";
import { useState, useCallback, useRef, useEffect, FormEvent } from "react";
import { useDebounce } from "@/hooks/useDebounce";

interface Suggestion {
  id: string;
  name: string;
  type: string;
  summary?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SearchBar({ initialQuery = "" }: { initialQuery?: string }) {
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(-1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const submitTimerRef = useRef<number | null>(null);
  const debouncedQuery = useDebounce(query, 200);

  // 卸载时清理提交态复位定时器
  useEffect(() => {
    return () => {
      if (submitTimerRef.current !== null) window.clearTimeout(submitTimerRef.current);
    };
  }, []);

  // Fetch suggestions when debounced query changes
  useEffect(() => {
    const trimmed = debouncedQuery.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    let cancelled = false;

    fetch(`${API_BASE}/api/nouns/suggest?q=${encodeURIComponent(trimmed)}`)
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        const items = data.suggestions || [];
        // Filter out exact match duplicates
        const seen = new Set<string>();
        const unique = items.filter((s: Suggestion) => {
          if (seen.has(s.name)) return false;
          seen.add(s.name);
          return true;
        });
        setSuggestions(unique.slice(0, 6));
        setShowSuggestions(unique.length > 0);
        setSelectedIdx(-1);
      })
      .catch(() => {
        if (!cancelled) setSuggestions([]);
      });

    return () => { cancelled = true; };
  }, [debouncedQuery]);

  const navigateToSearch = useCallback(
    (term: string) => {
      setShowSuggestions(false);
      setIsSubmitting(true);
      router.push(`/search?q=${encodeURIComponent(term)}`);
      // 客户端路由导航很快，短暂显示加载态后复位，避免按钮一直转圈
      submitTimerRef.current = window.setTimeout(() => setIsSubmitting(false), 800);
    },
    [router]
  );

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (trimmed.length >= 2) {
        // If a suggestion is selected, use its raw name
        if (selectedIdx >= 0 && suggestions[selectedIdx]) {
          navigateToSearch(suggestions[selectedIdx].name);
        } else {
          navigateToSearch(trimmed);
        }
      }
    },
    [query, selectedIdx, suggestions, navigateToSearch]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!showSuggestions) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIdx((prev) => Math.min(prev + 1, suggestions.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIdx((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Escape") {
        setShowSuggestions(false);
      }
    },
    [showSuggestions, suggestions.length]
  );

  const inputFocused = query.trim().length > 0;

  return (
    <form onSubmit={handleSubmit} className="relative w-full">
      <div
        className={`group relative flex items-center rounded-2xl border border-border-default bg-surface-card/80 shadow-[var(--shadow-elevated)] backdrop-blur-xl transition-all duration-300 focus-within:border-brand-accent/60 focus-within:bg-surface-card focus-within:ring-4 focus-within:ring-brand-accent/15 focus-within:shadow-[var(--shadow-glow)] ${
          inputFocused ? "ring-1 ring-brand-accent/10" : ""
        }`}
      >
        <Search className="absolute left-4 w-5 h-5 text-surface-muted-foreground pointer-events-none transition-colors group-focus-within:text-brand-accent" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => {
            if (suggestions.length > 0) setShowSuggestions(true);
          }}
          onBlur={() => {
            // Delay closing to allow click on suggestion
            setTimeout(() => setShowSuggestions(false), 200);
          }}
          onKeyDown={handleKeyDown}
          placeholder="输入任意名词，如「爱因斯坦」「区块链」「相对论」…"
          className="w-full h-13 pl-12 pr-36 py-3.5 bg-transparent text-surface-foreground placeholder:text-surface-muted-foreground/60 focus:outline-none rounded-2xl"
          aria-label="搜索名词"
          autoComplete="off"
          minLength={2}
        />
        {/* 按钮组绝对定位在输入框内部右侧，与左侧搜索图标对称 */}
        <div className="absolute right-2 flex items-center gap-1">
          <button
            type="submit"
            disabled={query.trim().length < 2}
            className="inline-flex items-center justify-center h-9 px-4 gap-1.5 bg-brand-accent text-surface-card rounded-xl text-sm font-medium hover:bg-brand-accent-strong hover:shadow-[var(--shadow-glow-sm)] active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-none transition-all duration-200 cursor-pointer"
            aria-label="搜索"
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <span className="hidden sm:inline">探索</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
          <Link
            href="/settings"
            className="h-9 w-9 flex items-center justify-center rounded-xl text-surface-muted-foreground hover:bg-surface-muted/80 hover:text-surface-foreground hover:rotate-90 transition-all duration-300"
            aria-label="设置"
          >
            <Settings className="w-4 h-4" />
          </Link>
        </div>
      </div>

      {/* Autocomplete suggestions dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-40 left-0 right-0 mt-2 bg-surface-card/95 backdrop-blur-xl border border-border-default rounded-2xl shadow-[var(--shadow-modal)] overflow-hidden animate-in fade-in zoom-in-95 origin-top">
          {suggestions.map((s, i) => (
            <button
              key={`${s.id}-${i}`}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                navigateToSearch(s.name);
              }}
              className={`w-full text-left px-4 py-3 flex items-center gap-3 transition-colors cursor-pointer ${
                i === selectedIdx
                  ? "bg-brand-accent/10 text-surface-foreground"
                  : "text-surface-foreground hover:bg-surface-muted/70"
              }`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors ${
                  i === selectedIdx
                    ? "bg-brand-accent/20 text-brand-accent"
                    : "bg-surface-muted/70 text-surface-muted-foreground"
                }`}
              >
                <Search className="w-3.5 h-3.5" />
              </span>
              <div className="min-w-0 flex-1">
                <span className="text-sm font-medium">{s.name}</span>
                {s.summary && (
                  <span className="ml-2 text-xs text-surface-muted-foreground truncate">
                    {s.summary}
                  </span>
                )}
              </div>
              {s.type && (
                <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-md bg-surface-muted text-surface-muted-foreground shrink-0 border border-border-default">
                  {s.type}
                </span>
              )}
              {i === selectedIdx && (
                <CornerDownLeft className="w-3 h-3 text-brand-accent shrink-0" />
              )}
            </button>
          ))}
          <div className="border-t border-border-default px-4 py-1.5 flex items-center justify-between text-[10px] text-surface-muted-foreground/70 bg-surface-muted/40">
            <span>↑↓ 选择</span>
            <span>Enter 搜索</span>
          </div>
        </div>
      )}

      {query.trim().length > 0 && query.trim().length < 2 && (
        <p className="mt-1 text-xs text-surface-muted-foreground pl-4">
          请输入至少 2 个字符
        </p>
      )}
    </form>
  );
}
