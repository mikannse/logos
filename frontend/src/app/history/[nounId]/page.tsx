"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { History, Clock, ArrowLeft, Trash2 } from "lucide-react";
import { fetchHistorySnapshot, deleteHistorySnapshot, HistorySnapshot } from "@/lib/api";
import { formatSavedAt } from "@/lib/format";
import EmptyState from "@/components/ui/EmptyState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import GraphSkeleton from "@/components/graph/GraphSkeleton";
import TimelineCompact from "@/components/timeline/TimelineCompact";

const GraphCanvas = dynamic(
  () => import("@/components/graph/GraphCanvas"),
  { loading: () => <GraphSkeleton />, ssr: false }
);

/**
 * 历史快照详情页：直接渲染已保存的图谱 + 时间轴，
 * 不经过搜索流程（不请求 /api/nouns，不触发建议 / 时间轴实时拉取）。
 */
export default function HistoryDetailPage() {
  const params = useParams();
  const nounId = typeof params?.nounId === "string" ? params.nounId : "";
  const [snapshot, setSnapshot] = useState<HistorySnapshot | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [deleted, setDeleted] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setNotFound(false);
    setDeleted(false);
    try {
      const snap = await fetchHistorySnapshot(nounId);
      if (!snap.exists) setNotFound(true);
      else setSnapshot(snap);
    } catch {
      setNotFound(true);
    } finally {
      setIsLoading(false);
    }
  }, [nounId]);

  useEffect(() => {
    if (!nounId) return;
    load();
  }, [nounId, load]);

  const handleDelete = useCallback(async () => {
    try {
      await deleteHistorySnapshot(nounId);
      setDeleted(true);
      setSnapshot(null);
    } catch {
      // 删除失败保持现状
    }
  }, [nounId]);

  if (!nounId || isLoading) {
    return (
      <div className="flex items-center justify-center py-16 flex-1">
        <LoadingSpinner />
      </div>
    );
  }

  if (notFound || !snapshot) {
    return (
      <EmptyState
        icon={<History className="w-12 h-12" />}
        title={deleted ? "快照已删除" : "该快照不存在或已删除"}
        description="返回历史列表，或重新搜索该名词。"
        action={
          <Link
            href="/history"
            className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border border-border-default bg-surface-card rounded-lg hover:bg-surface-muted transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> 返回历史列表
          </Link>
        }
      />
    );
  }

  const nodes = snapshot.graph?.nodes || [];
  const edges = snapshot.graph?.edges || [];
  const entityName = snapshot.entity?.name || snapshot.query || nounId;

  return (
    <div className="w-full max-w-7xl mx-auto px-4 py-5 flex flex-col flex-1">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <Link
          href="/history"
          aria-label="返回历史列表"
          className="p-1.5 rounded-lg text-surface-muted-foreground hover:bg-surface-muted hover:text-surface-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <History className="w-5 h-5 text-brand-accent shrink-0" />
        <h1 className="text-xl font-semibold text-surface-foreground font-heading">
          {entityName}
        </h1>
        <span className="text-xs font-mono text-surface-muted-foreground">{nounId}</span>
        <span className="flex items-center gap-1 text-xs text-surface-muted-foreground">
          <Clock className="w-3 h-3" /> {formatSavedAt(snapshot.saved_at)}
        </span>
        <button
          onClick={handleDelete}
          className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 text-xs border border-border-default bg-surface-card rounded-lg text-surface-muted-foreground hover:text-destructive hover:border-destructive/40 transition-colors cursor-pointer"
          aria-label="删除该快照"
        >
          <Trash2 className="w-3.5 h-3.5" /> 删除
        </button>
      </div>

      {/* Graph（复用 GraphCanvas，含内嵌图例） */}
      <div className="relative flex-1 min-h-[450px] bg-surface-card rounded-xl border border-border-default overflow-hidden">
        {nodes.length > 0 ? (
          <GraphCanvas centerId={nounId} nodes={nodes} edges={edges} />
        ) : (
          <div className="flex items-center justify-center h-full min-h-[450px]">
            <EmptyState title="暂无图谱数据" description="该快照未保存图谱数据" />
          </div>
        )}
      </div>

      {/* Timeline（milestones 由外部提供 → 不触发实时拉取） */}
      <div className="mt-3">
        <TimelineCompact nounId={nounId} milestones={snapshot.timeline || []} />
      </div>
    </div>
  );
}
