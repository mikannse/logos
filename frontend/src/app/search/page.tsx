"use client";

import dynamic from "next/dynamic";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useState, useEffect, useCallback } from "react";
import SearchBar from "@/components/search/SearchBar";
import GraphSkeleton from "@/components/graph/GraphSkeleton";
import GraphNodePanel from "@/components/graph/GraphNodePanel";
import GraphLegend from "@/components/graph/GraphLegend";
import TimelineCompact from "@/components/timeline/TimelineCompact";
import EmptyState from "@/components/ui/EmptyState";
import DisambiguationDialog, {
  DisambiguationItem,
} from "@/components/search/DisambiguationDialog";
import { searchNouns, fetchGraph, GraphNode, GraphEdge } from "@/lib/api";

const GraphCanvas = dynamic(
  () => import("@/components/graph/GraphCanvas"),
  { loading: () => <GraphSkeleton />, ssr: false }
);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function SearchContent() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const name = searchParams.get("name") || "";

  // Disambiguation state
  const [showDisambiguation, setShowDisambiguation] = useState(false);
  const [disambigItems, setDisambigItems] = useState<DisambiguationItem[]>([]);
  const [disambigQuery, setDisambigQuery] = useState("");

  // Graph state
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [isGraphLoading, setIsGraphLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [entityId, setEntityId] = useState("");
  const [entityLabel, setEntityLabel] = useState("");

  // Search state
  const [fuzzyResults, setFuzzyResults] = useState<any[]>([]);
  const [hasNoResults, setHasNoResults] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  // Fetch graph data
  useEffect(() => {
    if (!entityId) {
      setGraphNodes([]);
      setGraphEdges([]);
      return;
    }

    setIsGraphLoading(true);
    setError(null);
    setSelectedNode(null);

    fetchGraph(entityId, 1)
      .then((data) => {
        setGraphNodes(data.nodes || []);
        setGraphEdges(data.edges || []);
      })
      .catch((err) => {
        setError("加载图谱失败: " + (err instanceof Error ? err.message : "未知错误"));
      })
      .finally(() => setIsGraphLoading(false));
  }, [entityId]);

  // Search + disambiguation
  useEffect(() => {
    if (!query) return;

    if (query.startsWith("Q")) {
      setEntityId(query);
      setEntityLabel(name || query);
      return;
    }
    if (name) return;

    let cancelled = false;
    setIsSearching(true);
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

        if (data.results?.length > 0) {
          const first = data.results[0];
          setEntityId(first.id);
          setEntityLabel(first.name);
          return null;
        }

        return fetch(
          `${API_BASE}/api/nouns/fuzzy?q=${encodeURIComponent(query)}`
        ).then((r) => r.json());
      })
      .then((fuzzy: any) => {
        if (cancelled) return;
        if (fuzzy?.results?.length > 0) setFuzzyResults(fuzzy.results);
        else setHasNoResults(true);
      })
      .catch(() => { if (!cancelled) setHasNoResults(true); })
      .finally(() => { if (!cancelled) setIsSearching(false); });

    return () => { cancelled = true; };
  }, [query, name]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, []);

  const handleNodeHover = useCallback((node: GraphNode | null) => {
    // handled by D3 tooltip
  }, []);

  const handleExploreGraph = useCallback((nodeId: string) => {
    setSelectedNode(null);
    setEntityId(nodeId);
    setEntityLabel(nodeId);
  }, []);

  const navigateToFuzzy = (id: string, label: string) => {
    setEntityId(id);
    setEntityLabel(label);
    setHasNoResults(false);
    setFuzzyResults([]);
  };

  const handleYearChange = useCallback((year: number | null) => {
    // Future: filter graph by year
  }, []);

  const displayTitle = name || entityLabel || query;

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

      {/* Search bar */}
      <div className="w-full max-w-2xl mx-auto px-4 py-3">
        <SearchBar initialQuery={displayTitle} />
      </div>

      {/* Results header + filters */}
      <div className="w-full max-w-7xl mx-auto px-4 pb-2">
        {hasNoResults ? (
          <div>
            <h1 className="text-lg font-semibold text-surface-foreground font-heading">
              &ldquo;{query}&rdquo; 未找到
            </h1>
            {fuzzyResults.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2 items-center">
                <span className="text-sm text-surface-muted-foreground">您是不是想找：</span>
                {fuzzyResults.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => navigateToFuzzy(r.id, r.name)}
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
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-surface-foreground font-heading">
              {displayTitle}
            </h1>
            {entityId && (
              <span className="text-xs font-mono text-surface-muted-foreground">
                {entityId}
              </span>
            )}
          </div>
        )}
        {error && <p className="text-sm text-destructive mt-1">{error}</p>}
      </div>

      {/* Main graph + detail panel layout */}
      <div className="flex-1 flex flex-col lg:flex-row gap-3 px-4 pb-3 max-w-7xl mx-auto w-full">
        {/* Graph area */}
        <div className="flex-1 flex flex-col gap-3 min-w-0">
          <div className="relative flex-1 min-h-[450px] bg-surface-card rounded-xl border border-border-default overflow-hidden">
            {/* Graph legend overlay */}
            <div className="absolute top-3 left-3 z-10">
              <GraphLegend />
            </div>

            {/* Graph canvas or loading/empty state */}
            {isGraphLoading || isSearching ? (
              <GraphSkeleton />
            ) : graphNodes.length > 0 ? (
              <GraphCanvas
                centerId={entityId}
                nodes={graphNodes}
                edges={graphEdges}
                onNodeClick={handleNodeClick}
                onNodeHover={handleNodeHover}
              />
            ) : (
              <div className="flex items-center justify-center h-full min-h-[450px]">
                <EmptyState
                  title="暂无图谱数据"
                  description={hasNoResults ? `未找到"${query}"的信息` : "搜索后图谱将在此展示"}
                />
              </div>
            )}
          </div>

          {/* Timeline */}
          {entityId && !hasNoResults && (
            <TimelineCompact nounId={entityId} onYearChange={handleYearChange} />
          )}
        </div>

        {/* Node detail panel */}
        {selectedNode && graphEdges.length > 0 && (
          <div className="hidden lg:block">
            <GraphNodePanel
              node={selectedNode}
              edges={graphEdges}
              onClose={() => setSelectedNode(null)}
              onExploreGraph={handleExploreGraph}
            />
          </div>
        )}
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
