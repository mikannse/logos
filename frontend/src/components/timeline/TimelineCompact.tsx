"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Clock } from "lucide-react";
import { fetchTimeline, Milestone } from "@/lib/api";
import Skeleton from "@/components/ui/Skeleton";
import SourceLink from "@/components/ui/SourceLink";

interface TimelineCompactProps {
  nounId: string;
  onYearChange?: (year: number | null) => void;
  /** 外部提供的里程碑（历史快照视图）；非空时直接渲染，不再拉取实时数据 */
  milestones?: Milestone[] | null;
  /** 内部拉取完成后的回调（用于搜索快照保存） */
  onLoaded?: (milestones: Milestone[]) => void;
}

type Granularity = "year" | "decade" | "century";

// V2b: 粒度格式化纯函数（集中定义，避免各处手写世纪边界出错）
// 世纪边界：2000 属于 20 世纪（Math.floor(2000/100)=20）而非 21 世纪
export function formatGranule(year: number, granularity: Granularity): {
  label: string;
  representativeYear: number;
} {
  if (granularity === "decade") {
    return { label: `${Math.floor(year / 10) * 10}年代`, representativeYear: Math.floor(year / 10) * 10 };
  }
  if (granularity === "century") {
    const c = Math.floor(year / 100) + 1;
    return { label: `${c}世纪`, representativeYear: Math.floor(year / 100) * 100 };
  }
  return { label: String(year), representativeYear: year };
}

