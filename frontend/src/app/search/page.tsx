"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useState, useEffect } from "react";
import SearchBar from "@/components/search/SearchBar";
import GraphSkeleton from "@/components/graph/GraphSkeleton";
import EmptyState from "@/components/ui/EmptyState";
import DisambiguationDialog, {
  DisambiguationItem,
} from "@/components/search/DisambiguationDialog";
import { searchNouns } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FuzzyResult {
  id: string;
  name: string;
  type: string;
  similarity: number;
  summary?: string;
}

function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const query = searchParams.get("q") || "";
  const name = searchParams.get("name") || "";

  const [showDisambiguation, setShowDisambiguation] = useState(false);
  const [disambigItems, setDisambigItems] = useState<DisambiguationItem[]>([]);
  const [disambigQuery, setDisambigQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [fuzzyResults, setFuzzyResults] = useState<FuzzyResult[]>([]);
  const [hasNoResults, setHasNoResults] = useState(false);
  const [isQidSearch, setIsQidSearch] = useState(false);

  // Check for disambiguation when query changes
  useEffect(() => {
    if (!query) return;

    const isQid = query.startsWith("Q") && query.length > 1;
    setIsQidSearch(isQid);

    // Skip disambiguation for QID searches or already-resolved entity names
    if (isQid || name) return;

    let cancelled = false;
    setIsLoading(true);
    setHasNoResults(false);
    setFuzzyResults([]);

    searchNouns(query)
      .then((data: any) => {
        if (cancelled) return;

        // Show disambiguation if needed
        if (data.needs_disambiguation && data.disambiguation_groups?.length > 0) {
          setDisambigQuery(query);
          setDisambigItems(data.disambiguation_groups);
          setShowDisambiguation(true);
        }

        // If no exact results, try fuzzy search
        if (data.total === 0) {
          return fetch(
            `${API_BASE}/api/nouns/fuzzy?q=${encodeURIComponent(query)}`
          ).then((r) => r.json());
        }
        return null;
      })
      .then((fuzzy: any) => {
        if (cancelled) return;
        if (fuzzy && fuzzy.results && fuzzy.results.length > 0) {
          setFuzzyResults(fuzzy.results);
          setHasNoResults(false);
        } else if (fuzzy) {
          setHasNoResults(true);
        }
      })
      .catch(() => {
        if (!cancelled) setHasNoResults(true);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [query, name]);

  const navigateToFuzzy = (result: FuzzyResult) => {
    // Navigate using QID
    router.push(`/search?q=${result.id}&name=${encodeURIComponent(result.name)}`);
  };

  const displayTitle = name || query;

  if (!query) {
    return (
      <EmptyState
        title="输入一个名词开始探索"
        description="在上方搜索框中输入名词，查看关系图谱与演化时间轴"
      />
    );
  }

  return (
    <div className="flex flex-col flex-1">
      {/* Disambiguation dialog */}
      {showDisambiguation && (
        <DisambiguationDialog
          query={disambigQuery}
          items={disambigItems}
          onClose={() => setShowDisambiguation(false)}
        />
      )}

      {/* Search bar section */}
      <div className="w-full max-w-2xl mx-auto px-4 py-6">
        <SearchBar initialQuery={displayTitle} />
      </div>

      {/* Results info */}
      <div className="w-full max-w-5xl mx-auto px-4 pb-4">
        {hasNoResults ? (
          <div>
            <h1 className="text-xl font-semibold text-surface-foreground font-heading">
              &ldquo;{query}&rdquo; 未找到匹配
            </h1>
            <p className="text-sm text-surface-muted-foreground mt-1">
              没有找到精确匹配的结果。请检查拼写或换一个词试试。
            </p>

            {/* Fuzzy suggestions */}
            {fuzzyResults.length > 0 && (
              <div className="mt-4">
                <p className="text-sm font-medium text-surface-foreground mb-2">
                  您是不是想找：
                </p>
                <div className="flex flex-wrap gap-2">
                  {fuzzyResults.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => navigateToFuzzy(r)}
                      className="px-3 py-1.5 text-sm rounded-full border border-border-default bg-surface-card text-surface-foreground hover:bg-brand-accent hover:text-white hover:border-brand-accent transition-colors cursor-pointer"
                    >
                      {r.name}
                      <span className="ml-1.5 text-xs opacity-60">
                        {Math.round(r.similarity * 100)}%
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : isQidSearch ? (
          <div>
            <h1 className="text-xl font-semibold text-surface-foreground font-heading">
              {name || `实体 ${query}`}
            </h1>
            {name && (
              <p className="text-sm text-surface-muted-foreground mt-1">
                正在加载图谱数据...
              </p>
            )}
          </div>
        ) : (
          <h1 className="text-xl font-semibold text-surface-foreground font-heading">
            {displayTitle}
          </h1>
        )}
      </div>

      {/* Main content area */}
      <div className="flex-1 flex flex-col gap-4 px-4 pb-4 max-w-7xl mx-auto w-full">
        <div className="flex-1 min-h-[500px] bg-surface-card rounded-xl border border-border-default overflow-hidden">
          <GraphSkeleton />
        </div>
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-surface-muted border-t-brand-accent" />
        </div>
      }
    >
      <SearchContent />
    </Suspense>
  );
}
