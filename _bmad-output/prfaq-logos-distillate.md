---
title: "PRFAQ Distillate: Logos"
type: llm-distillate
source: "prfaq-logos.md"
created: "2026-07-30"
purpose: "Token-efficient context for downstream PRD creation"
---

## Product Identity

- Product name: **Logos** (λόγος — 古希腊语「言语」「理性」「知识」)
- Concept type: Commercial product (B2C, 面向知识工作者/普通用户)
- Tagline: 给你的好奇心装一张知识地图
- Core metaphor: "知识侦探" — 你丢线索，它帮你把拼图拼起来

## Rejected / Discarded Framings

- 「名词知识图谱」作为产品名被弃用 → 过于技术化，普通人听不懂；改用 Logos（有文化辨识度、适合传播）
- 「AI 知识图谱平台」弃用 → 听起来像企业级产品
- 面向「所有人」太宽泛 → 收缩到「知识工作者」起步（记者/分析师/创作者/研究者）
- 不做「另一个 Wikipedia」→ Wikipedia 是静态参考，Logos 是动态探索
- 不做「更好的 Obsidian」→ Obsidian 是手动工具，Logos 是自动的

## Accepted Design Principles (8条)

1. 渐进式信息密度 — 先给全景，想看细节再深入
2. 即时响应 + 流式加载 — 不要用户等
3. 智能筛选 + 关联强度排序 — 最重要的关系优先展示
4. 置信度标注 + 源头可追溯 — 每个事实都有根
5. 自动多粒度关键里程碑 — 5-10 个节点自动摘要
6. 免费探索 + 高级功能付费
7. 多源交叉验证 + 源质量评级
8. 人物优先原则 — 人物作为默认探索入口

## Technical Context

- MVP 技术栈: Next.js v16 + FastAPI + Neo4j (含向量索引)
- 可视化: D3.js force-graph + vis-timeline (MVP); Three.js (Phase 2)
- 数据源: Wikidata API → LLM 补充 → spaCy 备选 (分层)
- LLM 融合: GraphRAG 三层检索架构 (图 → 语义 → LLM)
- 缓存: 语义相似缓存 + 分层检索 + 上下文裁剪 → 节省 LLM 成本 60-80%
- 部署: Vercel (前端) + 轻量主机 (后端); 暂不 Docker; 暂不 Milvus (Neo4j 内置向量)
- 月度成本: ~$55-530/月 (LLM API 是大头)

## Competitive Intelligence

- 市场空白: 「高自动化 + 面向普通用户」象限无成熟产品
- 知识图谱市场: CAGR 18-32%, 2026 年约 $1.9B, 2032 年约 $9.9B
- 竞品四象限: 引擎(Neo4j) | 企业平台(Stardog) | AI 原生(Diffbot) | 个人管理(Obsidian) — Logos 跨越 A 和 D
- 时间窗口: ~3-5 年，大厂向下兼容需要时间
- 最可能的威胁: Diffbot 做界面、或 Google 做简化版

## User Personas (来自脑暴)

| 角色 | 场景 | 核心需求 |
|------|------|----------|
| 小明 (普通用户) | 搜一个不懂的名词 | 快速理解 + 看到相关 |
| 林记者 (记者) | 调查人物关系 | 发现隐藏关联 + 利益关系 |
| 王总 (投资者) | 研究领域趋势 | 技术树 + 人物/公司分布 + 推演 |
| 阿花 (创作者) | 积累主题素材 | 演化脉络 + 个人知识库 |

## Scope Signals

### Phase 1 In-scope (MVP)
- ✅ 搜索框输入名词 → 关系图谱 + 时间轴 + AI 问答
- ✅ 中英文双语输入
- ✅ 人物优先入口
- ✅ 多源交叉验证 + 置信度标注
- ✅ 渐进式信息密度展示

