"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] px-4 text-center">
      <div className="text-destructive mb-4 text-4xl animate-float">⚠</div>
      <h2 className="text-xl font-semibold text-surface-foreground font-heading">
        出错了
      </h2>
      <p className="mt-2 text-sm text-surface-muted-foreground max-w-sm">
        {error.message || "页面加载失败，请重试"}
      </p>
      <button
        onClick={reset}
        className="mt-4 px-5 py-2.5 bg-brand-accent text-surface-card rounded-xl text-sm font-medium hover:bg-brand-accent-strong hover:shadow-[var(--shadow-glow-sm)] active:scale-[0.98] transition-all duration-200 cursor-pointer"
      >
        重试
      </button>
    </div>
  );
}
