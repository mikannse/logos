import Link from "next/link";
import SearchBar from "@/components/search/SearchBar";

export default function Home() {
  return (
    <div className="flex flex-col flex-1">
      {/* Hero Section */}
      <section className="flex flex-col items-center justify-center px-4 py-24 md:py-32 text-center">
        <h1 className="text-[clamp(2.5rem,6vw,4rem)] font-bold leading-[1.1] tracking-tight text-surface-foreground max-w-3xl">
          给你的好奇心
          <br />
          装一张知识地图
        </h1>
        <p className="mt-6 text-lg md:text-xl text-surface-muted-foreground max-w-xl">
          搜一个名词，自动构建关系图谱与演化时间轴
        </p>

        <div className="mt-10 w-full max-w-lg">
          <SearchBar />
        </div>

        <div className="mt-6 flex flex-wrap gap-3 justify-center">
          {["爱因斯坦", "区块链", "CRISPR"].map((term) => (
            <Link
              key={term}
              href={`/search?q=${encodeURIComponent(term)}`}
              className="px-4 py-2 text-sm rounded-full border border-border-default text-surface-muted-foreground hover:border-surface-muted-foreground hover:text-surface-foreground transition-colors duration-150"
            >
              {term}
            </Link>
          ))}
        </div>
      </section>

      {/* Feature Cards */}
      <section className="w-full max-w-5xl mx-auto px-4 pb-24">
        <div className="grid md:grid-cols-3 gap-6">
          {[
            {
              icon: "🔗",
              title: "关系图谱",
              desc: "自动展示名词间的深层联系，拖拽缩放探索",
            },
            {
              icon: "📅",
              title: "演化时间轴",
              desc: "关键里程碑一目了然，拖动滑块看变迁",
            },
            {
              icon: "🤖",
              title: "AI 驱动",
              desc: "智能提取实体关系，多源数据交叉验证",
            },
          ].map((feature) => (
            <div
              key={feature.title}
              className="p-6 rounded-xl bg-surface-card border border-border-default shadow-[var(--shadow-card)] hover:shadow-[var(--shadow-elevated)] transition-shadow duration-200"
            >
              <div className="text-2xl mb-3">{feature.icon}</div>
              <h3 className="text-lg font-semibold text-surface-card-foreground">
                {feature.title}
              </h3>
              <p className="mt-2 text-sm text-surface-muted-foreground">
                {feature.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto py-8 text-center text-sm text-surface-muted-foreground border-t border-border-default">
        Logos © 2026 · 知识探索平台
      </footer>
    </div>
  );
}
