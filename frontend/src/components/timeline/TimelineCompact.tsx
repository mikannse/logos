"use client";

import { useEffect, useRef, useState } from "react";
import { Clock } from "lucide-react";
import { fetchTimeline, Milestone } from "@/lib/api";
import Skeleton from "@/components/ui/Skeleton";

interface TimelineCompactProps {
  nounId: string;
  onYearChange?: (year: number | null) => void;
}

export default function TimelineCompact({ nounId, onYearChange }: TimelineCompactProps) {
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!nounId) return;
    setIsLoading(true);

    fetchTimeline(nounId)
      .then((data) => {
        setMilestones(data.milestones || []);
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, [nounId]);

  const handleMilestoneClick = (index: number, milestone: Milestone) => {
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

  if (isLoading) {
    return (
      <div className="h-24 bg-surface-card rounded-xl border border-border-default p-4">
        <div className="flex gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-20 shrink-0 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (milestones.length === 0) {
    return (
      <div className="h-24 bg-surface-card rounded-xl border border-border-default flex items-center justify-center gap-2 text-sm text-surface-muted-foreground">
        <Clock className="w-4 h-4" />
        该概念的演化数据有限
      </div>
    );
  }

  return (
    <div className="bg-surface-card rounded-xl border border-border-default p-3">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-4 h-4 text-brand-accent" />
        <span className="text-sm font-medium text-surface-foreground font-heading">
          演化时间轴
        </span>
        <span className="text-xs text-surface-muted-foreground">
          {milestones.length} 个里程碑
        </span>
      </div>

      <div
        ref={scrollRef}
        className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin"
        style={{ scrollbarWidth: "thin" }}
      >
        {milestones.map((m, i) => (
          <button
            key={i}
            onClick={() => handleMilestoneClick(i, m)}
            className={`shrink-0 w-28 p-2 rounded-lg border text-left transition-all duration-150 cursor-pointer ${
              activeIndex === i
                ? "border-brand-accent bg-brand-accent/5 ring-1 ring-brand-accent/30"
                : "border-border-default hover:border-surface-muted-foreground"
            }`}
          >
            <div className="text-xs font-bold text-brand-accent">{m.year}</div>
            <div className="mt-0.5 text-xs text-surface-foreground truncate font-medium">
              {m.title}
            </div>
            {m.description && (
              <div className="mt-0.5 text-[10px] text-surface-muted-foreground line-clamp-2">
                {m.description}
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
