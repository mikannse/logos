---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - brainstorming/brainstorming-session-2026-07-30-101922.md
  - briefs/brief-logos-2026-07-30/brief.md
  - briefs/brief-logos-2026-07-30/addendum.md
  - research/domain-ai-名词知识图谱与演化平台-research-2026-07-30.md
  - research/technical-ai-名词知识图谱与演化平台-技术实现-research-2026-07-30.md
  - prfaq-logos.md
  - prfaq-logos-distillate.md
lastStep: 8
workflowType: 'architecture'
project_name: 'Logos — AI 名词知识图谱与演化平台'
user_name: 'BMad'
date: '2026-07-30'
status: 'complete'
completedAt: '2026-07-30'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (MVP Core Loop):**

1. **名词搜索** — 搜索框输入名词，自动触发多源数据采集与图谱构建
2. **关系图谱可视化** — 2D 力导向图展示实体间关联，支持缩放/拖拽/刷选/按关系类型着色
3. **演化时间轴** — 名词从哪来→关键变化→可能去向，自动提取 5-10 个关键节点
4. **AI 数据管道（内功，无对话界面）** — LLM 用于实体/关系提取、Web Search 内容结构化、以及前三个步骤的增强（知识点摘要、时序数据提取等）
5. **人物优先入口** — 人物作为默认探索入口，人物节点特殊展示
6. **多源数据融合** — Wikidata API + AI Web Search Tool 双数据源，结构化和非结构化数据统一入库
7. **增量式图谱展示** — 先渲染骨架（5-10 核心节点），后台逐步"长胖"
8. **多源交叉验证 + 置信度标注** — 每个事实标注可信度和来源链接

**Non-Functional Requirements:**

| 维度 | 要求 | 架构影响 |
|:---|:---|:---:|
| 感知性能 | 图谱骨架 < 1s | 异步并行请求 + WebSocket 增量推送 |
| 数据质量 | 关系可追溯、置信度可查 | Edge 模型必含 source/confidence/evidence |
| 成本控制 | LLM API 成本可预测 | 缓存优先 + 查询优化 |
| 可扩展 | MVP 紧密 → 未来可拆分 | 模块边界清晰、接口抽象 |
| 合规 | AI 生成内容标识、源链接 | UI 层面 + 数据层面双重保障 |

### Technical Constraints & Dependencies

| 领域 | 决策 | 依据 |
|:---|:---|:---|
| 前端 | Next.js v16 + TypeScript | 脑暴 + 技术报告验证 |
| 可视化 | D3.js force-graph + vis-timeline | 领域研究建议 |
| 后端 | FastAPI（Python 异步） | 脑暴 + 技术报告验证 |
| 图数据库 | **Neo4j**（含原生向量索引） | 多源异构数据归一化存储的必要基础设施 |
| 数据源 | Wikidata API + AI Web Search Tool | 结构化 + 非结构化双源 |
| AI 角色 | **仅用于数据管道**（实体提取、搜索结构化、摘要生成），无用户可见 AI 对话 | BMad 确认 |
| 部署 | 本地 Docker Compose（MVP） | BMad 确认 |
| 前端托管 | Vercel（待定，可后续决定） | — |

### Scale & Complexity Assessment

- **项目复杂度：** 中高——前端可视化 + 后端 AI 管道 + 多数据库 + 多源集成
- **主要技术领域：** 全栈 Web + AI/ML 数据处理
- **团队规模驱动：** 独立创始人 / 3-5 人团队 —— 架构必须极简
- **核心风险：** 不是技术可行性（所有组件已验证）—— UX 假设验证是整个项目命门
- **预计架构组件数：** ~8-12 个核心模块

### Cross-Cutting Concerns

| 关注点 | 影响范围 |
|:---|:---|
| LLM API 成本控制 | 全架构 —— 缓存策略、检索层次、AI 调用时机 |
| 数据质量 + 置信度标注 | 数据模型、图谱展示、用户信任链 |
| 渐进式信息密度 | 前端组件设计、数据加载策略、API 响应分层 |
| 多源数据融合 | 数据管道层、实体对齐、冲突解决 |
| 合规（AI 标识 + 隐私） | AI 输出标注、数据源引用、用户数据 |
| 可观测性 | LLM Token 追踪、图谱查询耗时、API 延迟 |

