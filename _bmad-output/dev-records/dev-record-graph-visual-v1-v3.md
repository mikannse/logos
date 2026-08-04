# Dev Agent Record — 图谱关系标注 · 时间线可视化 · 关系网扩展（V1–V3）

- **故事范围**：Sprint Change Proposal 2026-08-04-graph-visual（BMad 三点反馈：实体间未标明关系 / 时间线不直观 / 关系网不够复杂）
- **实施日期**：2026-08-04
- **提案审阅**：9 子提案经 71-agent 对抗性验证，8 批准 / 1 跳过（V1a 边文字标签）
- **实施顺序**：V1b → V2 → V3（后端先行，前端随后）
- **状态**：implemented（待人工评审 / 浏览器端验证）

---

## 1. 完成摘要

### V1b 图谱边 hover 显示来源与证据 ✅

**文件**：`frontend/src/components/graph/GraphCanvas.tsx`、`frontend/src/lib/constants.ts`、`GraphLegend.tsx`、`GraphNodePanel.tsx`

- **打通 evidence 数据链**：`SimLink` 接口增加 `evidence?: string`，`simLinks` 映射补 `evidence: e.evidence`——后端早已产出 evidence（如"合作者：恩格斯"），此前映射时丢弃。
- **宽透明命中线**：每条边画两条 line——视觉线（`pointer-events:none`）+ 同端点透明 `stroke-width:11`、`pointer-events:stroke` 命中线。弱边最细 0.75px 本体几乎不可命中，命中线让 hover 真正可用。
- **边 hover tooltip**：复用节点 tooltip 容器，展示关系类型中文（`edgeLabel()`）+ 置信度 + evidence + 来源链接（SourceLink 组件，空 url 显示"来源未知"）。
- **EDGE_LABELS 单一数据源**：中文映射提取到 `constants.ts`，GraphCanvas/GraphLegend/GraphNodePanel 共用，杜绝三处漂移。

### V2a 时间轴可视化升级（基线 + 刻度 + 年份卡片）✅

**文件**：`frontend/src/components/timeline/TimelineCompact.tsx`

- 从孤立卡片流升级为：竖线 + 刻度点 + 卡片 + 底部渐变基线（flex 流式布局）。
- **防同年重叠（关键约束）**：坚持 flex 流式、竖线锚定卡片自身，不用绝对坐标——后端只按 `(year,title)` 去重，同年多事件必须并排。
- 快照模式（externalMilestones）/ 实时模式 / onYearChange / onLoaded 契约原样保留，search 页与 history 快照页共享。

### V2b 时间轴粒度缩放（年/十年/世纪）✅

**文件**：`TimelineCompact.tsx`

- `granularity` state 放组件内部（search 页与 history 快照页自动同获）。
- `formatGranule` 纯函数：year→`'1970'` / decade→`'1970年代'` / century→`'20世纪'`（**世纪边界 `Math.floor(year/100)+1`**——2000 属 20 世纪）。
- `useMemo` 聚合派生 groups（代表里程碑 = 组内最早年份成员 + 组内数量 ×N）。
- **少数据降级**：`len<3` 或跨度<20/100 年时禁用对应粒度档；聚合组数 ≤1 也禁用。

### V2c 时间轴-图谱联动（真实现）✅

**文件**：`backend/app/api/graph.py`、`neo4j_repo.py`、`models/graph.py`、`frontend/src/app/search/page.tsx`、`GraphCanvas.tsx`、`TimelineCompact.tsx`

