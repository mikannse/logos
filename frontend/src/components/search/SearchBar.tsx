"use client";

import { useRouter } from "next/navigation";
import { Search, Loader2 } from "lucide-react";
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
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const debouncedQuery = useDebounce(query, 200);

  // Fetch suggestions when debounced query changes
  useEffect(() => {
    const trimmed = debouncedQuery.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);

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
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => { cancelled = true; };
  }, [debouncedQuery]);

  const navigateToSearch = useCallback(
    (term: string) => {
      setShowSuggestions(false);
      router.push(`/search?q=${encodeURIComponent(term)}`);
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

  return (
    <form onSubmit={handleSubmit} className="relative w-full">
      <div className="relative flex items-center">
        <Search className="absolute left-4 w-5 h-5 text-surface-muted-foreground pointer-events-none" />
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
          placeholder="输入名词探索..."
          className="w-full h-12 pl-12 pr-4 bg-surface-card border border-border-default rounded-xl text-surface-foreground placeholder:text-surface-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-transparent transition-shadow duration-150"
          aria-label="搜索名词"
          autoComplete="off"
          minLength={2}
        />
        <button
          type="submit"
          disabled={query.trim().length < 2}
          className="absolute right-2 h-8 px-4 bg-brand-accent text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
          aria-label="搜索"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            "搜索"
          )}
        </button>
      </div>

      {/* Autocomplete suggestions dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-40 left-0 right-0 mt-1 bg-surface-card border border-border-default rounded-xl shadow-[var(--shadow-elevated)] overflow-hidden">
          {suggestions.map((s, i) => (
            <button
              key={`${s.id}-${i}`}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                navigateToSearch(s.name);
              }}
              className={`w-full text-left px-4 py-2.5 flex items-center gap-3 transition-colors cursor-pointer ${
                i === selectedIdx
                  ? "bg-brand-accent/10 text-surface-foreground"
                  : "text-surface-foreground hover:bg-surface-muted"
              }`}
            >
              <Search className="w-3.5 h-3.5 text-surface-muted-foreground shrink-0" />
              <div className="min-w-0">
                <span className="text-sm font-medium">{s.name}</span>
                {s.summary && (
                  <span className="ml-2 text-xs text-surface-muted-foreground truncate">
                    {s.summary}
                  </span>
                )}
              </div>
              {s.type && (
                <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-surface-muted text-surface-muted-foreground shrink-0">
                  {s.type}
                </span>
              )}
            </button>
          ))}
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
