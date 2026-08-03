"use client";

import dynamic from "next/dynamic";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useState, useEffect, useCallback, useRef } from "react";
import SearchBar from "@/components/search/SearchBar";
import GraphSkeleton from "@/components/graph/GraphSkeleton";
import GraphNodePanel from "@/components/graph/GraphNodePanel";
import GraphLegend from "@/components/graph/GraphLegend";
import TimelineCompact from "@/components/timeline/TimelineCompact";
import BreadcrumbNav from "@/components/layout/BreadcrumbNav";
import EmptyState from "@/components/ui/EmptyState";
import DisambiguationDialog, {
  DisambiguationItem,
} from "@/components/search/DisambiguationDialog";
import DuplicateSearchDialog from "@/components/search/DuplicateSearchDialog";
import {
  searchNouns,
  fetchGraph,
  fetchHistorySnapshot,
  saveHistorySnapshot,
  GraphNode,
  GraphEdge,
  Milestone,
} from "@/lib/api";

const GraphCanvas = dynamic(
  () => import("@/components/graph/GraphCanvas"),
  { loading: () => <GraphSkeleton />, ssr: false }
);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const query = searchParams.get("q") || "";
  const name = searchParams.get("name") || "";
  // 由消歧弹窗选择/忽略后进入：不重复提示"已有历史结果"
  const fromDisambig = searchParams.get("from_disambig") === "1";

  // Disambiguation state
  const [showDisambiguation, setShowDisambiguation] = useState(false);
  const [disambigItems, setDisambigItems] = useState<DisambiguationItem[]>([]);
  const [disambigQuery, setDisambigQuery] = useState("");
  // 用户已忽略过消歧的查询（本会话内不再反复弹出）
  const dismissedDisambigRef = useRef<string | null>(null);

  // Graph state
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [isGraphLoading, setIsGraphLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [entityId, setEntityId] = useState("");
  const [entityLabel, setEntityLabel] = useState("");
  // 最新 entityId 的 ref：search effect 需对比当前实体，但不能依赖 entityId（避免 stale closure 与依赖循环）
  const entityIdRef = useRef("");
  useEffect(() => {
    entityIdRef.current = entityId;
  }, [entityId]);
  // 图谱强制刷新键：同实体"重新搜索"时也重新拉取（Story 4.2）
  const [graphRefreshKey, setGraphRefreshKey] = useState(0);

  // ---------- 搜索历史快照（Epic 4） ----------
  // 重复搜索提示：当前实体存在历史快照时记录其信息
  const [duplicateInfo, setDuplicateInfo] = useState<{ nounId: string; savedAt: string } | null>(null);
  // 最新一次拉取的时间轴（用于保存快照）
  const [timelineMilestones, setTimelineMilestones] = useState<Milestone[]>([]);
  // 时间轴是否已加载完成（区分"未加载"与"加载后为空"，保证空时间轴的实体也能保存快照）
  const [timelineLoaded, setTimelineLoaded] = useState(false);
  // 待保存快照：搜索解析出实体后置位，图谱 + 时间轴就绪后自动保存
  const pendingSnapshotRef = useRef<{ entityId: string; query: string } | null>(null);
  // 最近一次搜索目标（重复检查的过期保护，避免旧请求结果覆盖新搜索）
  const searchTargetRef = useRef("");

  // Search state
  const [fuzzyResults, setFuzzyResults] = useState<any[]>([]);
  const [hasNoResults, setHasNoResults] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  // Breadcrumb state (recursive exploration)
  const [breadcrumb, setBreadcrumb] = useState<Array<{ id: string; label: string; type?: string }>>([]);

  // Fetch graph data
  useEffect(() => {
    if (!entityId) {
      setGraphNodes([]);
      setGraphEdges([]);
      return;
    }

    let cancelled = false;
    setIsGraphLoading(true);
    setError(null);
    setSelectedNode(null);

    fetchGraph(entityId, 1)
      .then((data) => {
        if (cancelled) return;
        setGraphNodes(data.nodes || []);
        setGraphEdges(data.edges || []);
      })
      .catch((err) => {
        if (cancelled) return;
        setError("加载图谱失败: " + (err instanceof Error ? err.message : "未知错误"));
      })
      .finally(() => {
        if (!cancelled) setIsGraphLoading(false);
      });

    // 快速探索时取消过期请求，防止旧响应覆盖新实体图谱
    return () => { cancelled = true; };
  }, [entityId, graphRefreshKey]);

  // ---------- 搜索历史快照（Epic 4） ----------

  // 重复搜索检查：实体存在历史快照时弹出提示（FR-19）
  const checkDuplicate = useCallback((nounId: string, targetQuery: string) => {
    fetchHistorySnapshot(nounId)
      .then((snap) => {
        // 过期保护：已切到其他搜索 / 其他实体则忽略旧请求结果
        if (searchTargetRef.current !== targetQuery) return;
        if (entityIdRef.current !== nounId) return;
        if (snap.exists) setDuplicateInfo({ nounId, savedAt: snap.saved_at });
      })
      .catch(() => {});
  }, []);

  // TimelineCompact 内部拉取完成后上报（供快照保存）
  const handleTimelineLoaded = useCallback((ms: Milestone[]) => {
    setTimelineMilestones(ms);
    setTimelineLoaded(true);
  }, []);

  // 搜索解析出实体且图谱 + 时间轴都就绪后，自动保存快照（FR-17）
  useEffect(() => {
    const pending = pendingSnapshotRef.current;
    if (!pending) return;
    if (pending.entityId !== entityId) return;
    if (duplicateInfo?.nounId === entityId) return; // 用户在"查看/重搜"二选一中，暂不更新快照
    if (graphNodes.length === 0 || !timelineLoaded) return;

    saveHistorySnapshot({
      noun_id: entityId,
      query: pending.query,
      entity: { id: entityId, name: entityLabel },
      graph: { nodes: graphNodes, edges: graphEdges },
      timeline: timelineMilestones,
    }).catch(() => {});
    pendingSnapshotRef.current = null;
  }, [entityId, entityLabel, graphNodes, graphEdges, timelineMilestones, timelineLoaded, duplicateInfo]);

  // Search + disambiguation
  useEffect(() => {
    if (!query) return;

    searchTargetRef.current = query;

    // 仅当查询是真正的 Wikidata QID（Q + 数字）时才按实体 ID 处理，
    // 避免 "Quantum"、"Quran" 等普通英文词被误判跳过搜索
    if (/^Q[1-9]\d*$/.test(query)) {
      // 切换到新实体时同步清空旧图谱与时间轴（避免旧数据误入新实体快照）
      if (query !== entityIdRef.current) {
        setGraphNodes([]);
        setGraphEdges([]);
        setTimelineMilestones([]);
        setTimelineLoaded(false);
      }
      setEntityId(query);
      setEntityLabel(name || query);
      pendingSnapshotRef.current = { entityId: query, query: name || query };
      setGraphRefreshKey((k) => k + 1); // 同实体重搜也强制重新拉取
      // 由消歧弹窗选择/忽略后进入：不重复提示"已有历史结果"（用户刚主动选择了该实体）
      if (!fromDisambig) checkDuplicate(query, query);
      return;
    }
    if (name) return;

    let cancelled = false;
    setIsSearching(true);
    setHasNoResults(false);
    setFuzzyResults([]);
    // 注意：这里不清空 graphNodes/Edges。
    // 图谱由 graph effect 按 entityId 管理：切换到新实体时 graph effect 会重新拉取，
    // 同一实体重搜时保留现有图谱（否则会永久显示"暂无图谱数据"）。

    searchNouns(query)
      .then(async (data) => {
        if (cancelled) return;

        const disambigVisible =
          data.needs_disambiguation &&
          data.disambiguation_groups?.length > 0 &&
          query !== dismissedDisambigRef.current;
        if (disambigVisible) {
          setDisambigQuery(query);
          setDisambigItems(data.disambiguation_groups);
          setShowDisambiguation(true);
        }

        if (data.results?.length > 0) {
          const first = data.results[0];
          if (disambigVisible) {
            // 消歧弹窗存在：用户尚未选择实体，不自动解析、不生成图谱，
            // 等待用户在弹窗中选择（选择后经 QID 分支生成）
            return;
          }
          // 未触发消歧（或已忽略消歧）：自动解析为第一个结果
          if (first.id !== entityIdRef.current) {
            setGraphNodes([]);
            setGraphEdges([]);
            setTimelineMilestones([]);
            setTimelineLoaded(false);
          }
          setEntityId(first.id);
          setEntityLabel(first.name);
          setGraphRefreshKey((k) => k + 1); // 同实体重搜也强制重新拉取
          pendingSnapshotRef.current = { entityId: first.id, query };
          checkDuplicate(first.id, query);
          return; // 命中结果直接结束，避免误触发 hasNoResults
        }

        const res = await fetch(
          `${API_BASE}/api/nouns/fuzzy?q=${encodeURIComponent(query)}`
        );
        const fuzzy = await res.json();
        if (cancelled) return;
        if (fuzzy?.results?.length > 0) {
          setFuzzyResults(fuzzy.results);
          // 查询未命中具体实体：清除旧图谱，避免展示上一实体的图谱
          setGraphNodes([]);
          setGraphEdges([]);
        } else {
          setHasNoResults(true);
          setGraphNodes([]);
          setGraphEdges([]);
        }
      })
      .catch(() => { if (!cancelled) setHasNoResults(true); })
      .finally(() => { if (!cancelled) setIsSearching(false); });

    return () => { cancelled = true; };
  }, [query, name, fromDisambig, checkDuplicate]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, []);

  const handleNodeHover = useCallback((node: GraphNode | null) => {
    // handled by D3 tooltip
  }, []);

  const handleExploreGraph = useCallback((nodeId: string) => {
    // Add current entity to breadcrumb before switching
    setBreadcrumb((prev) => {
      const next = [...prev, { id: entityId, label: entityLabel || entityId }];
      // Max depth: 3 layers
      return next.length > 3 ? next.slice(-3) : next;
    });
    setSelectedNode(null);
    setEntityId(nodeId);
    setEntityLabel(nodeId);
  }, [entityId, entityLabel]);

  const navigateToFuzzy = (id: string, label: string) => {
    setEntityId(id);
    setEntityLabel(label);
    setHasNoResults(false);
    setFuzzyResults([]);
  };

  const handleYearChange = useCallback((year: number | null) => {
    // Future: filter graph by year
  }, []);

  const handleBreadcrumbNavigate = useCallback(
    (item: { id: string; label: string }, index: number) => {
      setBreadcrumb((prev) => prev.slice(0, index));
      setEntityId(item.id);
      setEntityLabel(item.label);
      setSelectedNode(null);
    },
    []
  );

  const displayTitle = name || entityLabel || query;

  if (!query) {
    return (
      <div className="flex flex-col items-center justify-center px-4 py-16 text-center">
        <div className="w-full max-w-lg">
          <SearchBar />
        </div>
        <p className="mt-4 text-sm text-surface-muted-foreground">
          输入名词，查看关系图谱与演化时间轴
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1">
      {/* Disambiguation dialog */}
      {showDisambiguation && (
        <DisambiguationDialog
          query={disambigQuery}
          items={disambigItems}
          onSelect={(item) => {
            // 用户选择：跳转到该实体（带 from_disambig 标记，避免重复提示"已有历史结果"）
            router.push(
              `/search?q=${encodeURIComponent(item.id)}&name=${encodeURIComponent(item.label)}&from_disambig=1`
            );
          }}
          onClose={() => setShowDisambiguation(false)}
          onDismiss={() => {
            // 用户忽略消歧：记住本次已忽略（同查询不再反复弹出），并默认选中第一个结果
            dismissedDisambigRef.current = disambigQuery;
            const first = disambigItems[0];
            if (first) {
              router.push(
                `/search?q=${encodeURIComponent(first.id)}&name=${encodeURIComponent(first.label)}&from_disambig=1`
              );
            }
          }}
        />
      )}

      {/* Duplicate search prompt (已有历史结果) */}
      {duplicateInfo && (
        <DuplicateSearchDialog
          query={query}
          entityName={displayTitle}
          savedAt={duplicateInfo.savedAt}
          onViewSnapshot={() => {
            // 跳转到专用历史详情页查看已保存快照（不经过搜索）
            const id = duplicateInfo.nounId;
            setDuplicateInfo(null);
            router.push(`/history/${encodeURIComponent(id)}`);
          }}
          onReSearch={() => {
            // 正常搜索已在进行：图谱已重新拉取，快照加载完成后自动更新
            setDuplicateInfo(null);
          }}
          onClose={() => setDuplicateInfo(null)}
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

      {/* Breadcrumb navigation */}
      {breadcrumb.length > 0 && (
        <div className="w-full max-w-7xl mx-auto px-4 pb-1">
          <BreadcrumbNav items={breadcrumb} onNavigate={handleBreadcrumbNavigate} />
        </div>
      )}

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
            <TimelineCompact
              nounId={entityId}
              onYearChange={handleYearChange}
              onLoaded={handleTimelineLoaded}
            />
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
