"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState, useEffect } from "react";
import SearchBar from "@/components/search/SearchBar";
import GraphSkeleton from "@/components/graph/GraphSkeleton";
import EmptyState from "@/components/ui/EmptyState";
import DisambiguationDialog, {
  DisambiguationItem,
} from "@/components/search/DisambiguationDialog";
import { searchNouns } from "@/lib/api";

function SearchContent() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const name = searchParams.get("name") || "";

  const [showDisambiguation, setShowDisambiguation] = useState(false);
  const [disambigItems, setDisambigItems] = useState<DisambiguationItem[]>([]);
  const [disambigQuery, setDisambigQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Check for disambiguation when query changes
  useEffect(() => {
    if (!query || query.startsWith("Q")) {
      // If query is a Wikidata ID (Q123), no need to disambiguate
      return;
    }

    // Only run disambiguation check if no name param (meaning we just searched)
    if (name) return;

    let cancelled = false;
    setIsLoading(true);

    searchNouns(query)
      .then((data: any) => {
        if (cancelled) return;
        if (data.needs_disambiguation && data.disambiguation_groups?.length > 0) {
          setDisambigQuery(query);
          setDisambigItems(data.disambiguation_groups);
          setShowDisambiguation(true);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [query, name]);

  // Determine display title
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
        <h1 className="text-xl font-semibold text-surface-foreground font-heading">
          {displayTitle}
        </h1>
        {name && (
          <p className="text-sm text-surface-muted-foreground mt-1">
            已选择实体 · 正在加载图谱数据...
          </p>
        )}
      </div>

      {/* Main content area */}
      <div className="flex-1 flex flex-col lg:flex-row gap-4 px-4 pb-4 max-w-7xl mx-auto w-full">
        {/* Graph area */}
        <div className="flex-1 min-h-[500px] bg-surface-card rounded-xl border border-border-default overflow-hidden">
          {isLoading ? (
            <GraphSkeleton />
          ) : (
            <GraphSkeleton />
          )}
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
