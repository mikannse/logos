import LoadingSpinner from "@/components/ui/LoadingSpinner";

export default function Loading() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
      <LoadingSpinner size="lg" />
      <p className="text-xs text-surface-muted-foreground font-mono">构建知识地图中…</p>
    </div>
  );
}