---

## Advanced Elicitation: Architecture Deep Dive

### Stakeholder Round Table (利益相关者圆桌)

**用户角色视角 → 架构合成：**

| 关注点 | 涉及角色 | 架构含义 |
|:---|:---|:---|
| 秒级图谱骨架 | 小明（普通用户） | 分块加载：先渲染 5-10 核心节点 → 后台增量推送扩展 |
| 关系可追溯 | 林记者（记者） | Edge 属性必有 `source`/`confidence`/`evidence` |
| N 跳深度控制 | 王总（投资者） | Neo4j 查询 `LIMIT` + 安全网；前端节点上限保护 |
| 卡片可快照 | 阿花（创作者） | API 响应结构预设计为可序列化快照格式（为 Phase 2 个人知识库准备）|
| 人物优先 + 关系着色 | 林记者 | 独立 `:Person` Node Label + 关系类型过滤 API |
| 模糊匹配 + 语义搜索 | 阿花 | Neo4j 向量索引 MVP 即需引入 |

### First Principles Analysis (第一性原理分析)

**核心反思：** 多源异构数据（Wikidata 结构化 + AI Web Search 非结构化）的归一化存储是图数据库不可替代的价值点。MVP 必须包含 Neo4j。

**核心理念 — AI 作为管道引擎：** AI 不暴露为用户可见的聊天窗口，而是作为数据管道的核心引擎：
- 搜索结构化 → Wikidata 直接入库
- 搜索非结构化 → AI Web Search + LLM 实体/关系提取 → 入库
- 知识点摘要生成 → LLM 处理 → 入库
- 数据质量增强 → LLM 交叉验证 → 标注置信度

### Architecture Decision Records (架构决策记录)

| ADR | 争议 | 决策 | 原理 |
|:---|:---|---:|:---|
| ADR-001 | AI Web Search 同步/异步 | **绝对异步**：并行请求（Wiki + AI Search 同时发），增量图谱节点逐步出现 | 用户感知性能优先 |
| ADR-002 | Edge 数据模型粒度 | `source` + `confidence` + `evidence` **必含** | 源头可追溯是信任根基 |
| ADR-003 | 人物独立 Label | **独立 `:Person` Label** | 人物优先原则的数据层保障 |
| ADR-004 | 图谱缓存粒度 | **全图缓存 + 节点级增量更新混合** | 命中率 + 数据新鲜度兼得 |

### Key Architectural Principles (Confirmed)

1. **先渲染后丰富** — 图谱骨架（500ms 内）→ 增量节点/边逐步推送，用户感知到的"快"比"完整"更重要
2. **AI 不可见原则** — AI 仅用于数据管道内功，不暴露为用户交互界面
3. **可追溯优先于数量** — 每条关系必须有数据来源，置信度标注不可省略
4. **图数据库是必需品** — 多源异构数据的统一存储层，不可因 MVP 简化而省略
5. **架构预留原则** — API 响应结构为 Phase 2（卡片快照、个人知识库）预留序列化格式

---

## Starter Template Evaluation

### Primary Technology Domain

全栈 Web 应用 — 双代码库架构（TypeScript 前端 + Python 后端），不存在单一 starter 覆盖两个代码库。

### Starter Options Considered

| 代码库 | 方案 | 当前版本 |
|:---|:---|---:|
| **前端（Next.js）** | `create-next-app` — Next.js 官方脚手架 | **Next.js v16.2.12** |
| **后端（FastAPI）** | 手动搭建规范化项目结构 | **FastAPI v0.141.1** |

### Frontend: Next.js Starter Configuration

`create-next-app` 默认提供的架构决策：

| 决策项 | 状态 | 适用性 |
|:---|:---:|:---:|
| TypeScript | ✅ 默认开启 | 适用 |
| App Router | ✅ 默认开启 | 适用 — RSC 做图谱数据初始加载 |
| Tailwind CSS | ✅ 默认开启 | 适用 — 原子化样式 |
| ESLint | ✅ 默认开启 | 适用 |
| React Compiler | ✅ `--react-compiler` 开启 | 自动优化图谱重渲染 |
| `src/` 目录 | ✅ `--src-dir` 开启 | 结构更清晰 |
| pnpm | ✅ 包管理器选型 | 速度 + 磁盘效率 |

