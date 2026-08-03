import LoadingSpinner from "@/components/ui/LoadingSpinner";

export default function SearchLoading() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
      <LoadingSpinner size="lg" />
      <p className="text-xs text-surface-muted-foreground font-mono">正在搜索…</p>
    </div>
  );
}
