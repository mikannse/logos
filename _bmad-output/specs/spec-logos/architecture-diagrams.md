# Architecture Diagrams

> 本文件记录 Logos 的系统架构图。完整架构决策见 [../../../architecture.md](architecture.md)。

## 系统架构总览

```
用户搜索名词
  → GET /api/nouns?q=...              ← Wikidata API（结构化数据）
  → 如存在 Neo4j 缓存，直接返回        ← Neo4j（已缓存图谱）
  → 如不存在，触发后台构建过程：
       Wikidata 结构化数据 → 写入 Neo4j（即时）
       AI Web Search → LLM 提取实体/关系 → 写入 Neo4j（异步）
  → 返回基线图谱（5–10 个节点）
  → 后台完成后通过 SSE 推送增量节点和边
  → 前端 GraphView 动态添加节点
```

## 技术栈全景

| 层次 | 技术 | 说明 |
|:---|:---|:---|
| 前端框架 | Next.js v16 + TypeScript | App Router + Server Components，SSR 图谱初始数据 |
| 图谱可视化 | D3.js force-graph (v7) | 力导向图，缩放 / 拖拽 / 悬停 |
| 时间轴 | vis-timeline | 交互时间轴，滑块联动 |
| 后端框架 | FastAPI (Python 3.12+) | 异步原生，WebSocket / SSE 支持 |
| 图数据库 | Neo4j 5.x（含向量索引） | 实体 + 关系存储，语义搜索 SEARCH 子句 |
| AI 管道 | LLM API (Claude / GPT) | 实体提取、搜索结构化、摘要生成 |
| 缓存 | Redis | 图谱查询缓存、LLM 响应缓存 |
| 部署 | Docker Compose（本地） | 前端 Vercel / 后端 Docker |

## API 端点

| 端点 | 方法 | 功能 |
|:---|:---:|:---|
| `/api/nouns?q={query}` | GET | 名词搜索（含消歧） |
| `/api/nouns/{id}` | GET | 名词详情 |
| `/api/nouns/{id}/graph?depth={n}` | GET | 关系图谱（分层，默认 1 跳，最多 3 跳）|
| `/api/nouns/{id}/timeline` | GET | 演化时间轴 |
| `/api/events/graph-updates?noun_id={id}` | GET SSE | 图谱增量更新推送 |

## API 响应格式

**图谱端点：**
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

**错误响应：**
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

## Neo4j 命名约定

| 元素 | 惯例 | 例子 |
|:---|:---|:---|
| Node Label | PascalCase | `:Person`, `:Entity`, `:Event` |
| Relationship Type | UPPER_SNAKE_CASE | `:RELATES_TO`, `:FOUNDED_BY` |
| 属性名 | camelCase | `entityName`, `confidenceScore` |

## 代码命名约定

| 元素 | TypeScript（前端） | Python（后端） |
|:---|:---|:---|
| 文件名 | `kebab-case.tsx` | `snake_case.py` |
| 组件名 | `PascalCase` | — |
| 函数 / 方法 | `camelCase` | `snake_case` |
| 类名 | `PascalCase` | `PascalCase` |
| 常量 | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` |

## 三层检索架构（Phase 2 AI 对话）

> *MVP 阶段 LLM 仅用于数据管道，用户可见的 AI 对话推迟至 Phase 2。以下三层检索架构为 Phase 2 预留。*

| 层次 | 检索源 | 触发条件 | 响应时间 |
|:---|:---|:---|:---:|
| L1: 图遍历 | Neo4j Cypher | 精确实体匹配 | < 100ms |
| L2: 语义搜索 | Neo4j 向量索引 (SEARCH) | 模糊匹配 | < 500ms |
| L3: LLM 推理 | Claude / GPT (GraphRAG) | 复杂推理 | 1–10s 流式 |

## 后端模块结构

```
backend/
├── app/
│   ├── main.py                   # FastAPI 入口
│   ├── config.py                 # 环境变量管理
│   ├── api/                      # 路由层
│   │   ├── nouns.py              # /api/nouns
│   │   ├── graph.py              # /api/graph
│   │   ├── timeline.py           # /api/timeline
│   │   └── sse.py                # /api/events
│   ├── services/                 # 业务逻辑层
│   │   ├── graph_service.py
│   │   ├── timeline_service.py
│   │   └── search_service.py
│   ├── repositories/             # 数据访问层
│   │   ├── neo4j_repo.py
│   │   └── wikidata_repo.py
│   ├── models/                   # Pydantic 模型
│   │   ├── noun.py
│   │   ├── relation.py
│   │   ├── graph.py
│   │   └── timeline.py
│   ├── ai/                       # AI 数据管道
│   │   ├── llm_client.py         # LLM 统一客户端（Instructor 封装）
│   │   ├── extractor.py          # 实体 / 关系提取
│   │   ├── web_search.py         # AI Web Search 工具
│   │   └── summarizer.py         # 知识点摘要生成
│   └── core/                     # 基础设施
│       ├── cache.py              # Redis 缓存封装
│       ├── neo4j_client.py       # Neo4j 驱动
│       └── exceptions.py         # 全局异常定义
└── tests/
```

## 三层缓存策略

| 缓存层 | 缓存内容 | TTL | 实现 |
|:---|:---|:---:|:---|
| L1: 浏览器 | 静态元数据、图谱快照 | 1h | Next.js `force-cache` |
| L2: Redis | 图谱查询、LLM 响应、语义相似 | 30m–6h | redis-py + FastAPI 缓存装饰器 |
| L3: 数据库 | Neo4j 热数据 | 持久化 | Neo4j 内存缓存 |