**初始化命令：**

```bash
pnpm create next-app frontend \
  --typescript \
  --tailwind \
  --eslint \
  --react-compiler \
  --src-dir \
  --app \
  --import-alias "@/*"
```

### Backend: FastAPI Project Structure

FastAPI 无官方 CLI starter。基于 Repository → Service → API 三层架构手工搭建：

```
backend/
├── app/
│   ├── main.py                # FastAPI 入口
│   ├── config.py              # 环境变量管理
│   ├── api/                   # 路由层
│   │   ├── __init__.py
│   │   ├── nouns.py           # /api/nouns
│   │   ├── graph.py           # /api/graph
│   │   └── timeline.py        # /api/timeline
│   ├── services/              # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── graph_service.py
│   │   └── timeline_service.py
│   ├── repositories/          # 数据访问层（Repository Pattern）
│   │   ├── __init__.py
│   │   ├── neo4j_repo.py
│   │   └── wikidata_repo.py
│   ├── models/                # Pydantic 数据模型
│   │   ├── __init__.py
│   │   ├── noun.py
│   │   └── relation.py
│   ├── ai/                    # AI 数据管道（LLM 内功）
│   │   ├── __init__.py
│   │   ├── llm_client.py      # LLM 统一客户端（Instructor 封装）
│   │   ├── extractor.py       # 实体/关系提取
│   │   ├── web_search.py      # AI Web Search 工具
│   │   └── summarizer.py      # 知识点摘要生成
│   └── core/                  # 基础设施
│       ├── __init__.py
│       ├── cache.py           # Redis 缓存封装
│       └── neo4j_client.py    # Neo4j 驱动
├── tests/
├── requirements.txt
├── pyproject.toml
└── Dockerfile
```

**初始依赖（requirements.txt）：**

```
fastapi==0.141.1
uvicorn[standard]
neo4j
pydantic
httpx
redis
instructor==1.15.4
neo4j-graphrag==1.18.0
```

**LLM 提供商依赖（按需安装）：**

```bash
# Anthropic（作为默认）
pip install anthropic

# 或 OpenAI
pip install openai

# 根据 Instructor `from_provider()` 一行切换
```

### Selected Architecture: Decoupled Starter Strategy

- **前端**：官方 `create-next-app` 脚手架（零配置启动）
- **后端**：FastAPI 手动搭建（三层架构，Repository → Service → API）
- **包管理器**：pnpm（前端）/ pip + requirements.txt（后端）
- **部署**：Docker Compose 编排双服务

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**

| 决策 | 选择 | 依据 |
|:---|:---|:---|
| Neo4j 数据迁移 | 随代码演化，无迁移工具 | Neo4j Schema-optional，MVP 规模无需版本化迁移 |
| 图谱推送协议 | SSE（Server-Sent Events） | 单向推送足够简单，无需 WebSocket 的复杂度 |
| 图谱数据加载 | 分层加载（默认 1 跳，最多 3 跳，每跳 ≤ 50 节点） | 渐进式信息密度原则 |

**Important Decisions (Shape Architecture):**

| 决策 | 选择 | 依据 |
|:---|:---|:---|
| 监控策略 | 结构化日志（JSON） + Sentry 免费层 | 零成本可见性，问题可追溯 |
| 前端状态管理 | React Compiler + 组件本地状态 | Starter 默认，轻量够用 |
| AI 管道框架 | **neo4j-graphrag v1.18.0 + Instructor v1.15.4** | neo4j-graphrag 做 Neo4j GraphRAG 检索，Instructor 做结构化实体/关系提取 |
| LLM 提供商策略 | 可切换（LiteLLM/Instructor 统一接口） | 通过 Instructor `from_provider()` 一行切换 Anthropic / OpenAI |

**Deferred Decisions (Post-MVP):**