- **年段数据模型（决策①）**：`GraphNode` 增加 `year_end`；判定 `isActive = (year ?? -∞) ≤ activeYear ≤ (yearEnd ?? +∞)`——单 `year` 相等会把在世人物（选 1848 时马克思）错误淡化。
- **后端补时间数据（复用内存 claims，零额外 HTTP）**：新增 `_extract_node_year(claims)` 纯函数，锚点年 P569/571/577/585、结束年 P570/576/8556；`build_graph_from_wikidata` 已把 related 实体全量 claims 拉到内存，直接解析。
- **打通 Neo4j 缓存路径（blocker）**：`upsert_entity` SET 加 `e.year = coalesce($year, e.year)`、`e.yearEnd`；`get_graph` 读回 year/yearEnd 透传——否则主请求路径（缓存命中）静默失效。
- **缓存键升级 v2**：`graph:{qid}:depth{n}:v2`，发布时间一次性失效旧 Redis 缓存（无年段数据）。
- **前端年段淡化**：`nodeOpacity` 叠加 activeYear 维度，复用现有 opacity 原地更新 effect——activeYear 变化只改属性不改布局，满足 ≤500ms 联动。
- **清除筛选**：再点同一里程碑 → `setActiveIndex(null)` + `onYearChange(null)` 回全时段；选中态显示"已筛选 XXXX · 点击可清除"。

### V2d 里程碑详情增强（展开/收起 + 来源链接）✅

**文件**：`TimelineCompact.tsx`

- **卡片结构重构（blocker）**：`<button>` 重构为 `<div role="button">`，整卡点击=年份联动；内部展开按钮/来源链接 `stopPropagation()` 隔离——`<button>` 内嵌 `<a>`/子按钮非法。
- 来源仅 `source_url` 非空时渲染，复用 SourceLink 组件（空 url 显示"来源未知"）。
- 单一 `expandedIndex` state，数据切换时重置。

### V3a 后端多跳构建 ✅

**文件**：`backend/app/api/graph.py`、`neo4j_repo.py`、`wikidata_repo.py`、`models/graph.py`

- **递归 depth 1→3**：frontier 逐跳收集候选 → 批量拉取 → 类型优先级排序截断 → 已访问集合防环。
- **hop≥2 白名单收敛（决策②）**：仅展开 `_STRONG_RELATION_PROPS`（10 个强属性），丢弃 P31/P279 分类与 P19/P20/P26/P937/P101 地理/家庭弱属性——防 hop-2/3 堆满分类噪音。
- **批量拉取 + 限流**：`get_entities_by_qids()`（wbgetentities `|` 连接 ≤50 ids，解析逻辑抽 `_parse_entity_detail` 复用）；`asyncio.Semaphore(10)` 惰性创建实例属性（修复 M2：类属性绑定事件循环会跨 loop 抛错）。
- **确定性聚合（替代 LIMIT 200 路径截断）**：`get_graph` 拆节点/边两条 `DISTINCT` 查询——旧路径式 LIMIT 在 depth≥2 时返回任意子集。
- **深度感知新鲜度（blocker①）**：`mark_graph_built` 写 `graphDepth=depth`；`get_graph` WHERE 加 `(graphDepth IS NULL OR graphDepth >= depth)`——否则 depth=1 构建后 depth=3 请求静默返回 1 跳。
- **多跳陈旧边清理（blocker②，B1 修复）**：每次为非中心源节点写边前先 `delete_outgoing_relations`——前次更深度构建写入的 hopN→hopN+1 内部边被清干净。
- **Web 丰富判定与深度解耦**：`_should_enrich` 只统计 hop-1 子图（`n.get("hop",1)==1`），避免多跳后丰富通道静默关闭。
- **死代码清理**：删除从未使用的 `_STRONG_RELEVANCE_THRESHOLD=0.6`；hop-1 保留 prop 制 relevance（强 0.7/分类 0.2），hop≥2 乘衰减（0.5/0.3）写库落值。
- **hop 字段**：`GraphEdge`/`GraphNode` 加可选 `hop`，`get_graph` 读回透传，前端同步。

### V3b 前端深度展开（双击 = 切换中心）✅

**文件**：`frontend/src/components/graph/GraphCanvas.tsx`、`frontend/src/app/search/page.tsx`

