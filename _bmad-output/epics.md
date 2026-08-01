---
stepsCompleted: [1, 2, 3, 4]
status: 'complete'
completedAt: '2026-07-30'
inputDocuments:
  - prds/prd-Logos-2026-07-30/prd.md
  - architecture.md
  - specs/spec-logos/SPEC.md
  - specs/spec-logos/design-principles.md
  - design-system/logos/MASTER.md
  - design-system/logos/pages/landing.md
  - design-system/logos/pages/search.md
---

# Logos — AI 名词知识图谱与演化平台 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Logos — AI 名词知识图谱与演化平台, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR-1: **名词搜索** — 用户在搜索框输入名词，系统自动识别实体类型（人物、概念、技术等）并返回图谱数据。支持中英文双语输入。
FR-2: **模糊语义搜索** — 精确名词匹配失败时，系统进行语义相似搜索，返回最接近的实体结果。
FR-3: **冷启动名词图谱构建** — 首次搜索未索引名词时，系统自动从公开数据源（Wikidata API → LLM 补充 → spaCy 备选）构建知识图谱并缓存。
FR-4: **力导向图谱展示** — 系统以力导向图展示名词节点的关联网络，核心节点居中，关联节点环绕。支持拖拽、缩放、悬停弹摘要、点击展开。
FR-5: **关联强度与类型可视化** — 通过边的粗细区分关联强度，颜色编码区分关系类型（影响/隶属/创作/其他），低置信度关系以虚线展示。
FR-6: **节点详情展开** — 用户点击图谱中任意节点，展开详情视图（名称、类型、描述、关键事实列表、置信度）。
FR-7: **关联过滤** — 用户可按关联类型、置信度等级、时间范围过滤图谱显示内容。
FR-8: **时间轴展示** — 系统以可交互时间轴展示名词演化关键里程碑（5-10个），支持缩放时间粒度（年/十年/世纪）。
FR-9: **时间轴-图谱联动** — 用户拖动时间轴滑块时，图谱动态联动，仅显示该时间范围内的节点和边（延迟 < 500ms）。
FR-10: **关键里程碑自动摘要** — 系统自动提取 5-10 个关键里程碑节点，按时间排序，标题简明（≤20字），附说明和来源。
FR-11: **人物识别与优先排序** — 系统识别搜索实体是否为人名，人物节点优先级最高，人物关系类型具体化（师承/合作/竞争/隶属/亲属）。
FR-12: **人物递归探索** — 用户点击关联人物节点时图谱中心切换，上一级上下文保留在面包屑导航中，支持回溯。
FR-13: **置信度标注** — 所有实体、关系、事实标注置信度等级（高/中/低），在 UI 中可视化区分。
FR-14: **来源追溯** — 用户悬停/点击任一条关系或事实，可查看其来源信息（数据源名称 + 链接）。

> **已推迟：** FR-11（图谱上下文 AI 问答）和 FR-12（图感知问答策略）已根据 BMad 确认推迟到 Phase 2。MVP 中 LLM 仅用于数据管道（实体提取、搜索结构化、摘要生成）。

### NonFunctional Requirements

**性能：**
- NFR-1: 图谱数据（100 节点级别）在 2 秒内完成渲染
- NFR-2: 图谱查询接口 P99 延迟 < 500ms（缓存命中）/ < 5s（缓存未命中需构建）
- NFR-3: 图谱构建后台异步处理，不阻塞用户交互

**成本控制：**
- NFR-4: 三层缓存策略：浏览器（Next.js force-cache）→ Redis → Neo4j 持久化
- NFR-5: 分层检索策略（图遍历 > 语义搜索 > LLM 推理），上层问答不调下层
- NFR-6: 简单查询用小模型，复杂推理用强模型（通过 Instructor 多提供商切换）

**数据质量：**
- NFR-7: 所有事实和关系标注置信度等级（高/中/低）
- NFR-8: 多源交叉验证：同一事实从多个数据源比对
- NFR-9: 不一致的数据标为「低置信度」并展示所有来源

**隐私与合规：**
- NFR-10: 不存储用户搜索历史（除非未来用户登录后主动保存）
- NFR-11: 公开数据图谱不关联个人身份
- NFR-12: AI 生成内容页面标注「内容由 AI 生成」+ 置信度
- NFR-13: 为用户数据导出和删除机制预留接口（为 Phase 2 准备）

