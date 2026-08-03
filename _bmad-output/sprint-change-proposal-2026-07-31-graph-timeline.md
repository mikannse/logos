# Sprint Change Proposal — 图谱相关内容性与 Web 数据管道丰富

- **日期**：2026-07-31
- **触发人**：BMad
- **状态**：**已批准（2026-07-31）** — 文档修订已应用，代码按 P1→P6 顺序交接 Developer agent 实施
- **变更等级**：Moderate（Epic 1/2 多 Story 调整，需 PO/DEV 协同）

---

## 1. Issue Summary

### 触发原因

BMad 在产品体验反馈中提出两个问题：

> **问题 1**：搜索的内容以及显示在图谱上的内容我不是很满意，很多名词跟我搜索的关联性不大，需要突出重要内容。
>
> **问题 2**：演化时间轴也不够丰富，比如"苹果公司"这个结果。

### 根因分析（代码级证据）

两个问题共享同一个根因：**Web Search + LLM 数据管道对正常搜索流程完全不可达**。

| # | 根因 | 代码证据 |
|:---|:---|:---|
| 1 | Web Search 管道只在"零结果冷启动"触发（`?build=true`），而前端**从不传 `build=true`** | [nouns.py:46](backend/app/api/nouns.py#L46) `start_build` 为死代码；`frontend/src/lib/api.ts` 的 `searchNouns` 不传 build 参数 |
| 2 | 正常搜索的图谱完全来自 Wikidata 固定属性白名单，含 P31/P279 纯分类节点，无相关性排序 | [graph.py:16](backend/app/api/graph.py#L16) `_RELATION_PROPS` 含 P31/P279；`_RELATED_LIMIT=15` 按固定顺序取前 15 |
| 3 | LLM 实体提取无焦点锚定、无相关性打分，`llm_*` ID 与 Wikidata QID 两套体系并存 | [extractor.py:15-21](backend/app/ai/extractor.py#L15-L21)；[graph_service.py:114-134](backend/app/services/graph_service.py#L114-L134) |
| 4 | 时间轴只依赖 Wikidata 带时间声明（P569/570/571/576/793/166/69/108/551），稀疏实体时间轴为空 | [timeline_service.py](backend/app/services/timeline_service.py)；`neo4j_repo.get_timeline`（[neo4j_repo.py:139](backend/app/repositories/neo4j_repo.py#L139)）与 `summarizer.extract_key_facts`（[summarizer.py:44](backend/app/ai/summarizer.py#L44)）均为 TODO |

**示例效果**：搜索"苹果公司"，当前图谱会出现"公司 / 企业 / 组织"等无关分类节点（P31/P279 目标），而真正相关的 iPhone / 史蒂夫·乔布斯 等因无 Web 丰富而缺失；时间轴因 Wikidata 带时间声明稀疏而几乎为空。

### 变更性质

不推翻既有架构决策，而是把已经存在的 **AI 数据管道（ADR-001、Story 1.5）从"零结果专用"扩展为"所有搜索的内容丰富通道"**，并补齐相关性过滤/排序与时间轴 AI 兜底。属**技术缺口补全 + 产品体验增强**，非需求误解、非战略转向。

---

## 2. Impact Analysis

### 2.1 Epic 影响

| Epic | 影响 | 说明 |
|:---|:---|:---|
| **Epic 1 搜索与知识图谱构建引擎** | 主要 | 构建管道扩展为"所有搜索的内容丰富通道"（Wikidata + Web Search + LLM 合并）；新增相关性过滤与 ID 统一解析 |
| **Epic 2 图谱可视化与探索体验** | 主要 | 图谱数据质量提升（2.1/2.2 数据侧）；时间轴 AI 兜底丰富（2.5） |
| **Epic 3 人物优先与数据质量系统** | 轻度 | `relevance` 与 `confidence` 语义区分；相关性过滤提升整体数据质量 |
| **Epic 4 匿名搜索历史** | 无 | 快照自动复用新数据（保存逻辑不变，仅数据来源更丰富） |

### 2.2 Story 影响

- **修改 Story 1.5**：冷启动构建扩展为"图谱构建与 Web 内容丰富管道"，新增相关性过滤、ID 统一解析、正常搜索触发丰富。
- **修改 Story 2.5**：演化时间轴新增 AI 兜底丰富（Wikidata <5 里程碑时 Web Search + LLM 提取合并）。
- **新增（可选，Phase 2）Story 2.6**：SSE 增量图谱丰富前端接线（本次不做，架构已预留）。
- 其余 Story 不变。

### 2.3 文档冲突与更新

| 文档 | 更新内容 | 状态 |
|:---|:---|:---|
| PRD | FR-3（冷启动→所有搜索构建）、FR-8（时间轴来源含 AI）、FR-10（里程碑提取含 Web 数据源） | 待应用（见 §4.2） |
| Epics | Story 1.5 / 2.5 AC 修订；FR Coverage 表无新增 FR，仅措辞扩展 | 待应用（见 §4.2） |
| Architecture | ADR-001 补充"MVP 落地同步合并、SSE 增量列 Phase 2"；数据模型节点/边增加 `relevance` 字段 | 待应用（见 §4.2） |
| Frontend Design | 里程碑来源展示（可选，本迭代不做）；`relevance` 字段非破坏性类型扩展 | 部分 |

### 2.4 技术影响

- **数据模型**：`GraphNode` / `GraphEdge` 增加 `relevance`（相关度）字段；Neo4j 节点/边属性持久化。
- **AI 管道**：`ExtractedEntity` 增加 `relevance`；`extract_from_text` 增加 `focus_entity` 锚定；`Summarizer` 新增 `extract_milestones` 里程碑结构化提取。
- **图谱构建**：LLM 实体按 `relevance>=0.5` 过滤；`llm_*` ID 优先解析为 Wikidata QID；P31/P279 分类节点标 `type:category` + `relevance:0.2`；图谱按类型优先级排序截断。
- **触发策略**：正常搜索解析出实体后，图谱基础强相关节点 <6 时触发 Web Search 丰富合并（同步，缓存 1h）。
- **时间轴**：Wikidata 里程碑 <5 时 Web Search + LLM 提取兜底合并、去重、补描述与来源。
- **成本**：符合 NFR-6 分层检索——Web Search + LLM 仅在"必要"时调用（图谱强相关节点 <6 / 时间轴 <5）。

---

## 3. Recommended Approach

**路径选择：Direct Adjustment（在现有计划内直接调整）**

- 不需要回滚任何已完成工作；
- 不需要缩小 MVP 范围——这是数据质量增强，非范围削减；
- 复用现有 AI 管道组件（web_search / extractor / summarizer），无新依赖。

**工作量估算**：

| 提案 | 内容 | 估算 |
|:---|:---|:---|
| P1 | 数据模型 `relevance` 字段（模型 + Neo4j + 前端类型） | 0.5 人日 |
| P2 | 提取器相关性打分 + 焦点锚定 | 0.5 人日 |
| P3 | 图谱构建相关性过滤 + ID 统一解析 | 1 人日 |
| P4 | Wikidata 去噪 + 类型优先级排序（方案 B） | 0.5 人日 |
| P5 | 正常搜索触发 Web 丰富（同步合并） | 1 人日 |
| P6 | 时间轴 AI 兜底丰富 | 1 人日 |
| 文档 | PRD / Epics / Architecture 同步 | 0.5 人日 |
| **合计** | | **约 5 人日** |

**风险评估**：

| 风险 | 等级 | 缓解 |
|:---|:---|:---|
| 首次图谱请求延迟增加（同步合并 +3-10s） | 中 | 仅"强相关节点 <6"时触发；结果缓存 1h；SSE 增量列 Phase 2 |
| LLM 成本上升 | 中 | 分层触发（图谱 <6 / 时间轴 <5 才调用）；LLM 提取结果缓存 |
| `llm_*` → QID 解析不准产生错配 | 低 | 仅 label 精确匹配才解析；无法解析保留 `llm_*` 前缀并标低 relevance |
| 概念类实体被 P31/P279 去噪误伤 | 低 | 方案 B 不剔除分类节点，仅降级为低 relevance 类别节点 |
| 时间轴 AI 里程碑与 Wikidata 冲突 | 低 | `(year,title)` 去重，Wikidata 优先级更高 |

**时间线影响**：不阻塞当前 Epic 4（匿名搜索历史）收尾；作为下一轮开发增量，P1→P2→P3→P4→P5→P6 顺序推进，P5 依赖 P2/P3/P4，P6 独立可并行。

---

## 4. Detailed Change Proposals

以下 6 条代码提案已经 BMad 在增量模式下逐条批准（`[a]`）。

### 4.1 代码变更提案（已批准）

**P1 数据模型：节点/边增加 `relevance` 字段**
- 文件：`backend/app/models/graph.py`、`backend/app/repositories/neo4j_repo.py`、`backend/app/api/graph.py`、`frontend/src/lib/api.ts`
- `GraphNode` / `GraphEdge` 增加 `relevance: float = Field(default=0.0, ge=0.0, le=1.0, description="与中心实体的相关度（≠confidence）")`；
- Neo4j `upsert_entity`/`upsert_relation` 读写 `relevance` 属性；
- 前端 `GraphNode`/`GraphEdge` 类型加 `relevance?: number`（非破坏性）。
- 理由：`confidence`（数据可靠度）与 `relevance`（相关度）语义分离，后续 P2-P5 全部依赖该字段。

**P2 提取器：相关性打分 + 焦点锚定**
- 文件：`backend/app/ai/extractor.py`
- `ExtractedEntity` 增加 `relevance: float`（核心相关 >0.7，弱相关 0.3-0.5，无关不提取）；
- `extract_from_text(text, focus_entity=None)` 增加焦点参数，system prompt 追加"以 `{focus_entity}` 为核心，只提取直接关联实体"。
- 理由：过滤无关内容的第一道闸。

**P3 图谱构建：相关性过滤 + `llm_*` ID 统一解析**
- 文件：`backend/app/services/graph_service.py`
- LLM 提取实体按 `relevance >= 0.5` 过滤；
- 新增 `_resolve_qid(name)`：Wikidata `wbsearchentities` label 精确命中 → QID，否则保留 `llm_*`；
- `upsert_entity`/`upsert_relation` 使用解析后的 ID 与 `relevance`。
- 理由：消除无关实体 + 消除两套 ID 体系造成的重复节点。

**P4 Wikidata 去噪 + 类型优先级排序（方案 B）**
- 文件：`backend/app/api/graph.py`
- 强关联属性白名单收敛为 `["P800","P1416","P106","P463","P910","P127","P355","P1830"]`；
- P31/P279 分类节点保留但标 `type:"category"` + `relevance:0.2`；
- 按类型优先级 `person > event > technology > organization > entity > category` 排序后截断 `_RELATED_LIMIT`。
- 理由：不误伤概念类实体的语义上游，同时让"苹果公司"图谱不再被"公司/企业"淹没。

**P5 正常搜索触发 Web 内容丰富（同步合并）**
- 文件：`backend/app/api/graph.py`（`build_graph_from_wikidata`）
- 基础图谱强相关节点（`relevance>=0.6`，即 person/event/technology/organization）<6 时：
  `web_search.search_and_extract(中心名)` → `extractor.extract_from_text(summary, focus_entity=中心名)` → 按 P2/P3 过滤 + ID 解析合并 → 缓存 1h；
- 否则仅 Wikidata 基础图谱（省成本，NFR-6）。
- 决策记录：本迭代采用**同步合并**（零前端改动）；SSE 增量推送列 Phase 2（架构 ADR-001 已预留）。

**P6 时间轴 AI 丰富（兜底合并）**
- 文件：`backend/app/ai/summarizer.py`、`backend/app/services/timeline_service.py`、`backend/app/repositories/neo4j_repo.py`
- `Summarizer.extract_milestones(focus_entity, text)`：结构化提取带年份里程碑（`ExtractedMilestone{year,title≤20字,description≤40字}`），替换 TODO 的 `extract_key_facts`；
- `TimelineService.get_timeline`：Wikidata 里程碑 <5 时 Web Search + 里程碑提取兜底，`(year,title)` 去重、Wikidata 优先、补描述与来源、按年份排序、封顶 10；
- `neo4j_repo.get_timeline`：保持返回空，补注释说明"时间轴走 Redis 缓存"。
- 理由：苹果公司将获得"1976 成立 → 1984 Macintosh → 2001 iPod → 2007 iPhone → 2011 乔布斯逝世…"真实里程碑。

### 4.2 文档变更提案（✅ 已应用 2026-07-31）

**PRD 修订：**

**FR-3**（[prd.md:152](backend/../_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L152)）
> OLD：`[系统] 在用户搜索一个尚未被索引的名词时 [条件：首次搜索]，自动从公开数据源构建该名词的知识图谱并缓存在数据库中。`
> NEW：`[系统] 在 [条件：用户搜索并解析出实体时]，自动从公开数据源（Wikidata + AI Web Search）构建/丰富该实体的知识图谱并缓存在数据库中；图谱内容按与中心实体的相关度过滤与排序。`

**FR-8**（[prd.md:230](backend/../_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L230)）
> OLD：`[系统] 可以 [能力：时序呈现] 以可交互时间轴形式展示名词的演化关键里程碑。`
> NEW：`[系统] 可以 [能力：时序呈现] 以可交互时间轴形式展示名词的演化关键里程碑；里程碑来源包括 Wikidata 结构化声明与 AI Web Search 提取（Wikidata 数据稀疏时兜底）。`

**FR-10**（[prd.md:254](backend/../_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L254)）
> OLD：`[系统] 可以 [能力：自动摘要] 从概念的相关事件中自动提取 5-10 个关键里程碑节点，按时间排序展现。`
> NEW：`[系统] 可以 [能力：自动摘要] 从概念的相关事件中自动提取 5-10 个关键里程碑节点，按时间排序展现；每个里程碑附简要说明与来源链接（AI 提取来源标注置信度）。`

**Epics 修订：**

**Story 1.5 冷启动图谱构建与 AI 数据管道** → 标题与 AC 扩展为"图谱构建与 Web 内容丰富管道"：
> 新增 AC：`And 用户搜索解析出实体且基础图谱强相关节点 <6 时，系统通过 AI Web Search + LLM 提取丰富图谱，实体按与中心的相关度（relevance ≥0.5）过滤，名称优先解析为 Wikidata QID`
> 新增 AC：`And Wikidata 纯分类节点（P31/P279 目标）标为低相关度类别节点，不占据图谱主展示位`

**Story 2.5 演化时间轴与图谱联动** → 新增 AC：
> `And Wikidata 里程碑少于 5 个时，系统通过 AI Web Search + LLM 提取里程碑兜底合并，去重并按年份排序`
> `And 每个里程碑附简要说明与来源链接（AI 提取标注置信度）`

**Architecture 修订：**
- **ADR-001 补充**：图谱内容丰富 MVP 落地为**同步合并**（首查构建合并后缓存）；SSE 增量推送列 Phase 2（前端接线）。
- **数据模型**：`GraphNode`/`GraphEdge` 增加 `relevance` 字段，语义为"与中心实体的相关度"，区别于 `confidence`（数据可靠度）。

---

## 5. Implementation Handoff

### 变更范围分类：**Moderate**（Epic 1/2 多 Story 调整，需 PO/DEV 协同）

### 交接对象与职责

| 角色 | 职责 |
|:---|:---|
| **PO / BMad** | 批准本提案；确认 PRD/Epics/Architecture 文档修订落地 |
| **Developer agent** | 按 P1 → P2 → P3 → P4 → P5 → P6 顺序实现；补后端单测（extractor relevance、relevance 过滤、milestone 提取、时间轴合并） |
| **Architect（如需）** | 复核 ADR-001 同步合并 vs SSE 的取舍记录与 `relevance` 字段设计 |

### 实现顺序与依赖

```
P1 数据模型 relevance（先行，P2-P6 全部依赖）
   ↓
P2 提取器相关性打分 + 焦点锚定 ─┐
P3 图谱构建过滤 + ID 统一解析 ──┼─ P5 正常搜索触发丰富（依赖 P2/P3/P4）
P4 Wikidata 去噪 + 排序 ────────┘
P6 时间轴 AI 兜底（独立，可与 P2-P5 并行）
   ↓
文档同步（PRD / Epics / Architecture）
```

### 成功标准

- [x] 搜索"苹果公司"图谱：核心为 iPhone / 史蒂夫·乔布斯 / 蒂姆·库克 等强相关节点，不再被"公司/企业"分类节点淹没（P1-P5）
- [x] LLM 提取实体按 `relevance>=0.5` 过滤，`llm_*` 与 Wikidata QID 合并去重（P2/P3）
- [x] 时间轴：搜索"苹果公司"返回 ≥5 个带描述与来源的里程碑（P6）
- [x] 缓存策略生效：首查构建后，重复查询 <500ms 命中缓存（P5/P6）
- [x] 后端 `pytest` 通过（新增 relevance 过滤、里程碑提取、时间轴合并单测）
- [x] 浏览器端全流程验证（搜索 → 图谱 → 时间轴 → 快照保存数据完整性）
- [x] PRD / Epics / Architecture 文档修订已应用

> ✅ 代码实施完成（2026-08-01，Dev Agent Record: `dev-records/dev-record-graph-quality-P1-P10.md`）
> ⚠️ 浏览器端全流程验证依赖本机运行 LLM 配置 + 图谱数据库，见 Dev Record §5 注意事项

---

## 附：本次决策记录

| 决策点 | 结论 |
|:---|:---|
| 图谱丰富触发 | 正常搜索解析出实体即纳入丰富通道，替代"仅零结果冷启动" |
| 同步 vs 异步丰富 | **同步合并**（本迭代，零前端改动）；SSE 增量列 Phase 2 |
| 分类节点处理 | 方案 B：P31/P279 目标保留但标 `type:category` + `relevance:0.2`，不剔除（避免误伤概念语义上游） |
| 时间轴兜底阈值 | Wikidata 里程碑 <5 时触发 AI 丰富 |
| 相关度阈值 | 图谱过滤 `relevance>=0.5`；触发丰富判断用 `强相关节点 <6` |