- **核心机制改写（决策③）**：原"加载更多 → depth+1 叠加"在现行后端不成立（`[r*1..depth]` 可变长路径使 depth 1→2 不改变节点集合）→ 改为**双击节点 = 切换图谱中心**（复用 `handleExploreGraph` + 面包屑，零新增状态）。
- **dblclick 竞态**：click 里 `if (event.detail >= 2) return` 防"先选中再展开"闪动；禁用 `dblclick.zoom`（否则双击同时缩放+切中心）；节点 dblclick `stopPropagation` 双保险。
- 不迁移 page 状态到 `useGraph`（约 80 行耦合，本轮无收益）；useGraph 保留为增量后端预留实现。

### V3c 快照防御上限 ✅

**文件**：`backend/app/api/history.py`、`tests/test_services/test_history_service.py`

- 入口校验：`graph.nodes/edges ≤200`、payload ≤1MB（超限 400）。
- **悬空边过滤**：`_validate_snapshot_graph` 校验边端点均在节点集，丢弃悬空边。
- 快照 payload 补 `depth`/`has_more` 元数据（前端 fetchGraph 已返回）。

---

## 2. 测试

| 套件 | 结果 |
|:---|:---|
| 后端全量 `pytest` | **184 passed**（基线 161 + 新增 23），1 环境性失败（`test_pinned_transport_socktype_zero_matches`，沙箱 socket 限制，非回归） |
| 新增 `test_graph_multi_hop.py` | 20 passed：多跳展开/防环/hop≥2 白名单/relevance 衰减/深度新鲜度/陈旧边清理/批量拉取/年段提取/节点年段透传 |
| 新增快照校验测试 | 3 passed：悬空边过滤/节点上限/边上限 |
| 前端 `tsc --noEmit` | 通过 |
| 前端 `next build` | 成功 |

## 3. 已知限制与后续

1. **M1 时间轴年份语义**：里程碑年份可来自限定符（P585/P580）或作品自身条目（P577），而图谱节点 `year` 仅来自实体自身 P569/571/577/585 主快照——点击限定符型里程碑时可能无节点精确匹配。现有 V2c 低覆盖降级（有 year 节点占比 <20% 时忽略淡化）兜底；完整对齐需把里程碑年份映射到其 target 节点，列为后续迭代。
2. **浏览器端验证依赖真实环境**：Tavily Key（Web 丰富）+ Neo4j + Redis 需本机运行；建议用"马克思"做全流程冒烟（搜索 → 悬停边 → 时间轴联动 → 双击展开 → 快照）。
3. **`delete_subgraph_edges` 现为未使用工具方法**（生产代码改用逐节点清理），保留供后续复杂清理场景。

## 4. 涉及文件

```
backend/app/api/graph.py                 # 多跳构建、_extract_node_year、_should_enrich 解耦、缓存键 v2
backend/app/api/history.py               # V3c 快照防御上限 + 悬空边校验
backend/app/models/graph.py              # GraphNode.year_end / GraphEdge.hop
backend/app/repositories/neo4j_repo.py   # 确定性聚合、graphDepth、year/yearEnd 读写、delete_subgraph_edges
backend/app/repositories/wikidata_repo.py# get_entities_by_qids、_parse_entity_detail 抽取、Semaphore
backend/tests/test_services/test_graph_multi_hop.py   # 新增 20 测试
backend/tests/test_services/test_history_service.py   # 新增 3 快照校验测试
frontend/src/components/graph/GraphCanvas.tsx         # V1b 命中线/边 hover、V2c 年段淡化、V3b 双击
frontend/src/components/graph/GraphLegend.tsx         # EDGE_LABELS 单一数据源
frontend/src/components/graph/GraphNodePanel.tsx      # 关系类型中文标签
frontend/src/components/timeline/TimelineCompact.tsx  # V2a/b/d 重写
frontend/src/app/search/page.tsx                      # activeYear/onExpandNode 接线
frontend/src/lib/api.ts                               # year_end/hop 字段
frontend/src/lib/constants.ts                         # EDGE_LABELS + edgeLabel()
```
