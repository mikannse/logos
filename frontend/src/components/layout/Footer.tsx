import Link from "next/link";

export default function Footer() {
  return (
    <footer className="mt-auto py-8 text-center text-sm text-surface-muted-foreground border-t border-border-default">
      <div className="max-w-7xl mx-auto px-4">
        <p>Logos © 2026 · 知识探索平台</p>
        <div className="mt-2 flex justify-center gap-4">
          <Link href="/" className="hover:text-surface-foreground transition-colors">
            首页
          </Link>
          <Link href="/search" className="hover:text-surface-foreground transition-colors">
            搜索
          </Link>
        </div>
      </div>
    </footer>
  );
}
