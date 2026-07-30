import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] px-4 text-center">
      <h1 className="text-6xl font-bold text-surface-muted-foreground">404</h1>
      <h2 className="mt-4 text-xl font-semibold text-surface-foreground">
        页面未找到
      </h2>
      <p className="mt-2 text-sm text-surface-muted-foreground">
        您访问的页面不存在
      </p>
      <Link
        href="/"
        className="mt-6 px-4 py-2 bg-brand-accent text-white rounded-md text-sm hover:bg-blue-700 transition-colors"
      >
        返回首页
      </Link>
    </div>
  );
}
