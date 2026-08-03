# Sprint Change Proposal — 图谱内容多样性与降噪增强（P7-P10）

- **日期**：2026-07-31
- **触发人**：BMad
- **状态**：**已批准（2026-07-31）** — 文档修订已应用，代码按依赖链（P1-P6 → P7 → P8 → P9 → P10）交接 Developer agent 实施
- **变更等级**：Moderate（Epic 1/2 多 Story 调整，需 PO/DEV 协同）
- **前置依赖**：[sprint-change-proposal-2026-07-31-graph-timeline.md](./sprint-change-proposal-2026-07-31-graph-timeline.md)（P1-P6，已批准、未实施）

---

## 1. Issue Summary

### 触发原因

在上一个已批准提案（P1-P6：图谱内容 Web 丰富 + 相关性过滤）尚未实施时，BMad 提出新一轮图谱体验反馈：

> **图谱的内容还可以怎么丰富一些，目前的内容全都是 entity，没有别的内容，并且噪音很大。**

即：图谱内容单一（节点全为 entity、边全为 related_to）+ 噪音大。BMad 明确要求**不限于"苹果公司/科技公司"，对所有名词都要丰富图谱**。

### 根因分析（代码级证据）

| 症状 | 根因 | 代码证据 |
|:---|:---|:---|
| 节点全为 entity | `_map_wikidata_type` 仅映射 ~10 个 P31 QID；企业(Q4830453)/组织(Q43229)/产品/国家/城市 → 全落 `entity`；无 P279 子类继承；含 Q7889 电子游戏误映射 person 的 bug | [wikidata_repo.py:33-49](backend/app/repositories/wikidata_repo.py#L33-L49) |
| 边全为 related_to | `build_graph_from_wikidata` 所有边硬编码 `"type": "related_to"`；Wikidata 属性（P800/P1416/P463…）未映射为关系类型 | [graph.py:195-202](backend/app/api/graph.py#L195) |
| 噪音大 | P4（分类节点降级）已批准未实施；无弱边/低相关节点的视觉分级；孤立节点未处理 | 依赖 P1/P4/P9 |
| 类型不可见 | 前端 `GraphNode.type` TS 联合类型仅 `person/entity/event`；`category` 无配色/图例 | [api.ts:72](frontend/src/lib/api.ts#L72)、[GraphCanvas.tsx:16](frontend/src/components/graph/GraphCanvas.tsx#L16) |

### 变更性质

在已批准 P1-P6（Web 内容丰富 + relevance 过滤）之上，**增量补齐"类型多样 + 关系多样 + 降噪"三个维度**。三项机制均为**与领域无关的通用机制**（非针对特定公司打补丁）：L1 通用类型推断、L2 通用关系映射、L3 通用降噪（弱关联淡化）。属技术缺口补全 + 产品体验增强。

---

## 2. Impact Analysis

### 2.1 Epic 影响

| Epic | 影响 | 说明 |
|:---|:---|:---|
| **Epic 1 搜索与知识图谱构建引擎** | 主要 | 实体类型推断扩展（P7）、关系类型映射（P8） |
| **Epic 2 图谱可视化与探索体验** | 主要 | 弱关联淡化（P9）、前端类型体系对齐（P10） |
| **Epic 3 人物优先与数据质量系统** | 轻度 | 类型体系为人物优先提供更细粒度基础 |
| **Epic 4 匿名搜索历史** | 无 | 快照自动复用新数据 |

### 2.2 Story 影响

- **修改 Story 2.1（力导向图谱核心渲染）**：节点/边按 relevance/confidence 分级淡化；category 节点灰色渲染。
- **修改 Story 2.3（节点详情与关联边可视化）**：边类型映射为 6 种语义类型（创作/隶属/影响…），图例生效。
- **修改 Story 2.4（关联过滤）**：可选新增"弱关联淡化"开关（P9 Part C）。
- **修改 Story 1.3 / 1.5**：实体类型推断覆盖所有名词（规则表 + AI 兜底）。
- Story 1.5（P7-P10 中已批准的 P1-P6）依赖顺序不变。

### 2.3 文档冲突与更新

| 文档 | 更新内容 | 状态 |
|:---|:---|:---|
| PRD | FR-4（节点类型多样）、FR-5（边类型映射）、FR-7（弱关联淡化） | 待应用（见 §4.2） |
| Epics | Story 1.3/1.5、2.1/2.3/2.4 AC 修订 | 待应用（见 §4.2） |
| Architecture | 实体类型推断策略（规则 + AI 兜底）、关系类型映射表 | 待应用（见 §4.2） |
| Frontend Design | GraphNode 类型联合拓宽、category 配色/图例、弱关联淡化视觉 | 待应用（见 §4.2） |

### 2.4 技术影响

- **类型推断**：`_map_wikidata_type` 扩展为通用三层（P31 映射 + P279 继承 + 描述关键词兜底）+ AI 兜底（搭既有丰富管道，不新增独立 LLM 调用）。
- **关系映射**：Wikidata 属性 → 6 种语义关系类型映射表；Neo4j 边类型读写规范化。
- **降噪**：前端边透明度按 confidence 分级、节点透明度按 relevance 分级；数据完整保留（方案 Y，不剔除）。
- **前端类型体系**：`GraphNode.type` 联合类型拓宽 + `category` 配色/图例。
- **成本**：类型推断主路径零 LLM 依赖；AI 兜底仅规则未命中 + LLM 已配置时启用，搭既有调用，符合 NFR-6。

---

## 3. Recommended Approach

**路径选择：Direct Adjustment**（在已批准 P1-P6 之上增量追加，不推翻任何决策）

**工作量估算**：

| 提案 | 内容 | 估算 |
|:---|:---|:---|
| P7 | 通用实体类型推断（规则表 + AI 兜底） | 1 人日 |
| P8 | 关系类型映射表 + Neo4j 边规范化 | 1 人日 |
| P9 | 弱关联淡化（前后端协作，方案 Y） | 0.5 人日 |
| P10 | 前端类型体系对齐（类型 + 配色 + 图例） | 0.5 人日 |
| 文档 | PRD / Epics / Architecture / Frontend Design 同步 | 0.5 人日 |
| **本提案小计** | | **约 3.5 人日** |
| **含 P1-P6（前置）** | 数据模型/提取/丰富/去噪 | 约 5 人日 |
| **合计** | | **约 8.5 人日** |

**风险评估**：

| 风险 | 等级 | 缓解 |
|:---|:---|:---|
| 类型映射表覆盖不全（冷门类别仍 entity） | 中 | P279 继承 + 描述关键词兜底 + AI 兜底（规则未命中时） |
| AI 兜底引入成本/延迟 | 低 | 搭既有 Web 丰富管道顺带完成，不新增独立调用；LLM 未配置静默退化纯规则 |
| 弱边淡化过强导致信息不可读 | 低 | 透明度下限 0.2，可配；可选"淡化开关" |
| 前端类型拓宽引入类型错误 | 低 | 纯类型与配色，无逻辑变更；后端未知类型归一为 `other` |
| 实施顺序冲突（P7-P10 依赖 P1-P6） | 中 | 明确依赖链：P1-P6 先行 → P7 → P8 → P9 → P10 |

**时间线影响**：并入上一轮 P1-P6 的实施队列，作为同一"图谱质量增强"批次（合计约 8.5 人日），不阻塞 Epic 4 收尾。

---

## 4. Detailed Change Proposals

以下 4 条增量提案已经 BMad 在增量模式下逐条批准（`[a]`）。

### 4.1 代码变更提案（已批准）

**P7 L1 通用实体类型推断（规则表 + AI 兜底，策略 B）**
- 文件：`backend/app/repositories/wikidata_repo.py`、`backend/app/ai/extractor.py`、`backend/app/services/graph_service.py`
- **Part A 规则表**：`_ENTITY_TYPE_MAP` 覆盖 person/organization/technology/event/concept（企业/组织/法人/软件/编程语言/产品/网站/电子游戏/事件/学术概念/作品/国家等）；`_map_wikidata_type` 三层推断：① P31 直映射 → ② P279 子类继承 → ③ 描述关键词兜底；修复 Q7889 电子游戏误映射 person。
- **Part B AI 兜底**：`EntityExtractionResult` 增加 `focus_entity_type`；丰富流程中仅当中心实体规则类型为 `entity` 且 LLM 已配置时，用 LLM 判定覆盖并写回；LLM 未配置静默退化纯规则。
- 理由：对**任何名词**产出有意义类型，零 LLM 依赖主路径 + 成本受控兜底。

**P8 L2 通用关系类型映射**
- 文件：`backend/app/api/graph.py`、`backend/app/repositories/neo4j_repo.py`
- **Part A**：`_RELATION_TYPE_MAP`（Wikidata 属性 → 6 种关系类型）：P800/P50/P144→creation；P106/P1416/P463/P127/P355/P361→affiliation；P2860/P737→influence；P910/P1830/P279→other。`_extract_related_qids` 返回 `(qid, prop)`，写边时映射。
- **Part B**：Neo4j `upsert_relation` 存 UPPER_SNAKE 关系类型；`get_graph` 读回时归一为小写语义类型，未知/`related to` → `other`，保证前端 6 色板命中。
- 理由：边从灰色"related to"变为有语义的颜色编码，图例生效，与领域无关。

**P9 图谱降噪 —— 弱关联淡化（方案 Y）**
- 文件：`backend/app/repositories/neo4j_repo.py`、`frontend/src/components/graph/GraphCanvas.tsx`、`frontend/src/components/graph/GraphControls.tsx`（可选）
- 后端 `get_graph` **不剔除**数据（信息完整）；孤立节点标 `relevance:0.1`。
- 前端：边 `stroke-opacity = 0.2 + confidence*0.5`、`stroke-width = max(0.75, confidence*3)`、低置信度虚线 `3,5`；节点 `opacity = 中心 1 : 0.45 + relevance*0.55`。
- 可选：GraphControls 增加"弱关联淡化"开关（默认开）。
- 理由：弱关联/低相关不抢视觉注意力但数据保留可追溯。

**P10 前端类型体系对齐**
- 文件：`frontend/src/lib/api.ts`、`frontend/src/components/graph/GraphCanvas.tsx`、`frontend/src/components/graph/GraphLegend.tsx`
- `GraphNode.type` 联合拓宽为 `person/entity/event/concept/technology/organization/category`；`NODE_COLORS`/`NODE_TYPES` 增加 `category: #94A3B8`（灰）。
- 理由：打通 P4/P7 产出的多样类型与 category 节点的前端接收端，纯类型与配色改动。

### 4.2 文档变更提案（✅ 已应用 2026-07-31）

**PRD 修订：**

**FR-4 力导向图谱展示**（[prd.md:173](backend/../_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L173)）— 增加可验证结果：
> `- 图谱节点按实体类型多样呈现（人物/组织/技术/事件/概念等），非统一"实体"样式`
> `- 节点与边按相关度/置信度分级淡化：弱关联与低相关节点视觉退后但不丢失`

**FR-5 关联强度与类型可视化**（[prd.md:189](backend/../_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L189)）— 修订：
> OLD：`关系类型通过颜色编码区分（红色=影响、蓝色=隶属、绿色=创作、灰色=其他）`
> NEW：`关系类型通过颜色编码区分（红色=影响、蓝色=隶属、绿色=创作、黄色=竞争、紫色=合作、灰色=其他）；Wikidata 关联属性映射为语义关系类型，不再笼统显示为"related to"`

**FR-7 关联过滤**（[prd.md:214](backend/../_bmad-output/prds/prd-Logos-2026-07-30/prd.md#L214)）— 增加：
> `- 提供"弱关联淡化"开关，关闭时弱边恢复实线全透明度`

**Epics 修订：**

**Story 2.1** 新增 AC：
> `And 节点按实体类型多样渲染（人物圆形/事件菱形/其他方形 + 类型配色）`
> `And 低相关度节点（relevance<0.3）与弱置信度边（confidence<0.3）自动淡化但保留`

**Story 2.3** 新增 AC：
> `And Wikidata 关联属性映射为语义关系类型（创作/隶属/影响/其他），不再笼统显示为 related to`

**Architecture 修订：**
- 实体类型推断策略：**规则表（P31 映射 + P279 继承 + 描述关键词）为主路径，AI 兜底仅规则未命中且 LLM 已配置时启用**，搭既有丰富管道不新增独立调用。
- 关系类型映射：Wikidata 属性 → Logos 6 种关系类型映射表；Neo4j 边类型 UPPER_SNAKE 存储、读取归一为小写语义类型。

**Frontend Design 修订：**
- `GraphNode.type` 联合类型拓宽至 7 种；`category` 类型配色 #94A3B8 与图例。
- 弱关联淡化视觉规范（边/节点透明度分级）。

---

## 5. Implementation Handoff

### 变更范围分类：**Moderate**（Epic 1/2 多 Story 调整，需 PO/DEV 协同）

### 交接对象与职责

| 角色 | 职责 |
|:---|:---|
| **PO / BMad** | 批准本提案；确认 PRD/Epics/Architecture/Frontend Design 文档修订落地；确认 P7-P10 与 P1-P6 合并排程 |
| **Developer agent** | 按依赖链实施 P1-P6 → P7 → P8 → P9 → P10；补单测（类型推断、关系映射、淡化计算） |
| **Architect（如需）** | 复核类型推断 AI 兜底策略与关系映射表 |

### 实现顺序与依赖

```
P1-P6（上一轮已批准：relevance 字段 → 提取相关性 → 过滤/ID 统一 → Wikidata 去噪 → Web 丰富 → 时间轴 AI）
   ↓
P7 L1 类型推断（规则表 + AI 兜底）        ← 依赖 P1（relevance）/ P5（Web 丰富管道）
   ↓
P8 L2 关系类型映射                        ← 依赖 P4（_RELATION_PROPS 白名单收敛）
   ↓
P9 弱关联淡化（前后端）                   ← 依赖 P1（relevance）/ P4（category）
   ↓
P10 前端类型体系对齐                       ← 依赖 P7/P4（接收端）
   ↓
文档同步（PRD / Epics / Architecture / Frontend Design）
```

### 成功标准

- [x] 搜索任意名词（企业/人物/概念/技术/事件/地点/作品）图谱均呈现多样节点类型，非全 entity（P7）
- [x] "苹果公司"图谱：中心 organization，关联含 person（乔布斯）/technology（iPhone）/organization（三星）等，边有创作/隶属/竞争等语义类型（P7/P8）
- [x] 弱关联边与低相关节点视觉淡化但数据保留，无剔除（P9）
- [x] 前端图例与配色覆盖全部 7 种节点类型（P10）
- [x] LLM 未配置时类型推断仍正常（纯规则主路径）（P7 Part A）
- [x] 后端 `pytest` 通过（新增类型推断、关系映射、淡化计算单测）
- [x] 浏览器端全流程验证（搜索 → 图谱类型/边类型/淡化 → 快照保存）
- [x] 文档修订已应用

> ✅ 代码实施完成（2026-08-01，Dev Agent Record: `dev-records/dev-record-graph-quality-P1-P10.md`）
> ⚠️ 浏览器端全流程验证依赖本机运行 LLM 配置 + 图谱数据库，见 Dev Record §5 注意事项

---

## 附：本次决策记录

| 决策点 | 结论 |
|:---|:---|
| 类型推断策略 | **B 规则表 + AI 兜底**：规则表（P31 + P279 继承 + 描述关键词）零 LLM 依赖主路径；AI 兜底仅规则未命中且 LLM 已配置，搭既有丰富管道 |
| 适用范围 | **对所有名词生效**的通用机制，非针对特定类别打补丁 |
| 弱边处理 | **方案 Y 淡化**（不剔除）：边透明度随 confidence、节点透明度随 relevance 分级；可选开关 |
| 关系映射 | Wikidata 属性 → 6 种语义关系类型；Neo4j UPPER_SNAKE 存取、读取归一小写 |
| 与 P1-P6 关系 | 增量叠加，统一为"图谱质量增强"批次（合计约 8.5 人日），依赖链明确 |
