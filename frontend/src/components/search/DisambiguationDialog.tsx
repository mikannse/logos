"use client";

import React, { useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { FileQuestion } from "lucide-react";

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
  onClose: () => void;
}

export default function DisambiguationDialog({
  query,
  items,
  onClose,
}: DisambiguationDialogProps) {
  const router = useRouter();
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  const handleSelect = useCallback(
    (item: DisambiguationItem) => {
      // Navigate to the entity using its Wikidata ID
      router.push(`/search?q=${encodeURIComponent(item.id)}&name=${encodeURIComponent(item.label)}`);
    },
    [router]
  );

  const handleEsc = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
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
    [onClose, items, selectedIndex, handleSelect]
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
    if (c >= 0.8) return "text-success";
    if (c >= 0.5) return "text-warning";
    return "text-destructive";
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/50 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label={`"${query}" 多义消歧`}
    >
      <div className="w-full max-w-lg bg-surface-card rounded-xl shadow-[var(--shadow-modal)] overflow-hidden animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="px-6 pt-6 pb-3">
          <div className="flex items-center gap-2 text-surface-muted-foreground mb-1">
            <FileQuestion className="w-4 h-4" />
            <span className="text-xs font-medium">多义匹配</span>
          </div>
          <h2 className="text-lg font-semibold text-surface-foreground font-heading">
            &ldquo;{query}&rdquo; 有多个可能的意思
          </h2>
          <p className="text-sm text-surface-muted-foreground mt-1">
            请选择你要探索的实体：
          </p>
        </div>

        {/* Items list */}
        <div ref={listRef} className="max-h-[50vh] overflow-y-auto px-2 pb-2">
          {items.map((item, i) => (
            <button
              key={item.id}
              onClick={() => handleSelect(item)}
              onMouseEnter={() => setSelectedIndex(i)}
              className={`w-full text-left px-4 py-3 rounded-lg transition-colors duration-100 cursor-pointer ${
                i === selectedIndex
                  ? "bg-brand-accent/10 ring-1 ring-brand-accent/30"
                  : "hover:bg-surface-muted"
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
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-muted text-surface-muted-foreground">
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
        <div className="px-6 py-3 border-t border-border-default flex items-center justify-between text-xs text-surface-muted-foreground">
          <span>↑↓ 选择 · Enter 确认 · Esc 关闭</span>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded-md hover:bg-surface-muted transition-colors cursor-pointer"
          >
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