| 决策 | 阶段 | 原因 |
|:---|:---:|:---|
| 认证与授权 | Phase 2 | MVP 无注册墙，无需用户系统 |
| 数据加密 | Phase 2 | 本地运行，无传输加密需求 |
| CI/CD 流水线 | Phase 2 | 本地 Docker 开发，上线前配置即可 |
| Prometheus/Grafana | Phase 2+ | MVP 日志+Sentry 足够 |
| 微服务拆分 | Phase 2+ | 模块化单体先验证产品

---

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

双语言项目（TypeScript + Python）中 5 个关键冲突领域，已全部覆盖。

### API & Data Exchange Patterns

**JSON 字段命名（跨前后端）：** `snake_case`
- Python FastAPI Pydantic 模型输出默认 snake_case
- 前端 API 层接受 snake_case 字段，前端内部变量用 camelCase
- 无需额外转换中间件

**API 响应格式（图谱端点）：**

```json
{
  "center": "爱因斯坦",
  "nodes": [
    { "id": "einstein", "label": "爱因斯坦", "type": "person", "confidence": 0.95 }
  ],
  "edges": [
    { "source": "einstein", "target": "relativity", "type": "developed", "confidence": 0.9, "source_url": "https://..." }
  ],
  "depth": 1,
  "has_more": true
}
```

**API 错误响应格式：**

```json
{
  "error": {
    "code": "not_found",
    "message": "未找到名词"实体名"",
    "status": 404,
    "details": {}
  }
}
```

### Neo4j Naming Conventions

| 元素 | 惯例 | 例子 |
|:---|:---|:---|
| Node Label | PascalCase | `:Person`, `:Entity`, `:Event` |
| Relationship Type | UPPER_SNAKE_CASE | `:RELATES_TO`, `:FOUNDED_BY` |
| 属性名 | camelCase | `entityName`, `confidenceScore` |

### Code Naming Conventions

| 元素 | TypeScript（前端） | Python（后端） |
|:---|:---|:---|
| 文件名 | `kebab-case.tsx` / `kebab-case.ts` | `snake_case.py` |
| 组件名 | `PascalCase` | — |
| 函数/方法 | `camelCase` | `snake_case` |
| 类名 | `PascalCase` | `PascalCase` |
| 常量 | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` |
| 测试文件 | `*.test.ts` / `*.test.tsx` | `test_*.py` |

### Key Rules for AI Agents

1. API 传输层始终 `snake_case`；前端内部变量用 `camelCase`
2. 图谱端点返回 nodes/edges 格式，非通用 `{data}` 封装
3. Neo4j Label = PascalCase, Relation = UPPER_SNAKE_CASE, 属性 = camelCase
4. 错误响应必须包含 `code` / `message` / `status` 三字段
5. 双语言各自遵循各自生态的命名标准

---

## Project Structure & Boundaries

### Complete Project Directory Structure

```
logos/
├── docker-compose.yml       # 编排前端+后端+Neo4j+Redis
├── .gitignore
├── README.md
│
├── frontend/                # Next.js TypeScript 前端
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── .env.example
│   ├── src/
│   │   ├── app/
│   │   │   ├── globals.css
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── [[...slug]]/
│   │   │       ├── page.tsx
│   │   │       └── loading.tsx
│   │   ├── components/
│   │   │   ├── graph/
│   │   │   │   ├── GraphView.tsx
│   │   │   │   ├── GraphNode.tsx
│   │   │   │   ├── GraphEdge.tsx
│   │   │   │   ├── GraphControls.tsx
│   │   │   │   └── GraphTooltip.tsx
│   │   │   ├── timeline/
│   │   │   │   ├── TimelineView.tsx
│   │   │   │   ├── TimelineItem.tsx
│   │   │   │   └── TimelineControls.tsx
│   │   │   ├── search/
│   │   │   │   ├── SearchBar.tsx
│   │   │   │   └── SearchResults.tsx
│   │   │   └── ui/
│   │   │       ├── LoadingSkeleton.tsx
│   │   │       ├── ErrorBoundary.tsx
│   │   │       ├── ConfidenceBadge.tsx
│   │   │       └── SourceLink.tsx
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── graph.ts
│   │   │   ├── sse.ts
│   │   │   └── utils.ts
│   │   ├── types/
│   │   │   ├── graph.ts
│   │   │   ├── api.ts
│   │   │   └── common.ts
│   │   └── hooks/
│   │       ├── useGraph.ts
│   │       ├── useSSE.ts
│   │       └── useTimeline.ts
│   ├── public/assets/icons/
│   └── tests/
│       └── components/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── nouns.py
│   │   │   ├── graph.py
│   │   │   ├── timeline.py
│   │   │   └── sse.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── graph_service.py
│   │   │   ├── timeline_service.py
│   │   │   └── search_service.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── neo4j_repo.py
│   │   │   └── wikidata_repo.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── noun.py
│   │   │   ├── relation.py
│   │   │   ├── graph.py
│   │   │   └── timeline.py
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── extractor.py
│   │   │   ├── web_search.py
│   │   │   └── summarizer.py
│   │   └── core/
│   │       ├── __init__.py
│   │       ├── cache.py
│   │       ├── neo4j_client.py
│   │       └── exceptions.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_api/
│   │   └── test_services/
│   └── scripts/
│       └── seed_data.py
└── docs/
    └── architecture.md
