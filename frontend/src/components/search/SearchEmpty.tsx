import EmptyState from "@/components/ui/EmptyState";

export default function SearchEmpty({ query }: { query: string }) {
  return (
    <EmptyState
      title={`未找到关于 "${query}" 的信息`}
      description="请检查拼写或尝试其他关键词"
      action={
        <div className="flex flex-wrap gap-2 justify-center">
          {["爱因斯坦", "区块链", "CRISPR", "神经网络", "量子计算"].map(
            (term) => (
              <a
                key={term}
                href={`/search?q=${encodeURIComponent(term)}`}
                className="px-3 py-1 text-sm rounded-full border border-border-default bg-surface-card/60 text-surface-muted-foreground hover:border-brand-accent/60 hover:text-surface-foreground hover:bg-brand-accent/5 transition-colors duration-200 backdrop-blur-sm"
              >
                {term}
              </a>
            )
          )}
        </div>
      }
    />
  );
}