**可观测性：**
- NFR-14: 请求链路追踪：记录图谱查询耗时
- NFR-15: API 延迟监控：各接口 P50/P95/P99
- NFR-16: 错误追踪：Sentry 集成前后端异常
- NFR-17: 成本监控：每日 LLM Token 消耗报表，超过阈值自动告警

**技术选型约束：**
- NFR-18: MVP 采用模块化单体（Monolithic + 清晰模块边界）
- NFR-19: MVP 仅用 Neo4j（含原生向量索引 SEARCH 子句），暂不引入独立 Milvus
- NFR-20: 部署：Docker Compose（后端）+ Vercel（前端）
- NFR-21: 技术栈：Next.js v16 + FastAPI + Neo4j 5.x + D3.js force-graph + vis-timeline

### Additional Requirements

**来自架构文档：**

1. **Starter 模板：** 前端使用 `create-next-app`（TypeScript + Tailwind + ESLint + React Compiler + src/ 目录），后端手动搭建 FastAPI 三层架构（Repository → Service → API）
2. **SSE 推送协议：** 图谱增量更新使用 Server-Sent Events（SSE），非 WebSocket
3. **分层图谱加载：** 默认 1 跳，最多 3 跳，每跳 ≤ 50 节点
4. **Neo4j 命名规范：** Node Label = PascalCase（`:Person`, `:Entity`），Relation = UPPER_SNAKE_CASE（`:RELATES_TO`），属性 = camelCase
5. **API 传输层：** 统一 snake_case（Python Pydantic 默认），前端内部变量用 camelCase
6. **API 响应格式：** `{center, nodes[], edges[], depth, has_more}` — 非通用 `{data}` 封装
7. **API 错误格式：** `{error: {code, message, status, details}}`
8. **双语言命名规范：** TypeScript kebab-case 文件名、camelCase 函数；Python snake_case 文件名、snake_case 函数
9. **AI 框架：** neo4j-graphrag v1.18.0 + Instructor v1.15.4，LLM 提供商可切换（通过 Instructor from_provider()）
10. **Docker Compose 编排：** 前端 + 后端 + Neo4j + Redis
11. **Neo4j 数据迁移：** 随代码演化，无迁移工具（MVP 规模无需版本化迁移）
12. **前端状态管理：** React Compiler + 组件本地状态（无需 Redux/Zustand）
13. **监控策略：** 结构化日志（JSON）+ Sentry 免费层
14. **人物独立 Label：** 独立 `:Person` Node Label，不可退化为统一 `:Entity` 类型
15. **Edge 必含属性：** 每条关系必有 `source` / `confidence` / `evidence` 三字段

### UX Design Requirements

**来自设计系统（design-system/logos/）：**

UX-DR-1: **色彩系统实现** — 基于 Master 定义的调色板实现 CSS 变量：Primary `#475569`、Accent `#2563EB`、Background `#F8FAFC`、Foreground `#1E293B` 等
UX-DR-2: **字体系统配置** — 引入 Google Fonts Outfit（标题）+ Work Sans（正文），配置 Tailwind 的 fontFamily
UX-DR-3: **间距变量系统** — 实现从 `--space-xs` (4px) 到 `--space-3xl` (64px) 的 7 级间距 Token
UX-DR-4: **阴影层级** — 实现 `--shadow-sm` 到 `--shadow-xl` 四级阴影深度
UX-DR-5: **按钮组件** — 实现 Primary Button（蓝色 `#2563EB`）和 Secondary Button（透明边框）两个变体，含 hover 动效
UX-DR-6: **卡片组件** — 实现通用卡片组件（圆角 12px、阴影、hover 上浮动效）
UX-DR-7: **输入框组件** — 实现搜索输入框（圆角 8px、聚焦态蓝色边框+阴影）
UX-DR-8: **模态框组件** — 实现模态框（背景模糊、圆角 16px、居中对齐）
UX-DR-9: **Exaggerated Minimalism 风格** — 大字号（clamp）、大留白、高对比度、标题字重 900
UX-DR-10: **落地页布局** — Hero 搜索区 → 热门分类 → FAQ 手风琴 → 联系 CTA，四段式布局，1200px 最大宽度
UX-DR-11: **搜索建议** — 输入时显示预测建议（autocomplete），无结果时显示建议和替代搜索
UX-DR-12: **动效系统** — 过渡动效 150-300ms，hover 变换，滚动渐入，禁止 layout-shifting hover
UX-DR-13: **可访问性要求** — 对比度 ≥ 4.5:1，键盘导航可见焦点态，`prefers-reduced-motion` 支持，`cursor:pointer` 在所有可点击元素
UX-DR-14: **图标规范** — 使用 SVG 图标（Heroicons/Lucide），禁止 Emoji 替代图标
UX-DR-15: **响应式断点** — 支持 375px（手机）、768px（平板）、1024px（小桌面）、1440px（大桌面）

