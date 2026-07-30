from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.nouns import router as nouns_router
from app.api.graph import router as graph_router
from app.api.timeline import router as timeline_router

app = FastAPI(
    title="Logos API",
    description="AI 名词知识图谱与演化平台后端 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(nouns_router, prefix="/api")
app.include_router(graph_router, prefix="/api")
app.include_router(timeline_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
