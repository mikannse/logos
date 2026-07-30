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
      <div className="text-destructive mb-4 text-4xl">⚠</div>
      <h2 className="text-xl font-semibold text-surface-foreground">
        出错了
      </h2>
      <p className="mt-2 text-sm text-surface-muted-foreground max-w-sm">
        {error.message || "页面加载失败，请重试"}
      </p>
      <button
        onClick={reset}
        className="mt-4 px-4 py-2 bg-brand-accent text-white rounded-md text-sm hover:bg-blue-700 transition-colors cursor-pointer"
      >
        重试
      </button>
    </div>
  );
}