export default function TimelineCompact({
  nounId,
  onYearChange,
  milestones: externalMilestones = null,
  onLoaded,
}: TimelineCompactProps) {
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  // V2b: 粒度状态放组件内部——search 页与历史快照页自动同获，行为一致
  const [granularity, setGranularity] = useState<Granularity>("year");
  // V2d: 展开的里程碑索引（单一 state）
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const onLoadedRef = useRef(onLoaded);
  onLoadedRef.current = onLoaded;

  useEffect(() => {
    // 外部快照模式：直接渲染，不拉取
    if (externalMilestones) {
      setMilestones(externalMilestones);
      setIsLoading(false);
      return;
    }

    if (!nounId) return;
    setIsLoading(true);

    // 修复 6：StrictMode 双挂载时首个 effect 的请求被 abort，避免重复调用
    const controller = new AbortController();

    fetchTimeline(nounId, controller.signal)
      .then((data) => {
        const ms = data.milestones || [];
        setMilestones(ms);
        setExpandedIndex(null); // V2d: 数据切换不残留展开状态
        onLoadedRef.current?.(ms);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setMilestones([]);
      })
      .finally(() => setIsLoading(false));

    return () => controller.abort();
  }, [nounId, externalMilestones]);

  // V2b: 聚合派生（useMemo 缓存）——granule → 组（代表里程碑 + 组内数量）
  const groups = useMemo(() => {
    if (granularity === "year") {
      return milestones.map((m, i) => ({
        label: String(m.year),
        representative: m,
        representativeIndex: i,
        memberCount: 1,
      }));
    }
    const map = new Map<string, { label: string; representative: Milestone; representativeIndex: number; memberCount: number }>();
    milestones.forEach((m, i) => {
      const { label } = formatGranule(m.year, granularity);
      if (!map.has(label)) {
        map.set(label, { label, representative: m, representativeIndex: i, memberCount: 0 });
      }
      const group = map.get(label)!;
      group.memberCount += 1;
      // 代表取组内最早年份的成员（milestones 已按年升序，首个即最早）
    });
    return Array.from(map.values());
  }, [milestones, granularity]);

  // V2b: 少数据降级——跨度不足 / 组数过少时禁用粗粒度档。
  // 判定基于原始数据而非当前 groups（避免选中 decade 后因 groups.length 变小误禁自身）。
  const minYear = milestones.length ? Math.min(...milestones.map((m) => m.year)) : 0;
  const maxYear = milestones.length ? Math.max(...milestones.map((m) => m.year)) : 0;
  const spanYears = maxYear - minYear;
  const decadeGroupCount = new Set(milestones.map((m) => Math.floor(m.year / 10))).size;
  const centuryGroupCount = new Set(milestones.map((m) => Math.floor(m.year / 100))).size;
  const decadeDisabled = milestones.length < 3 || spanYears < 20 || decadeGroupCount <= 1;
  const centuryDisabled = milestones.length < 3 || spanYears < 100 || centuryGroupCount <= 1;

  const handleMilestoneClick = (index: number, milestone: Milestone) => {
    // V2c: 再点同一里程碑 = 清除筛选（回到全时段）
    if (activeIndex === index) {
      setActiveIndex(null);
      onYearChange?.(null);
      return;
    }
    setActiveIndex(index);
    onYearChange?.(milestone.year);

    // Scroll milestone into view
    const container = scrollRef.current;
    if (container) {
      const child = container.children[index] as HTMLElement;
      if (child) {
        child.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
      }
    }
  };

  // V2d: 展开/收起切换（独立于年份联动）
  const toggleExpand = (index: number) => {
    setExpandedIndex((cur) => (cur === index ? null : index));
  };

  if (isLoading) {
    return (
      <div className="h-24 bg-surface-card/80 backdrop-blur-sm rounded-2xl border border-border-default p-4 shadow-[var(--shadow-card)]">
        <div className="flex gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-20 shrink-0 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (milestones.length === 0) {
    return (
      <div className="h-24 bg-surface-card/80 backdrop-blur-sm rounded-2xl border border-border-default flex items-center justify-center gap-2 text-sm text-surface-muted-foreground shadow-[var(--shadow-card)]">
        <Clock className="w-4 h-4 text-brand-accent" />
        该概念的演化数据有限
      </div>
    );
  }

  return (
    <div className="bg-surface-card/80 backdrop-blur-sm rounded-2xl border border-border-default p-3 shadow-[var(--shadow-card)]">
      {/* 头部：标题 + 里程碑数 + 粒度切换 */}
      <div className="flex items-center gap-2 mb-3">
        <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-brand-accent/15 text-brand-accent">
          <Clock className="w-4 h-4" />
        </span>
        <span className="text-sm font-medium text-surface-foreground font-heading">
          演化时间轴
        </span>
        <span className="text-xs text-surface-muted-foreground">
          {milestones.length} 个里程碑
        </span>
        {activeIndex !== null && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-brand-accent/15 text-brand-accent border border-brand-accent/20">
            已筛选 {groups[activeIndex]?.representative.year ?? ""} · 点击可清除
          </span>
        )}
        {/* V2b: 粒度切换 segmented control */}
        <div className="ml-auto flex items-center gap-0.5 text-xs" role="group" aria-label="时间粒度">
          {(["year", "decade", "century"] as const).map((g) => {
            const disabled = g === "decade" ? decadeDisabled : g === "century" ? centuryDisabled : false;
            const label = g === "year" ? "年" : g === "decade" ? "十年" : "世纪";
            return (
              <button
                key={g}
                disabled={disabled}
                aria-pressed={granularity === g}
                title={disabled ? "里程碑过少或时间跨度不足，无法聚合到该粒度" : undefined}
                onClick={() => {
                  setGranularity(g);
                  setActiveIndex(null);
                  onYearChange?.(null);
                  setExpandedIndex(null);
                }}
                className={`px-2 py-1 rounded-lg border transition-all duration-200 cursor-pointer ${
                  granularity === g
                    ? "bg-brand-accent text-surface-card border-brand-accent shadow-[var(--shadow-glow-sm)]"
                    : disabled
                      ? "bg-surface-card/40 border-border-default text-surface-muted-foreground/40 cursor-not-allowed"
                      : "bg-surface-card/60 border-border-default text-surface-muted-foreground hover:text-surface-foreground hover:bg-surface-muted"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* V2a: 基线 + 刻度 + 里程碑卡片 + 竖线连接（flex 流式，防同年重叠） */}
      <div className="relative">
        <div
          ref={scrollRef}
          className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin pt-4"
          style={{ scrollbarWidth: "thin" }}
        >
          {groups.map((group, gi) => {
            const m = group.representative;
            const isActive = activeIndex === group.representativeIndex;
            const isExpanded = expandedIndex === group.representativeIndex;
            const sourceUrl = m.source_url || "";

            return (
              <div
                key={`${group.label}-${gi}`}
                className="shrink-0 w-28 flex flex-col items-stretch"
              >
                {/* 竖线 + 刻度点 */}
                <div className="flex justify-center">
                  <div className={`w-px h-4 ${isActive ? "bg-brand-accent" : "bg-border-default"}`} />
                </div>
                <div className="flex justify-center -mt-px">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      isActive
                        ? "bg-brand-accent shadow-[0_0_6px_var(--color-accent)]"
                        : "bg-border-default"
                    }`}
                  />
                </div>

                {/* 卡片：整卡点击 = 年份联动；内部展开按钮/来源链接 stopPropagation 隔离 */}
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => handleMilestoneClick(group.representativeIndex, m)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleMilestoneClick(group.representativeIndex, m);
                    }
                  }}
                  className={`mt-1 p-2 rounded-xl border text-left transition-all duration-200 cursor-pointer flex flex-col items-start ${
                    isActive
                      ? "border-brand-accent/60 bg-brand-accent/10 ring-1 ring-brand-accent/30 shadow-[var(--shadow-glow-sm)]"
                      : "border-border-default hover:border-surface-muted-foreground/50 hover:bg-surface-muted/50 hover:-translate-y-0.5"
                  }`}
                >
                  <div className="text-xs font-bold text-brand-accent w-full flex items-center justify-between">
                    {group.label}
                    {group.memberCount > 1 && (
                      <span className="text-[9px] text-surface-muted-foreground font-normal">
                        ×{group.memberCount}
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 text-xs text-surface-foreground truncate font-medium w-full">
                    {m.title}
                  </div>
                  {isExpanded ? (
                    <div className="mt-0.5 text-[10px] text-surface-muted-foreground leading-relaxed w-full">
                      {m.description}
                      {sourceUrl && (
                        <div className="mt-1">
                          <SourceLink url={sourceUrl} name="来源" evidence={m.description} />
                        </div>
                      )}
                    </div>
                  ) : (
                    <>
                      {m.description && (
                        <div className="mt-0.5 text-[10px] text-surface-muted-foreground line-clamp-2 overflow-hidden w-full">
                          {m.description}
                        </div>
                      )}
                    </>
                  )}
                  {/* 展开/收起按钮（独立于年份联动） */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleExpand(group.representativeIndex);
                    }}
                    className="mt-1 text-[10px] text-brand-accent hover:underline cursor-pointer"
                    aria-expanded={isExpanded}
                  >
                    {isExpanded ? "收起" : "展开"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* 基线 */}
        <div className="absolute bottom-2 left-0 right-0 h-px bg-gradient-to-r from-brand-accent/60 via-border-default to-border-default pointer-events-none" />
      </div>
    </div>
  );
}
