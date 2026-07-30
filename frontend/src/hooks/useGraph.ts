"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchGraph, GraphNode, GraphEdge } from "@/lib/api";

interface UseGraphResult {
  nodes: GraphNode[];
  edges: GraphEdge[];
  isLoading: boolean;
  error: string | null;
  depth: number;
  hasMore: boolean;
  loadMore: () => void;
  selectedNode: GraphNode | null;
  setSelectedNode: (node: GraphNode | null) => void;
}

export function useGraph(centerId: string, initialDepth = 1): UseGraphResult {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [depth, setDepth] = useState(initialDepth);
  const [hasMore, setHasMore] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const loadGraph = useCallback(
    async (d: number) => {
      if (!centerId) return;

      setIsLoading(true);
      setError(null);

      try {
        const data = await fetchGraph(centerId, d);
        setNodes(data.nodes || []);
        setEdges(data.edges || []);
        setHasMore(data.has_more);
        setDepth(data.depth);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载图谱失败");
        setNodes([]);
        setEdges([]);
      } finally {
        setIsLoading(false);
      }
    },
    [centerId]
  );

  useEffect(() => {
    loadGraph(depth);
  }, [centerId, loadGraph, depth]);

  const loadMore = useCallback(() => {
    if (hasMore && depth < 3) {
      setDepth((d) => d + 1);
    }
  }, [hasMore, depth]);

  return {
    nodes,
    edges,
    isLoading,
    error,
    depth,
    hasMore,
    loadMore,
    selectedNode,
    setSelectedNode,
  };
}
