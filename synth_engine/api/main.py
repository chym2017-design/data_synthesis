"""
FastAPI 入口

提供合成引擎的 REST API。
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from synth_engine.api.routes import synthesis, qc, config, template, files, system
from synth_engine.tenant import (
    bind_request_workspace,
    init_tenant_store,
    reset_request_workspace,
)

app = FastAPI(title="Synth Engine API", version="0.1.0")
init_tenant_store()

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
app.include_router(system.router, prefix="/api/system", tags=["用户与队列"])


@app.middleware("http")
async def workspace_middleware(request: Request, call_next):
    """除健康检查外，所有 API 请求都绑定到 Nginx 已认证用户的工作空间。"""
    if not request.url.path.startswith("/api/") or request.url.path == "/api/health":
        return await call_next(request)
    token = None
    try:
        token = bind_request_workspace(request)
        return await call_next(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    finally:
        if token is not None:
            reset_request_workspace(token)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/logout")
async def logout_basic_auth():
    """本地测试入口；生产环境由 Nginx 返回相同响应。"""
    return Response(
        status_code=401,
        headers={
            "WWW-Authenticate": 'Basic realm="Synth Engine"',
            "Clear-Site-Data": '"cache", "cookies", "storage"',
            "Cache-Control": "no-store",
        },
    )


# 静态文件服务（前端构建产物）
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
