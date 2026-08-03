"use client";

import { X, ExternalLink, ChevronRight } from "lucide-react";
import type { GraphNode, GraphEdge } from "@/lib/api";
import ConfidenceBadge from "@/components/ui/ConfidenceBadge";
import SourceLink from "@/components/ui/SourceLink";

interface GraphNodePanelProps {
  node: GraphNode;
  edges: GraphEdge[];
  onClose: () => void;
  onExploreGraph: (nodeId: string) => void;
}

const TYPE_LABELS: Record<string, string> = {
  person: "人物",
  entity: "实体",
  concept: "概念",
  technology: "技术",
  event: "事件",
  organization: "组织",
  category: "类别",
};

export default function GraphNodePanel({
  node,
  edges,
  onClose,
  onExploreGraph,
}: GraphNodePanelProps) {
  const nodeEdges = edges.filter(
    (e) => e.source === node.id || e.target === node.id
  );

  return (
    <div className="w-full lg:w-80 bg-surface-card border-l border-border-default overflow-y-auto">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-border-default">
        <div>
          <h2 className="text-lg font-semibold text-surface-foreground font-heading">
            {node.label || node.id}
          </h2>
          <span className="inline-block mt-1 text-xs px-1.5 py-0.5 rounded bg-surface-muted text-surface-muted-foreground">
            {TYPE_LABELS[node.type] || node.type}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-surface-muted-foreground hover:text-surface-foreground transition-colors cursor-pointer"
          aria-label="关闭"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Confidence + Source */}
      <div className="px-4 py-3 border-b border-border-default space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-muted-foreground">置信度:</span>
          <ConfidenceBadge confidence={node.confidence} />
        </div>
        {/* Source links from edges */}
        {nodeEdges.slice(0, 3).map((edge, i) =>
          edge.source_url ? (
            <SourceLink key={i} url={edge.source_url} name={edge.type} evidence={edge.evidence} />
          ) : null
        )}
      </div>

      {/* Summary */}
      {node.summary && (
        <div className="px-4 py-3 border-b border-border-default">
          <p className="text-sm text-surface-foreground leading-relaxed">{node.summary}</p>
        </div>
      )}

      {/* Relations */}
      <div className="px-4 py-3">
        <h3 className="text-sm font-semibold text-surface-foreground mb-2 font-heading">
          关联关系
        </h3>
        {nodeEdges.length === 0 ? (
          <p className="text-sm text-surface-muted-foreground">暂无关联关系</p>
        ) : (
          <div className="space-y-1.5">
            {nodeEdges.slice(0, 10).map((edge, i) => {
              const relatedId = edge.source === node.id ? edge.target : edge.source;
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 text-sm p-2 rounded-lg hover:bg-surface-muted transition-colors"
                >
                  <span className="text-surface-muted-foreground text-xs">{edge.type}</span>
                  <ChevronRight className="w-3 h-3 text-surface-muted-foreground shrink-0" />
                  <span className="font-medium text-surface-foreground truncate">{relatedId}</span>
                  <ConfidenceBadge confidence={edge.confidence} />
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Explore button */}
      <div className="px-4 pb-4">
        <button
          onClick={() => onExploreGraph(node.id)}
          className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand-accent text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors cursor-pointer"
        >
          展开该节点的图谱
          <ExternalLink className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
