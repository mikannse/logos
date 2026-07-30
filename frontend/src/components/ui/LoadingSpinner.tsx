export default function LoadingSpinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const sizeMap = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-8 w-8" };

  return (
    <div
      className={`animate-spin rounded-full border-2 border-surface-muted border-t-brand-accent ${sizeMap[size]}`}
      role="status"
      aria-label="加载中"
    />
  );
}
