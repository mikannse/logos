"use client";

import React, { useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { FileQuestion } from "lucide-react";
import { CONFIDENCE_LEVELS } from "@/lib/constants";

export interface DisambiguationItem {
  id: string;
  label: string;
  label_en: string;
  type_label: string;
  confidence: number;
  summary: string;
}

interface DisambiguationDialogProps {
  query: string;
  items: DisambiguationItem[];
  /** 关闭（选择时也会调用，仅负责隐藏弹窗） */
  onClose: () => void;
  /** 用户显式选择某个实体（parent 接管导航） */
  onSelect?: (item: DisambiguationItem) => void;
  /** 用户忽略弹窗（Esc / 点击背板 / 取消），与"选择"区分 */
  onDismiss?: () => void;
}

export default function DisambiguationDialog({
  query,
  items,
  onClose,
  onSelect,
  onDismiss,
}: DisambiguationDialogProps) {
  const router = useRouter();
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  // 忽略弹窗：先关闭，再通知 parent（parent 决定是否默认选中第一个结果）
  const handleDismiss = useCallback(() => {
    onClose();
    onDismiss?.();
  }, [onClose, onDismiss]);

  const handleSelect = useCallback(
    (item: DisambiguationItem) => {
      onClose();
      if (onSelect) {
        onSelect(item); // parent takes full control
        return;
      }
      router.push(`/search?q=${encodeURIComponent(item.id)}&name=${encodeURIComponent(item.label)}`);
    },
    [router, onClose, onSelect]
  );

  const handleEsc = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") handleDismiss();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, items.length - 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (items[selectedIndex]) {
          handleSelect(items[selectedIndex]);
        }
      }
    },
    [handleDismiss, items, selectedIndex, handleSelect]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleEsc);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleEsc);
      document.body.style.overflow = "";
    };
  }, [handleEsc]);

  // Scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.children[selectedIndex] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  const confidenceColor = (c: number) => {
    if (c >= CONFIDENCE_LEVELS.HIGH.min) return "text-success";
    if (c >= CONFIDENCE_LEVELS.MEDIUM.min) return "text-warning";
    return "text-destructive";
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-surface/70 backdrop-blur-md p-4 animate-in fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleDismiss();
      }}
      role="dialog"
      aria-modal="true"
      aria-label={`"${query}" 多义消歧`}
    >
      <div className="w-full max-w-lg bg-surface-card/95 backdrop-blur-xl border border-border-default rounded-2xl shadow-[var(--shadow-modal)] overflow-hidden animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="px-6 pt-6 pb-3 border-b border-border-default bg-gradient-to-b from-brand-accent/5 to-transparent">
          <div className="flex items-center gap-2 text-brand-accent mb-1.5">
            <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-brand-accent/15">
              <FileQuestion className="w-3.5 h-3.5" />
            </span>
            <span className="text-xs font-medium uppercase tracking-wider">多义匹配</span>
          </div>
          <h2 className="text-lg font-semibold text-surface-foreground font-heading">
            &ldquo;{query}&rdquo; 有多个可能的意思
          </h2>
          <p className="text-sm text-surface-muted-foreground mt-1">
            请选择你要探索的实体：
          </p>
        </div>

        {/* Items list */}
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto px-2 py-2 space-y-1">
          {items.map((item, i) => (
            <button
              key={item.id}
              onClick={() => handleSelect(item)}
              onMouseEnter={() => setSelectedIndex(i)}
              className={`w-full text-left px-4 py-3 rounded-xl transition-all duration-150 cursor-pointer ${
                i === selectedIndex
                  ? "bg-brand-accent/10 ring-1 ring-brand-accent/30 shadow-[var(--shadow-glow-sm)]"
                  : "hover:bg-surface-muted/70"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-surface-foreground">
                      {item.label}
                    </span>
                    {item.label_en && (
                      <span className="text-xs text-surface-muted-foreground">
                        {item.label_en}
                      </span>
                    )}
                    <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-surface-muted text-surface-muted-foreground border border-border-default">
                      {item.type_label || "实体"}
                    </span>
                  </div>
                  {item.summary && (
                    <p className="mt-0.5 text-sm text-surface-muted-foreground line-clamp-2">
                      {item.summary}
                    </p>
                  )}
                </div>
                <span
                  className={`shrink-0 text-xs font-medium ${confidenceColor(
                    item.confidence
                  )}`}
                >
                  {Math.round(item.confidence * 100)}%
                </span>
              </div>
            </button>
          ))}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-border-default flex items-center justify-between text-xs text-surface-muted-foreground bg-surface-muted/30">
          <span className="font-mono">↑↓ 选择 · Enter 确认 · Esc 关闭</span>
          <button
            onClick={handleDismiss}
            className="px-3 py-1 rounded-lg hover:bg-surface-muted transition-colors cursor-pointer hover:text-surface-foreground"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
