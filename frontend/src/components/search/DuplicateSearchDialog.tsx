"use client";

import { useEffect, useCallback } from "react";
import { History, RefreshCw } from "lucide-react";
import { formatSavedAt } from "@/lib/format";

interface DuplicateSearchDialogProps {
  query: string;
  entityName: string;
  savedAt: string;
  /** 查看历史快照：直接加载已保存的图谱 + 时间轴 */
  onViewSnapshot: () => void;
  /** 重新搜索：重新构建最新数据并更新快照 */
  onReSearch: () => void;
  onClose: () => void;
}

export default function DuplicateSearchDialog({
  query,
  entityName,
  savedAt,
  onViewSnapshot,
  onReSearch,
  onClose,
}: DuplicateSearchDialogProps) {
  const handleEsc = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleEsc);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleEsc);
      document.body.style.overflow = "";
    };
  }, [handleEsc]);

  return (
    <div
      // pointer-events-none：遮罩不拦截背景（图谱）的缩放/拖拽事件，
      // 否则 fixed inset-0 覆盖整个视口，用户无法操作被挡住的图谱。
      // 卡片自身 pointer-events-auto 保留全部交互（按钮/点遮罩关闭）。
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh] bg-black/50 backdrop-blur-sm p-4 pointer-events-none"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label={`"${entityName || query}" 已有历史结果`}
    >
      <div className="w-full max-w-md bg-surface-card rounded-xl shadow-[var(--shadow-modal)] overflow-hidden animate-in fade-in zoom-in-95 pointer-events-auto">
        {/* Header */}
        <div className="px-6 pt-6 pb-3">
          <div className="flex items-center gap-2 text-surface-muted-foreground mb-1">
            <History className="w-4 h-4" />
            <span className="text-xs font-medium">搜索历史</span>
          </div>
          <h2 className="text-lg font-semibold text-surface-foreground font-heading">
            &ldquo;{entityName || query}&rdquo; 已有历史结果
          </h2>
          <p className="text-sm text-surface-muted-foreground mt-1">
            该名词的历史快照保存于 {formatSavedAt(savedAt)}。
            要查看历史结果，还是重新搜索最新数据？
          </p>
        </div>

        {/* Actions */}
        <div className="px-6 pb-6 pt-2 flex flex-col gap-2">
          <button
            onClick={onViewSnapshot}
            className="w-full inline-flex items-center justify-center gap-2 h-10 px-4 bg-brand-accent text-white rounded-lg text-sm font-medium hover:bg-brand-accent/90 transition-colors duration-150 cursor-pointer"
          >
            <History className="w-4 h-4" />
            查看历史快照
          </button>
          <button
            onClick={onReSearch}
            className="w-full inline-flex items-center justify-center gap-2 h-10 px-4 border border-border-default bg-transparent text-surface-foreground rounded-lg text-sm font-medium hover:bg-surface-muted transition-colors duration-150 cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
            重新搜索
          </button>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-border-default flex items-center justify-between text-xs text-surface-muted-foreground">
          <span>Esc 关闭</span>
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
