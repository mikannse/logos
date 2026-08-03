"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import * as d3 from "d3";
import type { GraphNode, GraphEdge } from "@/lib/api";
import { CONFIDENCE_LEVELS } from "@/lib/constants";

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
  category: "#94A3B8",
};

// P9 弱置信度边虚线阈值——与图例 LOW 档（<50%）一致
const WEAK_EDGE_THRESHOLD = CONFIDENCE_LEVELS.MEDIUM.min;

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: string;
  confidence: number;
  relevance?: number;
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
  // 存储 d3 zoom 实例与适配函数，供"重置视图"按钮复用（避免新建 zoom 实例导致 transform 失效）
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const fitToCenterRef = useRef<((force?: boolean) => void) | null>(null);
  const [hoveredNode, setHoveredNode] = useState<SimNode | null>(null);
  // P9 弱关联淡化开关（默认开）：弱边/低相关节点视觉退后但数据保留
  const [weakenEnabled, setWeakenEnabled] = useState(true);
  // 存 d3 selection，切换淡化开关时只更新属性、不重建整图（保留缩放/布局）
  // join 返回类型含 BaseType，故用宽松泛型
  const linksRef = useRef<d3.Selection<SVGLineElement | d3.BaseType, SimLink, SVGGElement, unknown> | null>(null);
  const shapesRef = useRef<d3.Selection<SVGGElement | d3.BaseType, SimNode, SVGGElement, unknown> | null>(null);
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

  // P9: 边淡化参数（透明度随 confidence、低置信度虚线）
  const edgeOpacity = useCallback(
    (confidence: number) => (weakenEnabled ? 0.2 + confidence * 0.5 : 1),
    [weakenEnabled]
  );
  const edgeDash = useCallback(
    (confidence: number) =>
      weakenEnabled && confidence < WEAK_EDGE_THRESHOLD ? "3,5" : "none",
    [weakenEnabled]
  );
  // P9: 节点淡化参数（中心 1.0，其他随 relevance 分级）
  const nodeOpacity = useCallback(
    (d: SimNode) => {
      if (!weakenEnabled) return 1;
      if (d.id === centerId) return 1;
      return 0.45 + (d.relevance ?? 0.5) * 0.55;
    },
    [weakenEnabled, centerId]
  );

  // 淡化开关切换：仅更新已有元素的 opacity/dash，不重建力导向布局
  useEffect(() => {
    if (!linksRef.current || !shapesRef.current) return;
    linksRef.current
      .attr("stroke-opacity", (d) => edgeOpacity(d.confidence))
      .attr("stroke-dasharray", (d) => edgeDash(d.confidence));
    shapesRef.current.attr("opacity", nodeOpacity);
  }, [weakenEnabled, edgeOpacity, edgeDash, nodeOpacity]);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;
    const container = containerRef.current;
    if (!container) return;

    const svg = d3.select(svgRef.current);
    // 尺寸存可变对象：fitToCenter / tooltip / resize 均读最新值，
    // 避免闭包捕获挂载时的旧尺寸（布局变化后图谱锚定到旧坐标系导致下方留白/被挡）。
    const size = { width: container.clientWidth || 800, height: container.clientHeight || 600 };

    // 显式设置 SVG width/height 属性，建立确定的 viewport。
    // WebKit/Safari 下纯 CSS 百分比尺寸（无 width/height 属性）的 <svg> 在调用
    // getBBox()（初次自动适配）/ getScreenCTM()（拖拽节点）解析相对长度时会抛：
    //   NotSupportedError: Failed to read the 'value' property from 'SVGLength':
    //   Could not resolve relative length.
    const applySize = () => {
      size.width = container.clientWidth || 800;
      size.height = container.clientHeight || 600;
      svg.attr("width", size.width).attr("height", size.height);
    };
    applySize();

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
    zoomRef.current = zoom;

    // 初始就给出宽松平移范围（而非等 fitToCenter 才设置）：
    // d3 zoom 默认 translateExtent 为 [[0,0],[svg宽,svg高]]，k=1 时视口正好填满该范围，
    // 布局未收敛/未 fit 前（仿真运行中用户就想拖动）任何方向平移都会被锁死，
    // 表现即"图谱一出来就拖不动 / 下方被挡"。初始放宽到 ±2 倍视口，
    // 保证任何时候（即使 fit 前）都能自由拖动，之后 fitToCenter 会按 bbox 收紧到合理范围。
    const viewportW = size.width;
    const viewportH = size.height;
    zoom.translateExtent([
      [-viewportW, -viewportH],
      [viewportW * 2, viewportH * 2],
    ]);

    // Center the graph
    const initialX = size.width / 2;
    const initialY = size.height / 2;

    // Convert to simulation data
    const simNodes: SimNode[] = nodes.map((n) => ({
      id: n.id,
      label: n.label || n.id,
      type: n.type,
      confidence: n.confidence,
      relevance: n.relevance ?? 0.5,
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
      .attr("stroke-width", (d) => Math.max(0.75, d.confidence * 3))
      .attr("stroke-opacity", (d) => (weakenEnabled ? 0.2 + d.confidence * 0.5 : 1))
      .attr("stroke-dasharray", (d) =>
        weakenEnabled && d.confidence < WEAK_EDGE_THRESHOLD ? "3,5" : "none");
    linksRef.current = link;

    // Draw nodes.
    // 拖动约定：普通拖拽 = 平移视图（在任何位置、包括节点上），
    // Shift+拖拽 = 拖动单个节点（重新布局）。
    // 否则放大后节点占满视口（无空白背景可抓），节点上的 d3.drag
    // 会 stopImmediatePropagation 吞掉 mousedown，视图无法平移，
    // 移出视口的下方节点就永远"被遮挡住"。
    // drag.filter(shiftKey) 在 noevent 之前求值：非 Shift 时不拦截
    // mousedown，事件冒泡到 svg 交给 zoom 平移。
    const node = g.append("g")
      .selectAll("g")
      .data(simNodes)
      .join("g")
      .attr("cursor", "grab")
      .call(
        d3.drag<SVGGElement, SimNode>()
          .filter((event) => event.shiftKey)
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
    shapesRef.current = node;

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

      // Node shape（实际淡化由 group opacity 控制，切换开关时仅更新 group）
      if (d.type === "person") {
        el.append("circle")
          .attr("r", r)
          .attr("fill", color)
          .attr("opacity", 1);
      } else if (d.type === "event") {
        el.append("polygon")
          .attr("points", `0,${-r * 1.3} ${r * 1.3},0 0,${r * 1.3} ${-r * 1.3},0`)
          .attr("fill", color)
          .attr("opacity", 1);
      } else {
        // entity / concept / technology
        el.append("rect")
          .attr("x", -r * 0.85)
          .attr("y", -r * 0.85)
          .attr("width", r * 1.7)
          .attr("height", r * 1.7)
          .attr("rx", r * 0.25)
          .attr("fill", color)
          .attr("opacity", 1);
      }

      // group opacity：中心 1.0，其他随 relevance 分级（由淡化开关 effect 统一更新）
      el.attr("opacity", nodeOpacity(d));

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
        const confClass = d.confidence >= CONFIDENCE_LEVELS.HIGH.min
          ? 'text-success'
          : d.confidence >= CONFIDENCE_LEVELS.MEDIUM.min
            ? 'text-warning'
            : 'text-destructive';

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
          .style("left", `${Math.min(mx + 15, size.width - 250)}px`)
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

    // 布局收敛后自动居中适配：
    // 1) 先让力导向布局运行，再基于真实布局的 bbox 计算，
    //    避免在布局开始前用随机初始位置的错误 bbox 做适配（导致图谱偏移）。
    // 2) 适配公式将 bbox 中心映射到视口中心（screen = user*k + x，需 cx*k + x = width/2）。
    let fitted = false;
    const fitToCenter = (force = false) => {
      if (fitted && !force) return;
      let bounds: SVGRect | null = null;
      try {
        bounds = g.node()?.getBBox() ?? null;
      } catch {
        bounds = null; // 测量失败（如 viewport 未就绪）时跳过，保证图谱仍能渲染
      }
      if (!bounds || bounds.width <= 0 || bounds.height <= 0) {
        // bbox 无效时【不】置位 fitted：布局可能尚未收敛，后续 tick/end 或延迟兜底会重试，
        // 否则一旦提前 return，fit 永久失效，translateExtent 停留在初始宽松范围。
        return;
      }
      fitted = true;
      const cx = bounds.x + bounds.width / 2;
      const cy = bounds.y + bounds.height / 2;
      const scale = Math.min(
        size.width / (bounds.width + 100),
        size.height / (bounds.height + 100),
        1.5
      );
      const transform = d3.zoomIdentity
        .scale(scale)
        .translate(size.width / scale / 2 - cx, size.height / scale / 2 - cy);
      // 平移边界（用户空间）：图谱 bbox 外扩一个视口。
      // 普通拖拽 = 平移视图后，若不加边界，用户可将图谱拖出视口完全"丢失"，
      // 只能靠重置按钮找回。加上边界后图谱始终可被拖回可见区域。
      zoom.translateExtent([
        [bounds.x - size.width, bounds.y - size.height],
        [bounds.x + bounds.width + size.width, bounds.y + bounds.height + size.height],
      ]);
      svg.transition().duration(500).call(zoom.transform, transform);
    };
    fitToCenterRef.current = fitToCenter;

    // Simulation tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as SimNode).x || 0)
        .attr("y1", (d) => (d.source as SimNode).y || 0)
        .attr("x2", (d) => (d.target as SimNode).x || 0)
        .attr("y2", (d) => (d.target as SimNode).y || 0);

      node.attr("transform", (d) => `translate(${d.x || 0},${d.y || 0})`);

      // 布局基本稳定（alpha < 0.1）后自动居中一次；拖拽重启动时不再反复适配
      if (!fitted && simulation.alpha() < 0.1) {
        fitToCenter();
      }
    });
    // 收敛兜底（alpha 到达 alphaMin 时）
    simulation.on("end", fitToCenter);

    // 延迟兜底居中：若布局稀疏/alpha 条件未触发（tick 的 alpha<0.1 与 end 都错过），
    // 1.2s 后强制适配一次；同时避免与用户的即时拖动冲突（fit 前已设置宽松 translateExtent）。
    let fitTimer: number | undefined;
    fitTimer = window.setTimeout(() => {
      if (!fitted) fitToCenter();
    }, 1200);

    // ---- 尺寸变化自适应 ----
    // 容器尺寸由 flex 布局决定，可能在挂载后变化（时间轴加载完成、视口调整等）。
    // 若 SVG 的 width/height 属性停留在旧值，图谱坐标系会锚定旧尺寸，
    // 新画布下方出现"死区/被挡"（旧尺寸之下没有可交互坐标）。
    // 此处监听变化并重测 + 强制重居中。
    const onResize = () => {
      if (
        Math.abs(container.clientWidth - size.width) > 1 ||
        Math.abs(container.clientHeight - size.height) > 1
      ) {
        applySize();
        fitToCenter(true); // force：忽略 fitted 守卫，按最新尺寸重算居中适配
      }
    };
    // 挂载后双帧重测：flex 容器高度在首次 effect 时可能尚未就绪（兄弟组件未渲染完）
    let rafId = 0;
    rafId = requestAnimationFrame(() => {
      rafId = requestAnimationFrame(onResize);
    });
    // ResizeObserver：容器尺寸真实变化（时间轴加载 / 视口调整）时重居中
    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(onResize);
      resizeObserver.observe(container);
    } else {
      // 兜底：无 ResizeObserver（旧浏览器）时退回 window.resize
      window.addEventListener("resize", onResize);
    }

    return () => {
      simulation.stop();
      cancelAnimationFrame(rafId);
      if (fitTimer) window.clearTimeout(fitTimer);
      linksRef.current = null;
      shapesRef.current = null;
      zoomRef.current = null;
      fitToCenterRef.current = null;
      resizeObserver?.disconnect();
      window.removeEventListener("resize", onResize);
    };
    // 淡化公式（edgeOpacity/edgeDash/nodeOpacity）仅经独立 effect 更新已有元素，
    // 若加入依赖会导致整图重建；此处有意省略
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, centerId, onNodeClick, onNodeHover, getEdgeColor]);

  return (
    // absolute inset-0：按偏移量填满 relative 父卡片，尺寸在任何浏览器中都确定。
    // 之前用 h-full（height:100%），其解析依赖 body min-h-full→main/page/卡片 flex-1
    // 整条链的高度"确定性"传递；该链在部分 Chromium 版本/时序下解析失败，
    // 容器塌缩到 min-h 兜底值，SVG 只剩顶部一截（图谱下方大片死区/节点被裁）。
    <div ref={containerRef} className="absolute inset-0 w-full h-full">
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

      {/* SVG canvas（尺寸由容器决定，不再设 min-height：
          卡片 min-h-[450px] 是唯一高度下限，避免 svg 比容器高被 overflow-hidden 裁掉一截） */}
      <svg
        ref={svgRef}
        className="w-full h-full"
      />

      {/* Tooltip */}
      <div
        ref={tooltipRef}
        className="fixed z-20 pointer-events-none bg-surface-card border border-border-default rounded-lg shadow-[var(--shadow-elevated)] opacity-0 transition-opacity duration-150"
        style={{ display: "none" }}
      />

      {/* Controls */}
      <div className="absolute bottom-3 right-3 z-10 flex items-center gap-2">
        <button
          onClick={() => setWeakenEnabled((v) => !v)}
          className={`p-2 rounded-lg border transition-colors cursor-pointer text-xs ${
            weakenEnabled
              ? "bg-brand-accent text-white border-brand-accent"
              : "bg-surface-card border-border-default text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted"
          }`}
          aria-pressed={weakenEnabled}
          aria-label="弱关联淡化开关"
          title={weakenEnabled ? "弱关联淡化：开（关闭可查看全部完整数据）" : "弱关联淡化：关"}
        >
          淡化
        </button>
        <button
          onClick={() => {
            // 修复：复用初始绑定的 zoom 实例（zoomRef）调用 fit 适配，
            // 恢复初始"居中适配"视图。旧实现新建 d3.zoom() 实例，事件命名空间
            // 不同，transform 不会触发已绑定监听器，点击后无任何反应。
            if (fitToCenterRef.current) {
              fitToCenterRef.current(true); // force：忽略 fitted 守卫，强制重算居中适配
            } else if (zoomRef.current && svgRef.current) {
              d3.select(svgRef.current)
                .transition()
                .duration(500)
                .call(zoomRef.current.transform, d3.zoomIdentity);
            }
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