```

### Requirements to Structure Mapping

| 功能需求 | 前端组件 | 后端 API | 数据层 |
|:---|:---|:---|:---|
| 名词搜索 | SearchBar.tsx, SearchResults.tsx | nouns.py (GET /api/nouns) | wikidata_repo.py |
| 关系图谱 | GraphView.tsx, GraphNode.tsx, GraphEdge.tsx | graph.py (GET /api/nouns/{id}/graph) | neo4j_repo.py |
| 演化时间轴 | TimelineView.tsx, TimelineItem.tsx | timeline.py (GET /api/nouns/{id}/timeline) | neo4j_repo.py |
| 增量图谱更新 | GraphView.tsx（SSE 订阅）| sse.py (GET /api/events/graph-updates) | — |
| AI 数据管道 | —（后台无 UI） | — | ai/extractor.py, ai/web_search.py |
| 置信度/来源标注 | ConfidenceBadge.tsx, GraphEdge.tsx（着色）| — | models/relation.py（Edge 模型）|

### API Boundaries

| 端点 | 方法 | 功能 | 消费方 |
|:---|:---:|:---|:---|
| `/api/nouns?q={query}` | GET | 名词搜索（含消歧） | SearchBar |
| `/api/nouns/{id}` | GET | 名词详情 | GraphTooltip |
| `/api/nouns/{id}/graph?depth={n}` | GET | 关系图谱（分层） | GraphView |
| `/api/nouns/{id}/timeline` | GET | 演化时间轴 | TimelineView |
| `/api/events/graph-updates?noun_id={id}` | GET SSE | 图谱增量更新推送 | GraphView（SSE 订阅）|

### Data Flow

```
用户搜名词
  → GET /api/nouns?q=...              ← Wikidata API（结构化数据）
  → 如存在 Neo4j 缓存，直接返回        ← Neo4j（已缓存图谱）
  → 如不存在，触发后台构建过程：
       Wikidata 结构化数据 → 写入 Neo4j（即时）
       AI Web Search → LLM 提取实体/关系 → 写入 Neo4j（异步）
  → 返回基线图谱（5-10 个节点）
  → 后台完成后通过 SSE 推送增量节点和边
  → 前端 GraphView 动态添加节点

---

## Architecture Validation Results

### Coherence Validation ✅

| 检查项 | 状态 | 说明 |
|:---|:---:|:---|
| Next.js + FastAPI 双语言架构 | ✅ | 前端 SSR/流式，后端异步/WebSocket，各司其职 |
| Neo4j + 向量索引 | ✅ | MVP 不引入 Milvus，Neo4j 5.x 原生支持 SEARCH 子句 |
| D3.js + vis-timeline 可视化 | ✅ | 2D 力导向图 + 时间轴，MVP 无需 Three.js |
| REST + SSE 通信 | ✅ | REST 标准查询，SSE 图谱增量推送 |
| Redis + Neo4j 缓存 | ✅ | 全图缓存 Redis，节点级增量更新 Neo4j |
| Wikidata + AI Web Search | ✅ | 结构化+非结构化互补，统一入 Neo4j |
| Docker Compose 本地部署 | ✅ | 前端(Vercel)+后端(Docker)+Neo4j+Redis 编排清晰 |
| **neo4j-graphrag + Instructor** | ✅ | 检索层 + 结构化提取层各司其职，可切换提供商 |

