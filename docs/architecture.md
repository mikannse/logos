# Logos — AI 名词知识图谱与演化平台

## 架构总览

### 技术栈

| 层 | 技术 | 版本 |
|---|---|---|
| 前端 | Next.js + TypeScript + Tailwind CSS | v16 |
| 后端 | FastAPI (Python) | v0.141 |
| 图数据库 | Neo4j (含向量索引) | 5.x |
| 缓存 | Redis | 7.x |
| AI | Anthropic/OpenAI + Instructor + neo4j-graphrag | — |

### 目录结构

```
logos/
├── docker-compose.yml       # 服务编排
├── frontend/                # Next.js 前端
│   ├── src/
│   │   ├── app/             # 页面路由
│   │   ├── components/      # React 组件
│   │   ├── lib/             # 工具函数
│   │   ├── hooks/           # React Hooks
│   │   └── types/           # TypeScript 类型
│   └── ...
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/             # 路由层
│   │   ├── services/        # 业务逻辑层
│   │   ├── repositories/    # 数据访问层
│   │   ├── models/          # Pydantic 模型
│   │   ├── ai/              # AI 数据管道
│   │   └── core/            # 基础设施
│   └── ...
└── docs/
    └── architecture.md      # 本文件
```

### API 端点

| 端点 | 方法 | 功能 |
|---|---|---|
| `/api/health` | GET | 健康检查 |
| `/api/nouns?q={query}` | GET | 名词搜索 |
| `/api/nouns/{id}` | GET | 名词详情 |
| `/api/nouns/{id}/graph?depth={n}` | GET | 关系图谱 |
| `/api/nouns/{id}/timeline` | GET | 演化时间轴 |

### API 规范

- 所有字段 `snake_case`
- 图谱端点返回 `{center, nodes[], edges[], depth, has_more}`
- 错误格式 `{error: {code, message, status, details}}`

### Neo4j 命名规范

- Node Label: PascalCase (`:Person`, `:Entity`, `:Event`)
- Relationship Type: UPPER_SNAKE_CASE (`:RELATES_TO`)
- 属性: camelCase (`entityName`)

### 后端三层架构

```
API (api/) → Service (services/) → Repository (repositories/)
```

- **API**: 路由、请求验证、响应格式化
- **Service**: 业务逻辑、多源数据融合
- **Repository**: 数据访问（Neo4j / Wikidata / Redis）
