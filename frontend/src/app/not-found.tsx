import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] px-4 text-center">
      <h1 className="text-6xl font-bold font-heading text-gradient">404</h1>
      <h2 className="mt-4 text-xl font-semibold text-surface-foreground">
        页面未找到
      </h2>
      <p className="mt-2 text-sm text-surface-muted-foreground">
        您访问的页面不存在，或者它从未被记录在这张知识地图上。
      </p>
      <Link
        href="/"
        className="mt-6 px-5 py-2.5 bg-brand-accent text-surface-card rounded-xl text-sm font-medium hover:bg-brand-accent-strong hover:shadow-[var(--shadow-glow-sm)] active:scale-[0.98] transition-all duration-200"
      >
        返回首页
      </Link>
    </div>
  );
}
