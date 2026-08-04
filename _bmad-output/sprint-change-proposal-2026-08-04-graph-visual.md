# Sprint Change Proposal — 图谱关系标注 · 时间线可视化 · 关系网扩展

- **日期**：2026-08-04
- **触发人**：BMad
- **状态**：**已批准（2026-08-04）** — 增量审阅完成，8/9 提案批准，1 提案（V1a）跳过；验证结论已并入
- **变更等级**：Moderate（Epic 2 多 Story 调整，需 PO/DEV 协同）

---

## 1. Issue Summary

### 触发原因

BMad 查看「马克思」的搜索结果后提出三点改进意见：

> 1. 图谱的各个实体之间没有标明关系
> 2. 底部的时间线还没有详细明确的说明，不直观
> 3. 关系网不够复杂，应当是一个复杂、更详细展开的庞大关系网

### 根因分析（代码级证据）

三点反馈分别对应三处**设计规范已承诺、但实现未落地**的规格缺口：

| # | 反馈 | 根因 | 代码证据 |
|:---|:---|:---|:---|
| 1 | 实体间未标明关系 | 边仅有颜色/粗细区分（对应 type/confidence），**无文字标签**；边无 hover 事件，来源/证据（`source_url`/`evidence`）在图上一处都看不到 | [GraphCanvas.tsx:197-207](frontend/src/components/graph/GraphCanvas.tsx#L197-L207) 只画 `line`；全文无 `edge label`/边 hover |
| 2 | 时间线不直观 | 时间轴仅为**横向卡片流**，无时间基线、刻度、连线；`handleYearChange` 是空桩（`// Future`）；FR-8 承诺的"年/十年/世纪"粒度缩放与 FR-9 的图谱联动**未实现**；描述被 `line-clamp-2` 截断 | [TimelineCompact.tsx](frontend/src/components/timeline/TimelineCompact.tsx) 仅 flex 卡片；[search/page.tsx:295-297](frontend/src/app/search/page.tsx#L295-L297) |
| 3 | 关系网不够复杂 | 前端固定 `fetchGraph(entityId, 1)` 只用 1 跳；后端单跳最多 15 节点（`_RELATED_LIMIT`）；`build_graph_from_wikidata` 明确"仅支持 depth=1，多跳留待后续"；`has_more` 与 `useGraph.loadMore` 存在但**前端从未接线**；设计规范承诺的"双击节点展开下一跳""滚动/缩放增量加载"未落地 | [search/page.tsx:99](frontend/src/app/search/page.tsx#L99)；[graph.py:78](backend/app/api/graph.py#L78)；[graph.py:431-433](backend/app/api/graph.py#L431-L433)；[useGraph.ts:55-59](frontend/src/hooks/useGraph.ts#L55-L59) |

**示例效果**：搜索"马克思"，图谱只显示 15 个左右节点、连线无任何文字，看不清"马克思→恩格斯"是合作还是影响；底部时间轴只是一排孤立的年份卡片，看不出演化脉络；想继续往下挖关系网也没有入口。

### 变更性质

**规格缺口补全（非全新需求）**。以下设计承诺均已存在于项目文档中：

- FR-5（[prd.md:200](_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L200)）："低置信度关系以虚线展示，**悬停时显示来源**"
- FR-4（[prd.md:180](_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L180)）："用户**滚动/缩放时增量加载更多**"；设计规范 4.4（[frontend-design.md:552](_bmad-output/frontend-design.md#L552)）："**双击节点 → 展开下一跳节点**（请求 API depth+1）"
- FR-8（[prd.md:240](_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L240)）："支持缩放到不同时间粒度（**年/十年/世纪**）"；FR-9：时间轴-图谱联动
- 时间轴视觉规范（[frontend-design.md:410-429](_bmad-output/frontend-design.md#L410-L429)）：带关键年份 → 事件标题的**横向时间轴条**

不推翻任何架构决策，全部为前端表现层补齐 + 后端多跳构建补齐。

---

## 2. Impact Analysis

### 2.1 Epic 影响

| Epic | 影响 | 说明 |
|:---|:---|:---|
| **Epic 2 图谱可视化与探索体验** | **主要** | 图谱边标注（Story 2.3）、时间轴可视化（Story 2.5）、关系网扩展（Story 2.1/2.2）均在本 Epic |
| **Epic 1 搜索与知识图谱构建引擎** | **主要** | 后端 `build_graph_from_wikidata` 需要实现 depth 2-3 多跳构建（Story 1.5 管道扩展） |
| **Epic 3 人物优先与数据质量系统** | 轻度 | 多跳展开后人物关系网更完整（Story 3.2 递归探索的数据源更丰富），无逻辑改动 |
| **Epic 4 匿名搜索历史** | 轻度 | 快照数据随图谱/时间轴变丰富；快照自动复用新数据，保存逻辑不变 |

### 2.2 Story 影响

- **修改 Story 2.1**（力导向图谱核心渲染）：新增边文字标签渲染（随缩放自适应显示）、边 hover 显示来源/证据。
- **修改 Story 2.2**（图谱后端 API 与分层加载）：后端实现 depth 2-3 多跳构建；前端接线 `has_more` + 深度展开（双击节点 / "加载更多"按钮）。
- **修改 Story 2.5**（演化时间轴与图谱联动）：时间轴从"卡片流"升级为"带基线/刻度/连线的可视化时间轴"，实现粒度缩放与图谱联动。
- **修改 Story 1.5**（图谱构建与 Web 内容丰富管道）：支持多跳构建（depth 1→2→3 递归拉取并合并，受每跳 ≤50 节点约束）。
- 其余 Story 不变。

### 2.3 文档冲突与更新

| 文档 | 更新内容 | 状态 |
|:---|:---|:---|
| PRD | FR-5 补"悬停边显示来源与关系标签"措辞；FR-4 补"双击/加载更多展开下一跳"落地说明；FR-8/9 补"时间轴可视化基线/刻度"措辞 | 待应用 |
| Epics | Story 2.1/2.2/2.5 AC 修订 | 待应用 |
| Architecture | 多跳构建落地决策（每跳 ≤50 节点、汇总去重、性能预算） | 待应用 |
| Frontend Design | 时间轴可视化线框更新（基线/刻度/连线）；边标签交互规范 | 待应用 |

### 2.4 技术影响

- **数据模型**：无 schema 变更（`GraphEdge` 已有 `type`/`evidence`/`source_url`，`GraphNode` 已有 `year`）。节点 `year` 字段当前**从不填充**——本次为时间轴联动提供数据时可能需要补。
- **图谱后端**：`build_graph_from_wikidata` 由单跳扩展为递归多跳（depth 2-3），需处理：跳过已访问节点防环、每跳 ≤50 节点截断、层级 relevance 衰减、缓存键已含 `depth{n}`。
- **图谱前端**：`GraphCanvas` 增加边标签（`<text>` 元素，缩放时按比例显示/隐藏避免密集重叠）与边 hover tooltip；`search/page.tsx` 把固定 `depth=1` 改为接入 `useGraph` 的 `loadMore`/双击展开。
- **时间轴前端**：`TimelineCompact` 重绘为基线 + 刻度 + 年份卡片的可视化时间轴；`handleYearChange` 由空桩改为真实的图谱节点淡化联动；新增粒度缩放（年/十年/世纪）。
- **时间轴后端**：粒度缩放可纯前端实现（按年份聚合），图谱联动需 `GraphNode.year` 有值——需评估 Wikidata 给节点补年份（`P569/570/571/577` 等时间属性）的工作量。
- **性能**：多跳后节点/边增多（1 跳 15 → 2 跳可能 30-50 → 3 跳可能 100+），需符合 NFR-1（2s 渲染 200 节点以内）与 NFR-2（P99 <500ms 缓存命中）。

---

## 3. Recommended Approach

**路径选择：Direct Adjustment（在现有计划内直接调整）**

- 不需要回滚任何已完成工作——既有 P1-P10 数据管道全部复用；
- 不需要缩小 MVP 范围——这是设计规范已承诺的规格补全；
- 无新外部依赖——前端 D3.js、vis-timeline 已在 `package.json`（[package.json](frontend/package.json)）。

**三个子提案的工作量估算**：

| 提案 | 内容 | 估算 |
|:---|:---|:---|
| V1 | 图谱边关系标注（文字标签 + hover 来源） | 1 人日 |
| V2 | 时间线可视化升级（基线/刻度/联动/粒度） | 1.5 人日 |
| V3 | 关系网扩展（后端多跳 + 前端深度展开） | 2 人日 |
| 文档 | PRD / Epics / Architecture / Frontend Design 同步 | 0.5 人日 |
| **合计** | | **约 5 人日** |

**风险评估**：

| 风险 | 等级 | 缓解 |
|:---|:---|:---|
| 边标签密集节点上文字重叠 | 中 | 缩放阈值控制：放大到一定级别才显示标签；仅显示置信度高的边 |
| 多跳后图谱超出渲染预算 | 中 | 每跳 ≤50 节点硬截断；前端力导向仍能处理 100-200 节点（NFR-1）；必要时"加载更多"按跳数渐进 |
| 多跳构建延迟增加（递归拉 Wikidata） | 中 | 缓存键已含 depth；`graph:{id}:depth2` 独立缓存；构建结果写 Neo4j 后 P99 <500ms 命中 |
| 节点无 `year` 导致时间轴联动数据缺失 | 中 | V2 联动若受阻，先做"时间轴自身可视化 + 粒度缩放"，图谱联动随 V2b 评估 |
| 时间轴重绘影响历史快照兼容 | 低 | `TimelineCompact` 已支持外部 `milestones` 快照模式（[TimelineCompact.tsx:31-36](frontend/src/components/timeline/TimelineCompact.tsx#L31-L36)），重绘保持该契约 |

**时间线影响**：不阻塞其他 Epic；V1/V2/V3 相互独立可部分并行（V3 依赖 V1 的边渲染基础设施较少，主要独立）。建议顺序 V1 → V2 → V3。

---

## 4. Detailed Change Proposals

### 4.1 代码变更提案

> **增量审阅记录（2026-08-04）**：9 个子提案经 71-agent 对抗性代码验证（每项确认问题均经第二 agent 反驳验证），8 个批准、1 个跳过（V1a）。批准项中的 blocker/major 修复已折入下方，标 [blocker] 者必须实现。

#### V1 图谱边关系标注

**V1a：边文字标签** — **⛔ 跳过（BMad 2026-08-04）**。若后续要恢复，参考验证结论：标签容器需 `pointer-events:none`（防破坏 Shift 拖拽）、密集边中点需去重（置信度过滤 + 垂直偏移）、`EDGE_LABELS` 提取到 constants.ts 共享。

**V1b：边 hover 显示来源/证据** — **✅ 批准**

- 文件：`frontend/src/components/graph/GraphCanvas.tsx`（单文件）
- [blocker] `SimLink` 接口（[GraphCanvas.tsx:47-51](frontend/src/components/graph/GraphCanvas.tsx#L47-L51)）增加 `evidence?: string`；`simLinks` 映射（[:179-185](frontend/src/components/graph/GraphCanvas.tsx#L179-L185)）补 `evidence: e.evidence`——后端已产出 evidence，只是映射时丢弃。
- [major] 每边画两条 line：视觉 line（`pointer-events:none`）+ 同端点透明 `stroke-width:10~12` 命中线（`pointer-events:stroke`），hover 绑在命中线（弱边最细 0.75px 本体几乎不可命中）。
- 复用节点 tooltip 容器，mouseenter 展示关系类型中文 + 置信度 + evidence + 来源；来源复用 SourceLink 组件（已处理空 url/畸形 url）；统一封装 `hideTooltip()`。

#### V2 时间线可视化升级

**V2a：基线 + 刻度 + 连线的可视化时间轴** — **✅ 批准**

- 文件：`frontend/src/components/timeline/TimelineCompact.tsx`
- 重绘为水平基线 + 刻度 + 里程碑卡片 + 竖线连接；**保持 flex 流式布局**，竖线/刻度锚定到卡片自身（卡片底部伪元素），**不用绝对坐标**——否则同年多事件重叠（后端只按 (year,title) 去重，[timeline_service.py:263-268](backend/app/services/timeline_service.py#L263-L268)）。
- 统一卡片 `min-h`：year/title 固定一行（truncate），描述区固定 2 行高 → 卡片底部平齐、竖线等长。
- 快照模式（externalMilestones）/实时模式/onYearChange/onLoaded 契约原样保留，两处调用方共享。

**V2b：粒度缩放（年/十年/世纪）** — **✅ 批准**

- 文件：`frontend/src/components/timeline/TimelineCompact.tsx`
- `granularity` state 放组件内部（`useState<'year'|'decade'|'century'>('year')`），search 页与 history 快照页自动同获。
- 集中定义 `formatGranule(year, granularity)` 纯函数：year→`'1970'` / decade→`'1970年代'` / century→`'20世纪'`（**`Math.floor(year/100)+1`**——2000 属 20 世纪）。
- 聚合用 `useMemo` 派生 `groups`，点击传组代表原始 year；activeIndex 用 `representativeIndex` 防跨粒度错位。
- 少数据降级：`len<3` 或跨度<20 年强制 year 档，十年/世纪按钮 disabled + tooltip；聚合后仅 1 组也禁用粗粒度。
- segmented control 放时间轴头部"N 个里程碑"旁，`aria-pressed` 选中态，复用 brand-accent 样式。

**V2c：时间轴-图谱联动（真实现）** — **✅ 批准**（含决策①：`year`+`year_end` 年段模型）

- 文件：`backend/app/api/graph.py`、`neo4j_repo.py`、`models/graph.py`、`api.ts`、`GraphCanvas.tsx`、`TimelineCompact.tsx`、`search/page.tsx`
- [决策①] **年段模型**：`GraphNode` 增加 `year_end?: number`（前端同步）；判定 `isActive = (year ?? -∞) ≤ activeYear ≤ (yearEnd ?? +∞)`，空边界开区间，无 year 节点不淡化——单 `year` 相等会把在世人物（如选 1848 时马克思）错误淡化。
- 后端补时间数据**复用内存 claims**（[graph.py:479-482](backend/app/api/graph.py#L479-L482) 已拉全量），新增纯函数 `_extract_node_year(claims)`：P569/P571/P577/P585 为锚点年，P570/P576 为结束年，**不引入 N+1**。
- [blocker] 打通 Neo4j：`upsert_entity` SET 加 `e.year = coalesce($year, e.year)`、`e.yearEnd = coalesce($yearEnd, e.yearEnd)`；`get_graph` 读回透传——否则主请求路径（缓存命中）静默失效。
- 发布时强制重建：缓存键升级（如 `graph:{qid}:depth{n}:v2`）或清 `graphBuiltAt`，避免旧缓存无 year。
- 前端 `nodeOpacity` 加 activeYear 维度，与 relevance 淡化叠加；activeYear 作为可选 prop（默认 null），history 页完全向后兼容；复用现有 opacity 原地更新 effect（[:105-111](frontend/src/components/graph/GraphCanvas.tsx#L105-L111)）满足 ≤500ms 联动。
- 一期只做**节点**淡化，不做边淡化（被淡化节点连出的边自然退后）。
- 清除筛选：再点同一里程碑 → `setActiveIndex(null)` + `onYearChange(null)`。
- 低覆盖降级：有 year 节点占比 <20% 时忽略 activeYear 不淡化（防概念类中心"功能像坏了"）。

**V2d：里程碑详情增强** — **✅ 批准**

- 文件：`frontend/src/components/timeline/TimelineCompact.tsx`（单文件）
- [blocker] 卡片从 `<button>` 重构为 `<div>`：年份/标题区触发联动、描述区独立"展开/收起"子按钮、来源 `<a>`，子元素统一 `e.stopPropagation()`——`<button>` 内嵌 `<a>`/子按钮非法且点击全触发联动。
- 来源仅在 `source_url` 非空时渲染，复用 SourceLink 组件（空 url 显示"来源未知"）。
- 空间：展开态卡片放宽宽度（w-44/48）+ flex `items-start`，收拢态保持 w-28。
- 按需显示"展开"：`useLayoutEffect` 判断 `scrollHeight > clientHeight` 才显示（后端 description 多为短文本）。
- 单一 `expandedIndex` state；`setMilestones` 时同步重置；越界守卫。

#### V3 关系网扩展

**V3a：后端多跳构建** — **✅ 批准**（含决策②：hop≥2 仅展开强关系属性）

- 文件：`backend/app/api/graph.py`、`neo4j_repo.py`、`wikidata_repo.py`、`models/graph.py`
- [blocker①] **深度感知新鲜度**：`mark_graph_built` 增加 depth 参数写 `e.graphDepth = depth`；`get_graph` WHERE 加 `AND (center.graphDepth IS NULL OR center.graphDepth >= $depth)`——否则 depth=1 构建后 depth=3 请求静默返回 1 跳。
- [blocker②] **多跳重建清理**：重建前对 visited 全部 hop 节点逐个 `delete_outgoing_relations`（或一条 Cypher `MATCH (n) WHERE n.entityId IN $ids MATCH (n)-[r]->(m) WHERE m.entityId IN $ids DELETE r`）——现有函数只删中心出边，多跳陈旧边清不掉。
- [major] **批量拉取 + 限流**：`wikidata_repo` 新增 `get_entities_by_qids(qids)`（wbgetentities `|` 连接 ≤50 ids），解析逻辑抽纯函数复用；加 `asyncio.Semaphore(8-10)`；可选实体级 Redis 缓存（`wd:{qid}`，TTL 7d）。
- [major] **get_graph 确定性聚合**：去掉 `LIMIT 200` 路径式截断，改 `WITH DISTINCT n` 收节点 + `WITH r, startNode(r), endNode(r)` 收边（构建规模有界 ≤~150 边）。
- [major] **[决策②] hop≥2 白名单收敛**：仅展开 `_STRONG_RELATION_PROPS`（P800/P1416/P463/P910/P127/P355/P1830/P1327/P69/P108/P102），丢弃 P31/P279/P19/P20/P26/P937/P101；`_extract_related_qids` 增加 props 参数——防 hop-2/3 堆满分类噪音。
- [major] **Web 丰富判定与深度解耦**：`_should_enrich` 只统计 hop-1 子图，避免多跳后丰富通道静默关闭。
- [minor] 删除死代码 `_STRONG_RELEVANCE_THRESHOLD=0.6`；hop-1 保留 prop 制 relevance（强 0.7/分类 0.2），hop≥2 跳衰减（0.5/0.3）写库落值；`GraphEdge`/`GraphNode` 加可选 `hop` 字段（与 V3b 共用）。
- 新增 `test_graph_multi_hop.py`：防环、每跳截断、relevance 衰减断言、graphDepth 新鲜度、重建清陈旧边；**保证现有 depth=1 测试行为不变**。

**V3b：前端深度展开接线** — **✅ 批准**（含决策③："双击 = 切换中心"，非深度叠加）

- 文件：`frontend/src/app/search/page.tsx`、`GraphCanvas.tsx`
- [关键改写] 原方案"加载更多 → depth+1 叠加"在现行后端下**不成立**：`get_graph` 的 `[r*1..depth]` 可变长路径已含全部跨跳，depth 1→2 不改变节点集合；`has_more` 是 LIMIT-200 截断标志非 depth 语义；`useGraph.loadMore` 全量重 fetch + 替换。→ 改为**双击节点 = 切换图谱中心**。
- [决策③] GraphCanvas 新增 prop `onExpandNode`；节点 click 按 `event.detail` 分支（detail 1 选中 / ≥2 展开）；page 端复用现有 `handleExploreGraph`（面包屑自动记录、零新增状态），与 GraphNodePanel"展开该节点的图谱"同路径。
- [major] 双击与 d3 zoom 冲突：`zoom.on("dblclick.zoom", null)` 或节点 dblclick `stopPropagation()`；命中距离守卫（< r+6）；桌面 d3 v7 实测。
- 双击时序竞态：click 里 `if (event.detail >= 2) return` 防"先选中再展开"闪动。
- **不迁移** page 状态到 `useGraph`（约 80 行耦合逻辑，本轮无收益）；useGraph 保留为增量后端预留实现并标注 dead-code。
- 可选：控制区加"展开"按钮取选中节点（非中心时可用）。

**V3c：多跳后的历史快照兼容** — **✅ 批准**

- 文件：`frontend/src/app/search/page.tsx`、`history.py`、`history_service.py`
- [范围澄清] 现状**不存在"多跳累积图谱"**（前端恒 depth=1、explore 不保存快照、后端无多跳）。V3c 范围改为"深度1大图谱快照 round-trip 验证 + 防御性上限 + 元数据"。多跳会话回放是新功能（会话级快照：breadcrumb 路径 + 跨 hop 合并 + 保存 depth），显式立项。
- 后端防御上限：`save_snapshot` 入口限 `graph.nodes/edges ≤200`、总 payload ≤1MB，超限 400/截断；校验 edge 端点均在 nodes 内（丢弃悬空边）。
- 快照 payload 补 `depth`/`has_more` 元数据，详情页据此展示跳数与截断标记；旧快照 `?.` 容错。

### 4.2 文档变更提案

**PRD 修订：**

**FR-5** 补"悬停任一条关系边显示关系类型/置信度/证据/来源"（注：V1a 边常驻文字标签已跳过，语义解释由悬停承担）。

**FR-4** 补"双击节点切换图谱中心展开其关联（复用现有中心切换 + 面包屑）"。

**FR-8** 补"时间轴以带时间基线/刻度的可视化形式呈现，支持年/十年/世纪粒度缩放"。

**FR-9** 补"时间轴联动落地：选中年份时图谱中非活跃节点淡化（年段判定，year+year_end）"。

**Epics 修订：**

- **Story 2.1** 新增 AC：`And 悬停任一边显示关系类型/置信度/证据/来源`。
- **Story 2.2** 新增 AC：`And 后端支持 depth 2-3 多跳构建，每跳 ≤50 节点，已访问节点去重防环，hop≥2 仅展开强关系属性`；`And 前端双击节点切换中心探索（最多 3 跳）`。
- **Story 2.5** 新增 AC：`And 时间轴以带基线/刻度的可视化形式呈现`；`And 支持年/十年/世纪粒度缩放`；`And 选中年份时图谱联动淡化非活跃节点（年段判定）`。

**Architecture 修订：**

- ADR 记录"多跳构建落地"：depth 1→3 递归拉取合并，每跳 ≤50 节点，hop≥2 白名单收敛为强关系属性，relevance 随跳数衰减，graphDepth 深度感知新鲜度，批量拉取 + Semaphore 限流。
- ADR 记录"时间轴-图谱联动数据模型"：`GraphNode` 增加 `year`/`year_end` 年段字段，`upsert_entity`/`get_graph` 打通，缓存键升级强制重建。

**Frontend Design 修订：**

- 时间轴线框更新为"基线 + 刻度 + 年份卡片"可视化形态（对齐 FR-8 承诺）。
- 图谱交互：双击节点 = 切换中心（对齐设计规范 4.4"双击节点 → 展开下一跳"的意图，实现为切中心）。

---

## 5. Implementation Handoff

### 变更范围分类：**Moderate**（Epic 2 多 Story 调整，需 PO/DEV 协同）

### 交接对象与职责

| 角色 | 职责 |
|:---|:---|
| **PO / BMad** | 已批准（2026-08-04）；确认 PRD/Epics/Architecture/Frontend Design 文档修订落地 |
| **Developer agent** | 按 V1b → V2 → V3 顺序实现（V1a 已跳过）；补后端单测（多跳构建去重/截断/relevance 衰减、节点 year 提取、graphDepth 新鲜度）；前端类型检查与 lint |
| **Architect（如需）** | 复核多跳构建的每跳节点上限与 relevance 衰减策略、V2c 年段模型（year+year_end）设计 |

### 实现顺序与依赖

```
V1b 边 hover 来源/证据（前端，独立，最先交付）
   ↓
V2 时间线可视化（V2a 基线/刻度 → V2b 粒度 → V2d 详情 可先行；
   V2c 图谱联动依赖后端补节点 year，后端先行）
   ↓
V3 关系网扩展（V3a 后端多跳 → V3b 前端双击切中心；V3c 快照防御上限）
   ↓
文档同步（PRD / Epics / Architecture / Frontend Design）
```

- V1b 完全独立，可最先交付；
- V2 内部：V2a/V2b/V2d 纯前端可先行；V2c 需后端 `_extract_node_year` + Neo4j 打通 + 缓存重建，独立成步；
- V3 依赖最大：V3a 后端多跳（含批量拉取/限流/确定性聚合/白名单收敛）是 V3b 双击切中心的数据前提；V3c 只需后端防御上限，可独立。

### 成功标准

- [ ] 搜索"马克思"图谱：悬停边显示关系类型/置信度/证据/来源（V1b；V1a 边文字标签已跳过）
- [ ] 时间轴：带基线/刻度的可视化形态，描述可展开，支持年/十年/世纪粒度缩放（V2a/b/d）
- [ ] 时间轴选中年份时图谱联动淡化非活跃节点（V2c 年段判定，year+year_end）
- [ ] 图谱双击节点切换中心探索（V3b），后端支持 depth 2-3 多跳构建（V3a）
- [ ] 后端 `pytest` 通过（新增多跳去重/截断/relevance 衰减、节点 year 提取、graphDepth 新鲜度单测；现有 depth=1 测试行为不变）
- [ ] 浏览器端全流程验证（搜索 → 图谱 → 悬停边 → 时间轴联动 → 双击展开 → 快照保存数据完整性）
- [ ] PRD / Epics / Architecture / Frontend Design 文档修订已应用

---

## 附：本次决策记录

| 决策点 | 结论 |
|:---|:---|
| 变更性质 | 规格缺口补全（FR-4/5/8/9 + 设计规范均已承诺），非全新需求 |
| 增量审阅 | 9 子提案经 71-agent 对抗性验证，8 批准 / 1 跳过（V1a 边文字标签）；确认问题均折入提案 |
| 决策① 联动时间模型 | **年段模型**：`year`+`year_end` 跨度判定（空边界开区间），非单 year 相等——防选事件年时错误淡化在世人物 |
| 决策② 多跳白名单 | **hop≥2 仅展开强关系属性**（P800/P1416/P463/P910/P127/P355/P1830/P1327/P69/P108/P102），丢弃分类/地理/家庭弱属性——多跳"大而干净" |
| 决策③ 展开交互 | **双击 = 切换中心**（复用 handleExploreGraph + 面包屑），非 depth 叠加——后端 `[r*1..depth]` 可变长路径使 depth 1→2 不改变节点集合 |
| 关系标注方案 | V1b 边 hover 来源/证据（批准）；V1a 边文字标签（跳过，后续可恢复） |
| 时间轴方案 | 基线 + 刻度 + 年份卡片可视化（flex 流式防同年重叠），粒度缩放纯前端聚合 |
| 关系网扩展 | 后端递归多跳（depth 1→3）+ 批量拉取/限流 + 确定性聚合 + graphDepth 新鲜度；前端双击切中心 |
| 快照兼容 | 现状无多跳累积；V3c 范围 = 深度1大图谱 round-trip + 防御上限（nodes/edges ≤200、payload ≤1MB）+ depth/has_more 元数据 |
