"use client";

import dynamic from "next/dynamic";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useState, useEffect, useCallback } from "react";
import SearchBar from "@/components/search/SearchBar";
import GraphSkeleton from "@/components/graph/GraphSkeleton";
import EmptyState from "@/components/ui/EmptyState";
import DisambiguationDialog, {
  DisambiguationItem,
} from "@/components/search/DisambiguationDialog";
import { searchNouns, fetchGraph, GraphNode } from "@/lib/api";

// Dynamic import: D3.js is heavy, only load when needed
const GraphCanvas = dynamic(
  () => import("@/components/graph/GraphCanvas"),
  {
    loading: () => <GraphSkeleton />,
    ssr: false,
  }
);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function SearchContent() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const name = searchParams.get("name") || "";

  const [showDisambiguation, setShowDisambiguation] = useState(false);
  const [disambigItems, setDisambigItems] = useState<DisambiguationItem[]>([]);
  const [disambigQuery, setDisambigQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isGraphLoading, setIsGraphLoading] = useState(false);
  const [fuzzyResults, setFuzzyResults] = useState<any[]>([]);
  const [hasNoResults, setHasNoResults] = useState(false);
  const [graphNodes, setGraphNodes] = useState<any[]>([]);
  const [graphEdges, setGraphEdges] = useState<any[]>([]);
  const [selectedEntityId, setSelectedEntityId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  // Determine the entity ID for graph fetching
  const entityId = (query?.startsWith("Q") && query) || selectedEntityId || "";

  // Fetch graph data when we have an entity ID
  useEffect(() => {
    if (!entityId) return;

    setIsGraphLoading(true);
    setError(null);

    fetchGraph(entityId, 1)
      .then((data) => {
        setGraphNodes(data.nodes || []);
        setGraphEdges(data.edges || []);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "加载图谱失败");
      })
      .finally(() => {
        setIsGraphLoading(false);
      });
  }, [entityId]);

  // Search + disambiguation check
  useEffect(() => {
    if (!query || query.startsWith("Q")) {
      if (query?.startsWith("Q")) {
        // Direct Wikidata ID search
        setSelectedEntityId(query);
      }
      return;
    }

    if (name) return; // Already resolved

    let cancelled = false;
    setIsLoading(true);
    setHasNoResults(false);
    setFuzzyResults([]);
    setGraphNodes([]);
    setGraphEdges([]);

    searchNouns(query)
      .then((data: any) => {
        if (cancelled) return;

        if (data.needs_disambiguation && data.disambiguation_groups?.length > 0) {
          setDisambigQuery(query);
          setDisambigItems(data.disambiguation_groups);
          setShowDisambiguation(true);
        }

        // If exact results exist, use the first one
        if (data.results?.length > 0) {
          const first = data.results[0];
          setSelectedEntityId(first.id);
          return null;
        }

        // No exact results, try fuzzy search
        return fetch(
          `${API_BASE}/api/nouns/fuzzy?q=${encodeURIComponent(query)}`
        ).then((r) => r.json());
      })
      .then((fuzzy: any) => {
        if (cancelled) return;
        if (fuzzy?.results?.length > 0) {
          setFuzzyResults(fuzzy.results);
        } else {
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

  const handleNodeClick = useCallback((node: GraphNode) => {
    console.log("Node clicked:", node);
  }, []);

  const handleNodeHover = useCallback((node: GraphNode | null) => {
    // Tooltip is handled by D3
  }, []);

  const navigateToEntity = (id: string, label: string) => {
    setSelectedEntityId(id);
    setHasNoResults(false);
    setFuzzyResults([]);
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
      <div className="w-full max-w-2xl mx-auto px-4 py-4">
        <SearchBar initialQuery={displayTitle} />
      </div>

      {/* Results info */}
      <div className="w-full max-w-7xl mx-auto px-4 pb-3">
        {hasNoResults ? (
          <div>
            <h1 className="text-lg font-semibold text-surface-foreground font-heading">
              &ldquo;{query}&rdquo; 未找到精确匹配
            </h1>
            {fuzzyResults.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="text-sm text-surface-muted-foreground">
                  您是不是想找：
                </span>
                {fuzzyResults.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => navigateToEntity(r.id, r.name)}
                    className="px-3 py-1 text-sm rounded-full border border-border-default bg-surface-card text-surface-foreground hover:bg-brand-accent hover:text-white transition-colors cursor-pointer"
                  >
                    {r.name}
                    <span className="ml-1.5 text-xs opacity-60">
                      {Math.round(r.similarity * 100)}%
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-baseline gap-3">
            <h1 className="text-lg font-semibold text-surface-foreground font-heading">
              {displayTitle}
            </h1>
            {selectedEntityId && (
              <span className="text-xs font-mono text-surface-muted-foreground">
                {selectedEntityId}
              </span>
            )}
          </div>
        )}

        {error && (
          <p className="mt-2 text-sm text-destructive">{error}</p>
        )}
      </div>

      {/* Main graph area */}
      <div className="flex-1 px-4 pb-4 max-w-7xl mx-auto w-full">
        <div className="relative min-h-[500px] bg-surface-card rounded-xl border border-border-default overflow-hidden">
          {(isGraphLoading || isLoading) ? (
            <GraphSkeleton />
          ) : graphNodes.length > 0 ? (
            <GraphCanvas
              centerId={entityId}
              nodes={graphNodes}
              edges={graphEdges}
              onNodeClick={handleNodeClick}
              onNodeHover={handleNodeHover}
            />
          ) : !hasNoResults && !entityId ? (
            <GraphSkeleton />
          ) : (
            <div className="flex items-center justify-center h-full min-h-[500px]">
              <EmptyState
                title="暂无图谱数据"
                description="搜索一个名词来查看它的关系图谱"
              />
            </div>
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
