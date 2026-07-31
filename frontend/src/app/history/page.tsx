"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { History, Trash2, Clock } from "lucide-react";
import { fetchHistoryList, deleteHistorySnapshot, HistoryItem } from "@/lib/api";
import { formatSavedAt } from "@/lib/format";
import EmptyState from "@/components/ui/EmptyState";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

export default function HistoryPage() {
  const router = useRouter();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchHistoryList();
      setItems(data.items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载历史记录失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // 点击历史记录：跳转到专用详情页，直接渲染已保存快照（不经过搜索流程）
  const handleOpen = useCallback(
    (item: HistoryItem) => {
      router.push(`/history/${encodeURIComponent(item.noun_id)}`);
    },
    [router]
  );

  const handleDelete = useCallback(async (nounId: string) => {
    try {
      await deleteHistorySnapshot(nounId);
      setItems((prev) => prev.filter((i) => i.noun_id !== nounId));
    } catch {
      // 删除失败保持现状
    }
  }, []);

  return (
    <div className="w-full max-w-3xl mx-auto px-4 py-6 flex flex-col flex-1">
      <div className="flex items-center gap-2 mb-5">
        <History className="w-5 h-5 text-brand-accent" />
        <h1 className="text-xl font-semibold text-surface-foreground font-heading">
          搜索历史
        </h1>
        {!isLoading && (
          <span className="text-sm text-surface-muted-foreground">
            {items.length} 条快照
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <LoadingSpinner />
        </div>
      ) : error ? (
        <EmptyState title="加载历史记录失败" description={error} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<History className="w-12 h-12" />}
          title="还没有搜索历史"
          description="搜索一个名词后，系统会自动保存图谱与时间轴快照，方便你随时回顾。"
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((item) => (
            <li
              key={item.noun_id}
              className="group px-4 py-3 bg-surface-card rounded-xl border border-border-default hover:border-brand-accent/40 hover:bg-surface-muted/40 transition-colors"
            >
              <div className="flex items-center gap-3">
                <button
                  onClick={() => handleOpen(item)}
                  className="flex-1 min-w-0 text-left cursor-pointer"
                  aria-label={`打开 ${item.entity_name || item.query} 的历史快照`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-surface-foreground truncate">
                      {item.entity_name || item.query || item.noun_id}
                    </span>
                    <span className="text-xs font-mono text-surface-muted-foreground shrink-0">
                      {item.noun_id}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-1 text-xs text-surface-muted-foreground">
                    <Clock className="w-3 h-3" />
                    <span>{formatSavedAt(item.saved_at)}</span>
                    {item.query && item.query !== item.entity_name && (
                      <span className="text-surface-muted-foreground/70">
                        · 查询词「{item.query}」
                      </span>
                    )}
                  </div>
                </button>
                <button
                  onClick={() => handleDelete(item.noun_id)}
                  aria-label={`删除 ${item.entity_name || item.query} 的历史快照`}
                  className="shrink-0 p-1.5 rounded-lg text-surface-muted-foreground hover:bg-surface-muted hover:text-destructive transition-colors cursor-pointer"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
