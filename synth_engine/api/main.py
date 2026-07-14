"""
FastAPI 入口

提供合成引擎的 REST API。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from synth_engine.api.routes import synthesis, qc, config, template, files

app = FastAPI(title="Synth Engine API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(synthesis.router, prefix="/api/synthesis", tags=["合成任务"])
app.include_router(qc.router, prefix="/api/qc", tags=["质检任务"])
app.include_router(config.router, prefix="/api/config", tags=["配置管理"])
app.include_router(template.router, prefix="/api/templates", tags=["模板管理"])
app.include_router(files.router, prefix="/api/files", tags=["结果文件"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# 静态文件服务（前端构建产物）
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