### Phase 1 Out-of-scope
- ❌ 用户注册/登录墙 (MVP 不做注册限制)
- ❌ 用户个人知识库
- ❌ 多名词对比
- ❌ 未来推演模式
- ❌ 3D 可视化
- ❌ 名词 Fork
- ❌ 知识卡片分享

### Phase 2 Candidates
- AI 深度推理、多名词对比、多语言全覆盖、用户上传数据
- Three.js 3D 可视化、Milvus 向量库、Celery 流水线

### Phase 3 Candidates
- 3D 名词街景、知识社交网络、未来推演模式、利益关系分析

## Open Questions / Unknowns

- 🔴 **核心假设:** 普通用户是否愿意用图谱化方式探索知识？(MVP 的首要验证目标)
- 🟡 **定价验证:** $9.99/月 是否被目标用户接受？
- 🟡 **移动端:** 初期只做 Web 是否足够？知识探索的触发场景很多在手机上
- 🟡 **冷启动:** 第一个 100 个用户的获取策略还需要具体化
- 🟡 **冷门词质量:** 数据稀疏的冷门名词图谱质量能过基线吗？
- 🟢 **合规:** 中国 AI 算法备案的具体流程和时限需要核实

## Resource Estimates

- 团队: 3-5 人 MVP (前端+后端+AI/NLP+设计/PM+创始人)
- 核心开发: 6-8 周 (核心闭环)
- 打磨 + 内测: 4-6 周
- MVP 总时间: 3-4 个月
- 月运营成本: ~$55-530/月

## Verdict Findings (actionable items)

### Needs More Heat
1. 用户获取策略 — 细化首个 100 用户的获取路径
2. 定价模型验证 — 用户对付费意愿的测试计划
3. 移动端策略 — Phase 1 结束前明确
4. 冷门词图谱质量基线 — 定义最低可接受标准
5. 数据源依赖风险 — Wikidata API 可用性变化如何应对

### Cracks in the Foundation
1. **核心假设验证是命门** — 在验证前所有商业计划都建立在沙地上
2. **团队多面手要求高** — 3-5 人覆盖前后端+AI+设计+推广，技能密度要求极高
3. **LLM 成本非线性增长** — 用户增长快时分层缓存是否够用？需要上限控制机制

---

## Coaching Notes Archives

### Stage 1 - Ignition
- Concept type: Commercial product (面向消费者的 SaaS)
- 初始假设被挑战: 「知识图谱」对普通人太抽象 → 用「名词地图」「知识侦探」等更直观的比喻
- 方向确定依据: 市场空白分析显示「高自动化+面向普通用户」象限无竞品
- Key user context: BMad 是独立创始人/开发者，资源有限 → MVP 必须轻、快

### Stage 2 - Press Release
- Rejected headline framings:
  - 「AI 知识图谱工具」→ 太技术化
  - 「名词探索引擎」→ 不够动人
  - 「给你的好奇心装一张知识地图」→ 最终采用，有画面感
- 差异化定位锚定: 自动构建 + 时间轴 + AI 对话三合一，而非单一功能竞争
- 竞品定位讨论: 明确不做 Obsidian 对手，不做 Neo4j 对手，不做 Wikipedia 替代
- Out-of-scope 记录: 注册墙、个人知识库、多名词对比等在 MVP 后

### Stage 3 - Customer FAQ
- Gaps revealed: 冷门名词质量、移动端策略、定价验证是尚未充分回答的客户关切
- Trade-offs: MVP 不做注册墙（降低门槛）vs 无法获取用户信息（不追踪使用情况）
- 竞争情报: 「用户说 vs Google」是最常见的质疑 — 需要准备好对比话术

### Stage 4 - Internal FAQ
- Feasibility risks: LLM 成本控制是最大的技术/运营风险
- 资源估算: 3-5 人团队 + 3-4 月 MVP 是最乐观估算，实际可能 +50%
- Time-to-market: 核心闭环 6-8 周可行，但体验打磨+反馈迭代容易被低估
- 核心未解决问题: 如果用户不喜欢图谱交互方式，回退路径是什么？