### Requirements Coverage ✅

8 个 MVP 核心需求全部有架构支持：

| # | 需求 | 架构覆盖 |
|:---:|:---|---:|
| 1 | 名词搜索 | SearchBar → nouns.py → wikidata_repo.py |
| 2 | 关系图谱 | GraphView → graph.py → neo4j_repo.py |
| 3 | 演化时间轴 | TimelineView → timeline.py → neo4j_repo.py |
| 4 | AI 数据管道（无对话界面） | llm_client.py → extractor.py / web_search.py / summarizer.py |
| 5 | 人物优先入口 | 独立 `:Person` Label + GraphNode 区分渲染 |
| 6 | 多源数据融合 | wikidata_repo.py + ai/web_search.py → 统一入 Neo4j |
| 7 | 增量图谱展示 | SSE 端点 + GraphView 动态添加节点 |
| 8 | 置信度标注+可追溯 | Edge 模型 source/confidence/evidence → ConfidenceBadge |

### Implementation Readiness ✅

| 维度 | 状态 |
|:---|---:|
| 关键决策已记录含版本 | ✅ 全部完成 |
| 完整目录结构已定义 | ✅ 前端 + 后端完整树 |
| API 端点已定义 | ✅ 5 个核心端点 |
| 命名模式已建立 | ✅ API(snake_case) / Neo4j(Pascal+UPPER) / 代码(各自标准) |
| 数据模型已定义 | ✅ Node(含:Person) / Edge(含source/confidence/evidence) / GraphResponse |
| 错误处理格式已定 | ✅ 统一 error(code/message/status) |
| AI 框架已锁定 | ✅ neo4j-graphraph v1.18.0 + Instructor v1.15.4 |

### Architecture Completeness Checklist

**需求分析**
- [x] 项目上下文已深入分析
- [x] 规模和复杂度已评估
- [x] 技术约束已识别
- [x] 跨领域关注点已映射

**架构决策**
- [x] 关键决策已记录含版本
- [x] 技术栈已完全指定
- [x] 集成模式已定义
- [x] 性能考量已处理

**实现模式**
- [x] 命名规范已建立
- [x] 结构模式已定义
- [x] 通信模式已指定
- [x] 流程模式已记录

**项目结构**
- [x] 完整目录结构已定义
- [x] 组件边界已建立
- [x] 集成点已映射
- [x] 需求到结构映射已完成

### Architecture Readiness Assessment

**Overall Status:** ✅ **READY FOR IMPLEMENTATION**

**Confidence Level:** **High** — 所有组件经过多源验证

**Key Strengths:**
- 第一性原理驱动的架构简化——AI 作为管道引擎而非对话界面
- 人物优先原则在数据模型层面的原生支持
- 渐进式信息密度通过分层加载 + SSE 增量推送落地
- 双语言项目的一致命名规范防止 AI 代理冲突
- Neo4j + Instructor + neo4j-graphrag 各司其职的轻量组合
- 架构过渡路径清晰（模块化单体 → 微服务）

**Areas for Future Enhancement:**
- Phase 2 引入 Milvus 独立向量层
- Phase 2 增加用户系统 + 个人知识库
- Phase 2+ 引入 Three.js 3D 可视化
- 上线前配置 CI/CD 和 Prometheus 监控

**First Implementation Priority:**
```bash
# 1. 前端初始化
pnpm create next-app frontend --typescript --tailwind --eslint --react-compiler --src-dir --app --import-alias "@/*"

# 2. 后端搭建
mkdir -p backend/app/{api,services,repositories,models,ai,core}
touch backend/app/__init__.py
touch backend/app/{api,services,repositories,models,ai,core}/__init__.py
```
```
