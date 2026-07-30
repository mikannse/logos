"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronDown, ArrowRight, Sparkles, Network, Clock } from "lucide-react";
import SearchBar from "@/components/search/SearchBar";

const POPULAR_CATEGORIES = [
  {
    name: "科学",
    terms: ["爱因斯坦", "相对论", "量子力学", "CRISPR", "进化论"],
    icon: "🔬",
  },
  {
    name: "技术",
    terms: ["区块链", "神经网络", "人工智能", "云计算", "量子计算"],
    icon: "💻",
  },
  {
    name: "人物",
    terms: ["孔子", "毛泽东", "达芬奇", "莎士比亚", "特斯拉"],
    icon: "👤",
  },
];

const FAQ_ITEMS = [
  {
    q: "Logos 的数据来源是什么？",
    a: "Logos 的数据主要来自 Wikidata（结构化数据）和 AI Web Search（非结构化数据）。系统通过多源交叉验证标注置信度，确保信息可靠性。",
  },
  {
    q: "搜索任何名词都能获得图谱吗？",
    a: "大多数常见名词（人物、概念、技术、事件）都能自动生成图谱。冷门名词可能需要稍长时间构建，系统会通过异步后台处理。",
  },
  {
    q: "如何使用时间轴功能？",
    a: "搜索名词后，页面底部的时间轴会自动展示 5-10 个关键里程碑。拖动滑块可以观察不同时期的关系变化。",
  },
  {
    q: "Logos 免费吗？",
    a: "MVP 阶段完全免费。未来会推出付费高级功能（如深度搜索、数据导出等），基础搜索功能永久免费。",
  },
  {
    q: "如何确保信息的准确性？",
    a: "每条关系和事实都标注置信度等级（高/中/低），并附带来源链接。用户可点击追溯数据源头自行验证。",
  },
];

function FAQAccordion() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div className="max-w-2xl mx-auto space-y-3">
      {FAQ_ITEMS.map((item, i) => (
        <div
          key={i}
          className="border border-border-default rounded-xl overflow-hidden bg-surface-card transition-shadow duration-200 hover:shadow-[var(--shadow-card)]"
        >
          <button
            onClick={() => setOpenIndex(openIndex === i ? null : i)}
            className="w-full flex items-center justify-between px-5 py-4 text-left cursor-pointer"
            aria-expanded={openIndex === i}
          >
            <span className="font-medium text-surface-foreground font-heading">
              {item.q}
            </span>
            <ChevronDown
              className={`w-5 h-5 text-surface-muted-foreground shrink-0 transition-transform duration-200 ${
                openIndex === i ? "rotate-180" : ""
              }`}
            />
          </button>
          {openIndex === i && (
            <div className="px-5 pb-4 text-sm text-surface-muted-foreground leading-relaxed animate-in fade-in slide-in-from-top-1">
              {item.a}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function Home() {
  return (
    <div className="flex flex-col flex-1">
      {/* Section 1: Hero */}
      <section className="flex flex-col items-center justify-center px-4 py-24 md:py-32 text-center">
        <h1 className="text-[clamp(2.5rem,6vw,4rem)] font-bold leading-[1.1] tracking-tight text-surface-foreground max-w-3xl font-heading">
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

      {/* Section 2: Feature Cards */}
      <section className="w-full max-w-5xl mx-auto px-4 pb-20">
        <div className="grid md:grid-cols-3 gap-6">
          {[
            {
              icon: <Network className="w-6 h-6 text-brand-accent" />,
              title: "关系图谱",
              desc: "自动展示名词间的深层联系，力导向图拖拽缩放探索",
            },
            {
              icon: <Clock className="w-6 h-6 text-brand-accent" />,
              title: "演化时间轴",
              desc: "关键里程碑一目了然，拖动滑块观察历史变迁",
            },
            {
              icon: <Sparkles className="w-6 h-6 text-brand-accent" />,
              title: "AI 驱动",
              desc: "智能提取实体关系，多源数据交叉验证置信度",
            },
          ].map((feature) => (
            <div
              key={feature.title}
              className="p-6 rounded-xl bg-surface-card border border-border-default shadow-[var(--shadow-card)] hover:shadow-[var(--shadow-elevated)] transition-all duration-200 group"
            >
              <div className="mb-3">{feature.icon}</div>
              <h3 className="text-lg font-semibold text-surface-card-foreground font-heading">
                {feature.title}
              </h3>
              <p className="mt-2 text-sm text-surface-muted-foreground leading-relaxed">
                {feature.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Section 3: Popular Categories */}
      <section className="w-full max-w-5xl mx-auto px-4 pb-20">
        <h2 className="text-2xl font-bold text-center text-surface-foreground mb-10 font-heading">
          热门分类
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          {POPULAR_CATEGORIES.map((cat) => (
            <div
              key={cat.name}
              className="p-6 rounded-xl bg-surface-card border border-border-default"
            >
              <div className="text-2xl mb-3">{cat.icon}</div>
              <h3 className="text-base font-semibold text-surface-foreground mb-3 font-heading">
                {cat.name}
              </h3>
              <div className="flex flex-wrap gap-2">
                {cat.terms.map((term) => (
                  <Link
                    key={term}
                    href={`/search?q=${encodeURIComponent(term)}`}
                    className="px-3 py-1 text-sm rounded-full bg-surface-muted text-surface-muted-foreground hover:bg-brand-accent hover:text-white transition-colors duration-150"
                  >
                    {term}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Section 4: FAQ */}
      <section className="w-full max-w-5xl mx-auto px-4 pb-20">
        <h2 className="text-2xl font-bold text-center text-surface-foreground mb-10 font-heading">
          常见问题
        </h2>
        <FAQAccordion />
      </section>

      {/* Section 5: CTA */}
      <section className="w-full max-w-3xl mx-auto px-4 pb-24 text-center">
        <div className="p-10 rounded-2xl bg-gradient-to-br from-brand-accent/5 to-brand-primary/5 border border-border-default">
          <h2 className="text-2xl font-bold text-surface-foreground mb-4 font-heading">
            准备好开始探索了吗？
          </h2>
          <p className="text-surface-muted-foreground mb-8 max-w-md mx-auto">
            搜一个名词，看看它背后的关系网络和演化故事
          </p>
          <Link
            href="/search"
            className="inline-flex items-center gap-2 h-12 px-6 bg-brand-accent text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors duration-150"
          >
            开始探索
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto py-8 text-center text-sm text-surface-muted-foreground border-t border-border-default">
        Logos © 2026 · 知识探索平台
      </footer>
    </div>
  );
}