### FR Coverage Map

| FR | Epic | 描述 |
|:---:|:---:|:---|
| FR-1 | Epic 1 | 名词搜索 |
| FR-2 | Epic 1 | 模糊语义搜索 |
| FR-3 | Epic 1 | 冷启动图谱构建 |
| FR-4 | Epic 2 | 力导向图谱展示 |
| FR-5 | Epic 2 | 关联强度与类型可视化 |
| FR-6 | Epic 2 | 节点详情展开 |
| FR-7 | Epic 2 | 关联过滤 |
| FR-8 | Epic 2 | 时间轴展示 |
| FR-9 | Epic 2 | 时间轴-图谱联动 |
| FR-10 | Epic 2 | 关键里程碑自动摘要 |
| FR-11 | Epic 3 | 人物识别与优先排序 |
| FR-12 | Epic 3 | 人物递归探索 |
| FR-13 | Epic 3 | 置信度标注 |
| FR-14 | Epic 3 | 来源追溯 |
| FR-17 | Epic 4 | 搜索历史自动保存 |
| FR-18 | Epic 4 | 历史记录查看 |
| FR-19 | Epic 4 | 重复搜索提示 |

## Epic List

### Epic 1: 搜索与知识图谱构建引擎
用户输入一个名词，系统自动识别实体类型，从 Wikidata + AI Web Search 构建知识图谱并缓存。支持中英文输入、模糊语义匹配、冷启动构建。

**FRs 覆盖:** FR-1, FR-2, FR-3

**主要涉及文件:** SearchBar, SearchResults, nouns.py, wikidata_repo.py, ai/ 数据管道, config.py

**NFRs 覆盖:** 图谱构建异步非阻塞、三层缓存策略、Wiki + AI 双数据源

---

### Epic 2: 图谱可视化与探索体验
用户看到力导向关系图谱（可拖拽/缩放/过滤），点击节点展开详情。同时看到演化时间轴，拖动时间滑块时图谱动态联动。后台自动提取关键里程碑。

**FRs 覆盖:** FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10

**主要涉及文件:** GraphView/GraphNode/GraphEdge/GraphControls/GraphTooltip, TimelineView/TimelineItem/TimelineControls, graph.py, timeline.py, neo4j_repo.py, sse.py

**NFRs 覆盖:** 2s 图谱渲染、P99 < 500ms 缓存命中、SSE 增量推送、分层加载(1-3跳)

---

### Epic 3: 人物优先与数据质量系统
人物节点自动优先展示，关系类型具体化（师承/合作/竞争）。用户递归探索人物网络。所有事实标注置信度（高/中/低），可追溯来源。

**FRs 覆盖:** FR-11, FR-12, FR-13, FR-14

**主要涉及文件:** GraphNode(人物渲染), ConfidenceBadge, SourceLink, 边着色/虚线逻辑, neo4j_repo.py(:Person Label), GraphTooltip

**NFRs 覆盖:** 多源交叉验证、置信度标注、来源追溯、独立 :Person Label

---

### Epic 4: 匿名搜索历史（快照回顾）
无需登录，服务端自动保存搜索结果完整快照（查询词 + 图谱 + 时间轴）；用户可回顾历史搜索，重复搜索同一名词时提示"已有历史结果"，可选择查看快照或重新搜索。

**FRs 覆盖:** FR-17, FR-18, FR-19

**主要涉及文件:** SnapshotService, history.py, SearchBar, SearchResults, history 路由与 UI 组件

**NFRs 覆盖:** NFR-10（匿名快照、可删除、不关联身份）、存储决策（JSON 文件快照，零新增依赖）

---

## Epic 1: 搜索与知识图谱构建引擎

用户输入一个名词，系统自动识别实体类型，从 Wikidata + AI Web Search 构建知识图谱并缓存。支持中英文输入、模糊语义匹配、冷启动构建。

### Story 1.1: 项目初始化与基础设施搭建

As a **开发团队**,
I want 初始化前后端项目结构并配置 Docker 编排和服务依赖,
So that 所有模块可以在统一环境中开发、构建和运行。

