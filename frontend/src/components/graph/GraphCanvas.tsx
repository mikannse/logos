"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import * as d3 from "d3";
import type { GraphNode, GraphEdge } from "@/lib/api";

interface GraphCanvasProps {
  centerId: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
  onNodeHover?: (node: GraphNode | null) => void;
}

const NODE_COLORS: Record<string, string> = {
  person: "#2563EB",
  entity: "#16A34A",
  event: "#D97706",
  concept: "#8B5CF6",
  technology: "#0891B2",
  organization: "#DC2626",
};

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function createNodePath(type: string, cx: number, cy: number, r: number): string {
  switch (type) {
    case "person":
      return `<circle cx="${cx}" cy="${cy}" r="${r}" />`;
    case "event":
      return `<polygon points="${cx - r},${cy} ${cx},${cy - r * 1.5} ${cx + r},${cy} ${cx},${cy + r * 1.5}" />`;
    case "entity":
    case "concept":
    default:
      return `<rect x="${cx - r * 0.8}" y="${cy - r * 0.8}" width="${r * 1.6}" height="${r * 1.6}" rx="${r * 0.2}" />`;
  }
}

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: string;
  confidence: number;
  summary?: string;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  type: string;
  confidence: number;
  source_url: string;
}

export default function GraphCanvas({
  centerId,
  nodes,
  edges,
  onNodeClick,
  onNodeHover,
}: GraphCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [hoveredNode, setHoveredNode] = useState<SimNode | null>(null);

  const getEdgeColor = useCallback((type: string) => {
    const edgeColors: Record<string, string> = {
      influence: "#DC2626",
      affiliation: "#2563EB",
      creation: "#16A34A",
      competition: "#D97706",
      collaboration: "#8B5CF6",
    };
    return edgeColors[type] || "#64748B";
  }, []);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    const width = containerRef.current?.clientWidth || 800;
    const height = containerRef.current?.clientHeight || 600;

    // Clear previous
    svg.selectAll("*").remove();

    // Create tooltip div
    const tooltip = d3.select(tooltipRef.current);

    // Setup zoom
    const g = svg.append("g");

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Center the graph
    const centerNode = nodes.find((n) => n.id === centerId);
    const initialX = centerNode ? width / 2 : width / 2;
    const initialY = centerNode ? height / 2 : height / 2;

    // Convert to simulation data
    const simNodes: SimNode[] = nodes.map((n) => ({
      id: n.id,
      label: n.label || n.id,
      type: n.type,
      confidence: n.confidence,
      summary: n.summary,
    }));

    const simLinks: SimLink[] = edges.map((e) => ({
      source: e.source,
      target: e.target,
      type: e.type,
      confidence: e.confidence,
      source_url: e.source_url,
    }));

    // Force simulation
    const simulation = d3.forceSimulation<SimNode>(simNodes)
      .force("link", d3.forceLink<SimNode, SimLink>(simLinks)
        .id((d) => d.id)
        .distance((d) => 100 + (1 - d.confidence) * 50)
      )
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(initialX, initialY))
      .force("collision", d3.forceCollide().radius(30));

    // Draw edges
    const link = g.append("g")
      .selectAll("line")
      .data(simLinks)
      .join("line")
      .attr("stroke", (d) => getEdgeColor(d.type))
      .attr("stroke-width", (d) => Math.max(1, d.confidence * 3))
      .attr("stroke-opacity", 0.4)
      .attr("stroke-dasharray", (d) => d.confidence < 0.5 ? "4,4" : "none");

    // Draw nodes
    const node = g.append("g")
      .selectAll("g")
      .data(simNodes)
      .join("g")
      .attr("cursor", "pointer")
      .call(
        d3.drag<SVGGElement, SimNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }) as any
      );

    // Node circles with type-specific shapes
    node.each(function (d) {
      const el = d3.select(this);
      const r = d.id === centerId ? 22 : 16;
      const color = NODE_COLORS[d.type] || "#64748B";

      // Drop shadow for center node
      if (d.id === centerId) {
        el.append("circle")
          .attr("r", r + 4)
          .attr("fill", "none")
          .attr("stroke", color)
          .attr("stroke-width", 3)
          .attr("opacity", 0.3);
      }

      // Node shape
      if (d.type === "person") {
        el.append("circle")
          .attr("r", r)
          .attr("fill", color)
          .attr("opacity", 0.9);
      } else if (d.type === "event") {
        el.append("polygon")
          .attr("points", `0,${-r * 1.3} ${r * 1.3},0 0,${r * 1.3} ${-r * 1.3},0`)
          .attr("fill", color)
          .attr("opacity", 0.9);
      } else {
        // entity / concept / technology
        el.append("rect")
          .attr("x", -r * 0.85)
          .attr("y", -r * 0.85)
          .attr("width", r * 1.7)
          .attr("height", r * 1.7)
          .attr("rx", r * 0.25)
          .attr("fill", color)
          .attr("opacity", 0.9);
      }

      // Node label
      el.append("text")
        .text(d.label.length > 8 ? d.label.slice(0, 7) + "…" : d.label)
        .attr("text-anchor", "middle")
        .attr("dy", r + 16)
        .attr("fill", "var(--color-foreground)")
        .attr("font-size", "11px")
        .attr("font-family", "var(--font-work-sans)");

      // Hover events
      el.on("mouseenter", function (event) {
        const safeLabel = escapeHtml(d.label);
        const safeType = escapeHtml(d.type);
        const safeSummary = d.summary ? escapeHtml(d.summary) : "";
        const confClass = d.confidence >= 0.8 ? 'text-success' : d.confidence >= 0.5 ? 'text-warning' : 'text-destructive';

        tooltip.style("opacity", 1)
          .style("display", "block")
          .html(`
            <div class="p-3 text-sm">
              <div class="font-semibold text-surface-foreground font-heading">${safeLabel}</div>
              <div class="flex gap-1 mt-1">
                <span class="text-[10px] px-1 py-0.5 rounded bg-surface-muted text-surface-muted-foreground">${safeType}</span>
                <span class="text-[10px] px-1 py-0.5 rounded bg-surface-muted ${confClass}">
                  ${Math.round(d.confidence * 100)}%
                </span>
              </div>
              ${safeSummary ? `<p class="mt-1 text-xs text-surface-muted-foreground">${safeSummary}</p>` : ""}
            </div>
          `);
        setHoveredNode(d);
        onNodeHover?.(d as unknown as GraphNode);
      })
      .on("mousemove", function (event) {
        const [mx, my] = d3.pointer(event, svgRef.current?.parentElement);
        tooltip
          .style("left", `${Math.min(mx + 15, width - 250)}px`)
          .style("top", `${Math.max(my - 10, 10)}px`);
      })
      .on("mouseleave", function () {
        tooltip.style("opacity", 0).style("display", "none");
        setHoveredNode(null);
        onNodeHover?.(null);
      });

      // Click
      el.on("click", function () {
        onNodeClick?.(d as unknown as GraphNode);
      });
    });

    // Simulation tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as SimNode).x || 0)
        .attr("y1", (d) => (d.source as SimNode).y || 0)
        .attr("x2", (d) => (d.target as SimNode).x || 0)
        .attr("y2", (d) => (d.target as SimNode).y || 0);

      node.attr("transform", (d) => `translate(${d.x || 0},${d.y || 0})`);
    });

    // Initial zoom to fit
    const bounds = g.node()?.getBBox();
    if (bounds) {
      const scale = Math.min(
        width / (bounds.width + 100),
        height / (bounds.height + 100),
        1.5
      );
      const tx = width / 2 - (bounds.x + bounds.width / 2) * scale;
      const ty = height / 2 - (bounds.y + bounds.height / 2) * scale;
      svg.transition().duration(500).call(
        zoom.transform,
        d3.zoomIdentity.translate(tx, ty).scale(scale)
      );
    }

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, centerId, onNodeClick, onNodeHover, getEdgeColor]);

  return (
    <div ref={containerRef} className="relative w-full h-full min-h-[500px]">
      {/* Graph legend */}
      <div className="absolute top-3 left-3 z-10 flex flex-wrap gap-3 text-xs bg-surface-card/80 backdrop-blur-sm px-3 py-2 rounded-lg border border-border-default">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1">
            <span
              className="inline-block w-2.5 h-2.5 rounded-sm"
              style={{ backgroundColor: color }}
            />
            {type}
          </span>
        ))}
      </div>

      {/* SVG canvas */}
      <svg
        ref={svgRef}
        className="w-full h-full"
        style={{ minHeight: "500px" }}
      />

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        className="fixed z-20 pointer-events-none bg-surface-card border border-border-default rounded-lg shadow-[var(--shadow-elevated)] opacity-0 transition-opacity duration-150"
        style={{ display: "none" }}
      />

      {/* Controls */}
      <div className="absolute bottom-3 right-3 z-10 flex gap-2">
        <button
          onClick={() => {
            const svg = d3.select(svgRef.current);
            svg.transition().duration(500).call(
              d3.zoom<SVGSVGElement, unknown>().transform as any,
              d3.zoomIdentity
            );
          }}
          className="p-2 bg-surface-card border border-border-default rounded-lg text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted transition-colors cursor-pointer text-xs"
          aria-label="重置视图"
          title="重置视图"
        >
          ⊞
        </button>
      </div>

      {/* Empty state */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <p className="text-sm text-surface-muted-foreground">
            暂无图谱数据
          </p>
        </div>
      )}
    </div>
  );
}
