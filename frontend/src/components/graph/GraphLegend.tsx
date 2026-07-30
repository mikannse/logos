"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { CONFIDENCE_LEVELS } from "@/lib/constants";

const EDGE_TYPES: Record<string, { label: string; color: string }> = {
  influence: { label: "影响", color: "#DC2626" },
  affiliation: { label: "隶属", color: "#2563EB" },
  creation: { label: "创作", color: "#16A34A" },
  competition: { label: "竞争", color: "#D97706" },
  collaboration: { label: "合作", color: "#8B5CF6" },
  other: { label: "其他", color: "#64748B" },
};

const NODE_TYPES: Record<string, { label: string; color: string; shape: string }> = {
  person: { label: "人物", color: "#2563EB", shape: "circle" },
  entity: { label: "实体", color: "#16A34A", shape: "square" },
  concept: { label: "概念", color: "#8B5CF6", shape: "square" },
  technology: { label: "技术", color: "#0891B2", shape: "square" },
  event: { label: "事件", color: "#D97706", shape: "diamond" },
  organization: { label: "组织", color: "#DC2626", shape: "square" },
};

const CONFIDENCE_LEGEND = [
  { label: `${CONFIDENCE_LEVELS.HIGH.label} (>{Math.round(CONFIDENCE_LEVELS.HIGH.min * 100)}%)`, style: "solid", opacity: "1" },
  { label: `${CONFIDENCE_LEVELS.MEDIUM.label} (${Math.round(CONFIDENCE_LEVELS.MEDIUM.min * 100)}-${Math.round(CONFIDENCE_LEVELS.HIGH.min * 100)}%)`, style: "solid", opacity: "0.6" },
  { label: `${CONFIDENCE_LEVELS.LOW.label} (<${Math.round(CONFIDENCE_LEVELS.MEDIUM.min * 100)}%)`, style: "dashed", opacity: "0.4" },
];

export default function GraphLegend() {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="bg-surface-card/90 backdrop-blur-sm border border-border-default rounded-lg text-xs max-w-[200px]">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 text-surface-foreground font-medium cursor-pointer"
      >
        <span>图例</span>
        <ChevronDown
          className={`w-3 h-3 transition-transform ${isOpen ? "" : "-rotate-90"}`}
        />
      </button>

      {isOpen && (
        <div className="px-3 pb-3 space-y-3">
          {/* Node types */}
          <div>
            <p className="text-surface-muted-foreground mb-1.5">节点类型</p>
            <div className="space-y-1">
              {Object.entries(NODE_TYPES).map(([key, val]) => (
                <div key={key} className="flex items-center gap-1.5">
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-sm shrink-0"
                    style={{ backgroundColor: val.color }}
                  />
                  <span className="text-surface-foreground">{val.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Edge types */}
          <div>
            <p className="text-surface-muted-foreground mb-1.5">关系类型</p>
            <div className="space-y-1">
              {Object.entries(EDGE_TYPES).map(([key, val]) => (
                <div key={key} className="flex items-center gap-1.5">
                  <span
                    className="inline-block h-0.5 w-4 shrink-0 rounded-full"
                    style={{ backgroundColor: val.color }}
                  />
                  <span className="text-surface-foreground">{val.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Confidence */}
          <div>
            <p className="text-surface-muted-foreground mb-1.5">置信度</p>
            <div className="space-y-1">
              {CONFIDENCE_LEGEND.map((cl, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span
                    className="inline-block h-0.5 w-4 shrink-0"
                    style={{
                      backgroundColor: "var(--color-foreground)",
                      opacity: cl.opacity,
                      borderTopStyle: cl.style === "dashed" ? "dashed" : "solid" as any,
                    }}
                  />
                  <span className="text-surface-foreground">{cl.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