**Acceptance Criteria:**

**Given** 开发环境尚未搭建
**When** 执行项目初始化脚本
**Then** 前端使用 `pnpm create-next-app` 初始化（TypeScript + Tailwind + ESLint + React Compiler + src/ 目录）
**And** 后端手动搭建 FastAPI 三层架构（Repository → Service → API），含完整目录结构
**And** `docker-compose.yml` 编排前端（Next.js dev）+ 后端（FastAPI）+ Neo4j 5.x + Redis
**And** 前端 `.env.example` 和后端 `.env.example` 包含所有环境变量占位符
**And** 前后端分别可通过 `docker compose up` 正常启动无报错

**覆蓋需求:** NFR-18（模块化单体）、NFR-20（Docker Compose）、NFR-21（技术栈）、架构附加 1（Starter）、架构附加 10（Docker 编排）

---

### Story 1.2: 设计系统基础与落地页搜索界面

As a **普通用户**,
I want 打开 Logos 首页看到一个带搜索框的 Hero 区域，感受到专业、极简的知识探索气场,
So that 我可以立即输入名词开始探索。

**Acceptance Criteria:**

**Given** 用户首次访问 Logos
**When** 打开首页
**Then** 页面显示 Hero 区域，包含一个居中搜索框和品牌标语
**And** CSS 变量系统已实现：`--color-primary` (#475569)、`--color-accent` (#2563EB)、`--color-background` (#F8FAFC) 等
**And** 字体使用 Outfit（标题）+ Work Sans（正文），通过 Google Fonts 引入
**And** 间距 Token（`--space-xs` 到 `--space-3xl`）和阴影层级（`--shadow-sm` 到 `--shadow-xl`）已配置
**And** 按钮组件（Primary/Secondary）、输入框组件、卡片组件、模态框组件已实现
**And** 落地页包含四段布局：Hero 搜索区 → 热门分类 → FAQ 手风琴 → CTA
**And** 最大宽度 1200px，全宽分段居中布局
**And** 可访问性：对比度 ≥ 4.5:1，`cursor:pointer` 在所有可点击元素，焦点态可见，支持 `prefers-reduced-motion`
**And** 响应式：375px / 768px / 1024px / 1440px 断点均正常

**覆蓋需求:** UX-DR-1~8（色彩/字体/间距/阴影/组件）、UX-DR-9（Exaggerated Minimalism）、UX-DR-10（落地页布局）、UX-DR-12~15（动效/可访问性/图标/响应式）

---

### Story 1.3: 名词搜索 API 与 Wikidata 集成

As a **普通用户**,
I want 在搜索框输入名词后，系统从 Wikidata 获取结构化数据并返回结果,
So that 我无需打开多个标签页就能获得该名词的结构化信息。

**Acceptance Criteria:**

**Given** 用户在搜索框输入一个已知名词（如"爱因斯坦"）
**When** 提交搜索请求
**Then** `GET /api/nouns?q=爱因斯坦` 端点被调用
**And** 后端通过 `wikidata_repo.py` 查询 Wikidata API 获取结构化数据
**And** 搜索数据写入 Neo4j 缓存（Node + Edge 模型）
**And** 搜索 API 返回结果包含：实体 ID、名称、类型（person/concept/technology）、置信度、一句话描述
**And** 搜索英文"Einstein"和中文"爱因斯坦"返回同一实体（跨语言对齐）
**And** 缓存命中时返回 < 500ms；首次未命中时返回 < 5s（含 Wikidata 查询时间）
**And** 输入 < 2 字符时返回提示"请输入更多内容"

**覆蓋需求:** FR-1（名词搜索）、NFR-2（P99 延迟）、NFR-4（三层缓存）、架构附加 5~7（API 格式）

---

### Story 1.3b: 实体消歧与用户选择界面

As a **普通用户**,
I want 搜索有歧义的名词时弹出消歧选择窗口，让我明确选择目标实体,
So that 即使有多个同名实体，我也能准确找到我想探索的那一个。

**Acceptance Criteria:**

**Given** 用户搜索一个有多义的名词（如"苹果"→水果/公司、"Java"→编程语言/岛屿）
**When** API 检测到返回多个不同实体
**Then** 搜索 API 返回 `needs_disambiguation: true` + `disambiguation_groups`
**And** 前端弹出 DisambiguationDialog 消歧弹窗
**And** 每个消歧项展示：实体名称、英文名（跨语言识别）、类型标签（人物/公司/概念等）、置信度、描述
**And** 弹窗支持键盘导航（↑↓选择，Enter确认，Escape关闭）
**And** 用户选择某一实体后，前端导航至该实体的图谱视图
**And** 跨语言对齐：同一 Wikidata Q ID 的不同语言标签合并为同一实体
**And** 按 Wikidata P31（instance of）推断可读类型标签
**And** 各实体按置信度降序排列，Wikipedia 页面来源优先级最高

**覆蓋需求:** FR-1（名词搜索含消歧）、架构附加 5（API 格式扩展）

---

### Story 1.4: 模糊语义搜索

As a **普通用户**,
I want 输入不完全准确的名词时，系统能理解我的意图并给出最接近的结果,
So that 我不需要记住精确的名称也能找到想要的信息。

**Acceptance Criteria:**

**Given** 用户输入一个没有精确命中的查询（如"深度学习之父"或拼写错误的名词）
**When** 搜索请求到达
**Then** 系统首先尝试精确匹配，未命中时退回到语义相似搜索
**And** 利用 Neo4j 向量索引（SEARCH 子句）执行语义查询
**And** 返回最接近的 1-3 个实体结果，标注匹配相似度分数
**And** 输入"深度学习之父"时返回 Hinton / LeCun 等人物的图谱
**And** 没有任何近似匹配时显示"未找到相关概念"，并建议检查拼写或换词
**And** 搜索建议 UI：用户输入时显示预测建议下拉列表（autocomplete

**覆蓋需求:** FR-2（模糊语义搜索）、UX-DR-11（搜索建议）、NFR-19（Neo4j 向量索引）

---

### Story 1.5: 图谱构建与 Web 内容丰富管道

As a **系统**,
I want 当用户搜索一个从未被索引的名词时，自动从多源数据构建知识图谱,
So that 即使是冷门名词也能获得可用的图谱数据。

**Acceptance Criteria:**

**Given** 用户搜索一个尚未被索引的名词
**When** 搜索请求到达
**Then** 系统触发异步构建流程（FastAPI BackgroundTasks）
**And** 分层数据源策略执行：Wikidata API（结构化数据）→ LLM 实体/关系提取（非结构化）→ AI Web Search 结构化 → 统一入 Neo4j
**And** 基线图谱（5-10 个核心节点）在 15 秒内完成并缓存
**And** 重复搜索同一名词时立即命中缓存（无需重建）
**And** AI 数据管道仅用于后台处理，不暴露用户交互界面
**And** 通过 Instructor v1.15.4 封装 LLM 调用，支持通过 `from_provider()` 切换 Anthropic / OpenAI
**And** 通过 neo4j-graphrag v1.18.0 实现图谱检索增强
**And** Wikidata 等主要数据源无数据时，提示用户数据有限，仅展示 LLM 推理结果并标注置信度
**And** 用户搜索解析出实体且基础图谱强相关节点 <6 时，系统通过 AI Web Search + LLM 提取丰富图谱，实体按与中心实体的相关度（relevance ≥0.5）过滤，名称优先解析为 Wikidata QID（无法解析保留 llm_* 前缀并标低相关度）
**And** Wikidata 纯分类节点（P31/P279 目标）标为低相关度类别节点（type:category + relevance 0.2），不占据图谱主展示位

**覆蓋需求:** FR-3（冷启动构建）、NFR-3（异步非阻塞）、架构附加 9（AI 框架）、架构附加 2（SSE 准备）

## Epic 2: 图谱可视化与探索体验

用户看到力导向关系图谱（可拖拽/缩放/过滤），点击节点展开详情。同时看到演化时间轴，拖动时间滑块时图谱动态联动。后台自动提取关键里程碑。

### Story 2.1: 力导向图谱核心渲染

As a **普通用户**,
I want 搜索名词后看到一个力导向关系图谱，节点可拖拽、画布可缩放,
So that 我对该名词的上下文关联有直观的视觉认知。

**Acceptance Criteria:**

**Given** 用户已搜索一个名词并收到图谱数据
**When** 图谱数据返回前端
**Then** GraphView 组件使用 D3.js force-graph 渲染力导向图
**And** 核心节点居中显示，关联节点环绕分布
**And** 默认展示 50 个主要关联节点
**And** 图谱在 2 秒内完成渲染（200 节点以内）
**And** 用户可拖拽任意节点，画布支持缩放（滚轮/手势）
**And** 鼠标悬停节点时弹出摘要卡片（名称、类型、置信度、一句话描述）
**And** 节点按实体类型多样渲染（人物圆形/事件菱形/其他方形 + 类型配色）
**And** 低相关度节点（relevance<0.3）与弱置信度边（confidence<0.3）自动淡化但保留
**And** 无图谱数据时显示友好空状态提示

**覆蓋需求:** FR-4（力导向图谱）、NFR-1（2s 渲染）、NFR-21（D3.js）

---

### Story 2.2: 图谱后端 API 与分层加载

As a **系统**,
I want 提供分层图谱查询 API 并支持 SSE 增量推送新增节点,
So that 用户可以快速看到图谱骨架，后台逐步丰富完整数据。

**Acceptance Criteria:**

**Given** 用户请求某个名词的图谱数据
**When** `GET /api/nouns/{id}/graph?depth=1` 被调用
**Then** 后端查询 Neo4j 返回该节点 1 跳范围内的所有关联（nodes + edges 格式）
**And** 默认 depth=1，最大 depth=3，每跳 ≤ 50 节点
**And** API 响应格式：`{center, nodes[], edges[], depth, has_more}`
**And** 字段使用 snake_case
**And** 缓存命中时 P99 < 500ms，未命中需构建时 < 5s
**And** `GET /api/events/graph-updates?noun_id={id}` SSE 端点建立长连接
**And** 后台完成新增节点/边解析后通过 SSE 推送增量数据
**And** 前端 GraphView 收到 SSE 事件后动态添加节点和边

**覆蓋需求:** FR-4（分层加载）、NFR-2（P99 延迟）、架构附加 2（SSE）、架构附加 3（分层加载）、架构附加 5-7（API 格式）

---

### Story 2.3: 节点详情展开与关联边可视化

As a **探索用户**,
I want 点击节点查看详情，并一眼看出节点间的关联强度和关系类型,
So that 我无需外部搜索就能理解名词间的深层联系。

**Acceptance Criteria:**

**Given** 用户在图谱中看到一个感兴趣节点
**When** 点击该节点
**Then** 详情面板在当前图谱旁展开（侧边栏或覆盖层）
**And** 详情面板包含：名称、类型、描述、置信度、关键事实列表（带来源）
**And** 详情面板底部显示「展开该节点的图谱」按钮，点击后中心切换到该节点
**And** 边的粗细反映关联强度（强关联 > 弱关联）
**And** 边的颜色编码关系类型（红色=影响、蓝色=隶属、绿色=创作、灰色=其他）
**And** Wikidata 关联属性映射为语义关系类型（创作/隶属/影响/其他），不再笼统显示为 related to
**And** 提供图例说明（可展开/收起）
**And** 低置信度关系以虚线展示，悬停显示来源
**And** 悬停任一条边时高亮显示其连接的两个节点

**覆蓋需求:** FR-5（边可视化）、FR-6（节点详情）、FR-14（来源追溯）

---

### Story 2.4: 关联过滤与搜索页集成

As a **高级用户**,
I want 按关联类型、置信度和时间范围过滤图谱内容,
So that 我可以聚焦于特定维度的关系网络。

**Acceptance Criteria:**

**Given** 用户在图谱视图中看到多个关联节点
**When** 用户操作过滤器控件
**Then** 关联类型多选过滤器（影响/隶属/创作/其他）可用，选择后图谱实时更新
**And** 置信度滑块（高/中/低）可用，调整后低置信度节点和边淡化而非消失
**And** 时间范围选择器可用，选择后过滤该时间段外的节点
**And** 过滤后图谱的动画过渡平滑（< 300ms）
**And** 搜索页完整布局搭建：顶部搜索栏（含 autocomplete）+ 图谱主区域 + 节点详情面板 + 底部/侧边时间轴 + 过滤工具栏
**And** 图谱默认占据页面主要面积，时间轴位于底部或侧边
**And** 错误响应格式统一：`{error: {code, message, status, details}}`

**覆蓋需求:** FR-7（关联过滤）、架构附加 7（错误格式）、架构附加 11-12（状态管理/监控）

---

### Story 2.5: 演化时间轴与图谱联动

As a **深度用户**,
I want 看到名词的演化时间线和关键里程碑，并拖动时间滑块观察不同时期的图谱变化,
So that 我能理解该概念的历史变迁和关键转折。

**Acceptance Criteria:**

**Given** 用户正在查看某个名词的图谱
**When** 页面加载完成
**Then** `GET /api/nouns/{id}/timeline` 返回 5-10 个关键里程碑
**And** TimelineView 使用 vis-timeline 渲染交互式时间轴
**And** 里程碑标题 ≤ 20 字，附带简要说明和来源链接
**And** 支持缩放时间粒度（年/十年/世纪）
**And** 没有历史数据时显示"该概念的演化数据有限"
**And** 拖动时间滑块时，图谱中不在该时间范围内的节点自动淡化
**And** 回到全时段时图谱恢复完整显示
**And** 联动延迟 ≤ 500ms
**And** 跨度 50 年以上的概念至少提取 5 个里程碑
**And** Wikidata 里程碑少于 5 个时，系统通过 AI Web Search + LLM 提取里程碑兜底合并，去重并按年份排序
**And** 每个里程碑附简要说明与来源链接（AI 提取里程碑标注置信度）

**覆蓋需求:** FR-8（时间轴）、FR-9（图谱联动）、FR-10（里程碑摘要）、NFR-21（vis-timeline）

## Epic 3: 人物优先与数据质量系统

人物节点自动优先展示，关系类型具体化（师承/合作/竞争）。用户递归探索人物网络。所有事实标注置信度（高/中/低），可追溯来源。

### Story 3.1: 人物识别与优先排序

As a **记者用户（如林记者）**,
I want 搜索人名时自动看到该人物的关联网络，且人物关系类型具体化,
So that 我一眼就能看出该人物与谁合作、受谁影响、属于哪个组织。

**Acceptance Criteria:**

**Given** 用户搜索一个人物名称
**When** 系统识别实体类型为 `:Person`
**Then** 图谱中心自动展示该人物的关联网络
**And** Neo4j 中人物节点使用独立 `:Person` Label（不可退化为 `:Entity`）
**And** 人物节点在搜索排名中优先于非人物节点
**And** 人物节点在图谱中的交互层级高于非人物节点（首位展示、更详细信息面板）
**And** 人物关系类型具体化为：师承/合作/竞争/隶属/亲属 等，而非笼统的"关联"
**And** 人物节点的悬停摘要卡片包含：姓名、领域、关键成就、置信度

**覆蓋需求:** FR-11（人物识别与优先排序）、架构附加 14（`:Person` 独立 Label）、架构附加 3（Neo4j 命名规范）

---

### Story 3.2: 人物递归探索与面包屑导航

As a **记者用户（如林记者）**,
I want 点击人物节点的关联人物时，图谱中心切换到该人物，并能回溯之前的探索路径,
So that 我可以连贯地探索多层人物关系网络而不迷失方向。

**Acceptance Criteria:**

**Given** 用户正在浏览一个人物的图谱
**When** 点击该人物的一个关联人物节点
**Then** 图谱中心切换到被点击的人物节点，展开其关联网络
**And** 上一级人物的探索上下文保留在面包屑导航中（左侧或底部）
**And** 面包屑支持点击回溯到任意已浏览过的人物节点
**And** `GET /api/nouns/{id}/graph?depth=1` 对新中心节点发起新的分层查询
**And** 切换过程动画流畅，不出现空白或闪烁
**And** 人物递归深度上限为 3 层（防止过度展开）

**覆蓋需求:** FR-12（人物递归探索）、NFR-18（模块化单体）

---

### Story 3.3: 置信度标注系统

As a **追求信息可靠性的用户（如王总）**,
I want 图谱中每个事实都标注置信度等级，并在 UI 中一目了然,
So that 我能判断哪些信息可靠可用、哪些需要进一步核实。

**Acceptance Criteria:**

**Given** 图谱中有多个实体和关系
**When** 查看图谱
**Then** 高置信度（多源交叉验证）的实体/关系无特殊标记，正常显示
**And** 中置信度（单一权威来源）的实体/关系旁带 ⚠️ 标记
**And** 低置信度（LLM 推理/单一非权威来源）的实体/关系旁带 ⚠️ 标记，且以虚线/暗淡色展示
**And** 提供「置信度说明」入口，用户点击后查看标注规则
**And** ConfidenceBadge 组件实现三种置信度状态的可视化变体
**And** 错误边标注的置信度在 Neo4j Edge 模型的 `confidence` 字段中存储（float 0.0-1.0）

**覆蓋需求:** FR-13（置信度标注）、NFR-7（置信度等级）、架构附加 15（Edge 三字段）

---

### Story 3.4: 来源追溯系统

As a **严谨的研究者**,
I want 悬停或点击任一条关系或事实时查看其来源信息,
So that 我可以追溯到信息源头，验证其可靠性。

**Acceptance Criteria:**

**Given** 用户在图谱中看到一条关系或一个事实
**When** 悬停或点击该关系/事实
**Then** 显示来源信息弹窗，包含数据源名称和链接
**And** 多源交叉验证的信息显示所有来源
**And** 每个来源默认显示源名称，点击后在新标签页打开原始页面
**And** 单源信息显示为该来源，多源信息按置信度排序展示
**And** SourceLink 组件实现来源展示，含源名称、链接图标、hover 态
**And** 来源信息存储于 Neo4j Edge 模型的 `source` 和 `evidence` 字段
**And** 无来源时标注「来源未知」

**覆蓋需求:** FR-14（来源追溯）、NFR-8（多源交叉验证）、NFR-9（低置信度展示来源）、架构附加 15（Edge 三字段）

## Epic 4: 匿名搜索历史（快照回顾）

无需登录，服务端自动保存搜索结果的完整快照（查询词 + 图谱 + 时间轴）；用户可回顾历史搜索，重复搜索同一名词时提示"已有历史结果"，可选择查看快照或重新搜索。

**存储决策（2026-07-31）：** 快照采用 JSON 文件存储（`data/history/*.json` + `index.json`），零新增依赖、可持久、可导出删除。图谱/时间轴的实时展示仍走 Redis 缓存 + Neo4j 持久化，快照是独立于缓存的完整副本，保存不依赖缓存命中。

### Story 4.1: 后端快照存储服务

As a **开发团队**,
I want 提供搜索快照的保存、列表、读取与存在性检查能力,
So that 前端能在搜索后保存快照、并在重复搜索时提示已有历史。

**Acceptance Criteria:**

**Given** 用户搜索并解析出实体
**When** 搜索结果返回图谱与时间轴
**Then** 系统自动保存该次搜索的完整快照（查询词、实体 ID/名称、图谱 nodes/edges、时间轴 milestones、saved_at）
**And** 同一名词重复搜索时更新快照，不产生重复记录
**And** 提供接口：POST/GET `/api/history`、GET `/api/history/{noun_id}`（含 exists 检查）、DELETE `/api/history/{noun_id}`
**And** 快照以 JSON 文件存储于 `data/history/`，零新增外部依赖
**And** 删除接口可清除单个名词的快照（隐私可删除）

**覆蓋需求:** FR-17、NFR-10

---

### Story 4.2: 搜索流程接入快照（保存 + 重复提示）

As a **回头搜索的用户**,
I want 搜索相同名词时系统提示已有历史结果，并可选择查看快照或重新搜索,
So that 我能快速回到之前的结果，避免重复等待。

**Acceptance Criteria:**

**Given** 用户搜索一个已存在历史快照的名词
**When** 搜索结果返回
**Then** 提示"已有历史结果"，提供两个选项：查看历史快照 / 重新搜索
**And** 选择"查看历史快照"直接加载已保存的图谱与时间轴（不发重新构建请求）
**And** 选择"重新搜索"重新构建最新数据并更新快照
**And** 首次搜索（无历史快照）不弹出提示，正常直接展示结果

**覆蓋需求:** FR-17、FR-19

---

### Story 4.3: 历史记录 UI

As a **想回顾过往探索的用户**,
I want 查看历史搜索列表并点击加载对应快照,
So that 我可以找回之前看过的名词图谱。

**Acceptance Criteria:**

**Given** 用户打开历史记录入口
**When** 查看历史列表
**Then** 显示历史搜索列表（名词、解析实体、保存时间）
**And** 点击某条记录加载该次保存的完整图谱与时间轴快照
**And** 列表支持删除单条历史记录
**And** 历史入口在搜索页/首页可访问

**覆蓋需求:** FR-18

<!-- Repeat for each future epic (N = 5, 6, 7...) -->

## Epic {{N}}: {{epic_title_N}}

{{epic_goal_N}}

<!-- Repeat for each story (M = 1, 2, 3...) within epic N -->

### Story {{N}}.{{M}}: {{story_title_N_M}}

As a {{user_type}},
I want {{capability}},
So that {{value_benefit}}.

**Acceptance Criteria:**

<!-- for each AC on this story -->

**Given** {{precondition}}
**When** {{action}}
**Then** {{expected_outcome}}
**And** {{additional_criteria}}

<!-- End story repeat -->
