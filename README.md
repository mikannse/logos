# Logos — AI 名词知识图谱与演化平台

给你的好奇心装一张知识地图。

搜索任意名词，自动构建关系图谱与演化时间轴，终结碎片知识时代的 17 个标签页。

## 技术栈

- **前端**: Next.js v16 + TypeScript + Tailwind CSS + D3.js + vis-timeline
- **后端**: FastAPI (Python 异步)
- **数据库**: Neo4j 5.x (图数据库, 含原生向量索引)
- **缓存**: Redis 7.x
- **AI**: Anthropic/OpenAI (通过 Instructor 封装) + neo4j-graphrag
- **编排**: Docker Compose

## 快速开始

```bash
# 启动所有服务
docker compose up

# 前端: http://localhost:3000
# 后端: http://localhost:8000
# Neo4j Browser: http://localhost:7474
```

## 项目结构

```
logos/
├── frontend/          # Next.js 前端
├── backend/           # FastAPI 后端 (三层架构)
├── docker-compose.yml # 服务编排
└── docs/              # 文档
```

## 开发指南

### 前端开发
```bash
cd frontend
pnpm install
pnpm dev
```

### 后端开发
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
