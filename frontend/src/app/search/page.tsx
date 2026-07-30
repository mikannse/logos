"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import SearchBar from "@/components/search/SearchBar";
import GraphSkeleton from "@/components/graph/GraphSkeleton";
import EmptyState from "@/components/ui/EmptyState";

function SearchContent() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";

  if (!query) {
    return (
      <EmptyState
        title="输入一个名词开始探索"
        description="在上方搜索框中输入名词，查看关系图谱与演化时间轴"
      />
    );
  }

  return (
    <div className="flex flex-col flex-1">
      {/* Search bar section */}
      <div className="w-full max-w-2xl mx-auto px-4 py-6">
        <SearchBar initialQuery={query} />
      </div>

      {/* Main content area */}
      <div className="flex-1 flex flex-col lg:flex-row gap-4 px-4 pb-4 max-w-7xl mx-auto w-full">
        {/* Graph area */}
        <div className="flex-1 min-h-[500px] bg-surface-card rounded-xl border border-border-default overflow-hidden">
          <GraphSkeleton />
        </div>
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-surface-muted border-t-brand-accent" />
        </div>
      }
    >
      <SearchContent />
    </Suspense>
  );
}
