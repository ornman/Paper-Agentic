# FastAPI 应用入口
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router

app = FastAPI(
    title="论文写作助手 API",
    version="1.0.0-mvp",
    description="基于 RAG 的学术写作辅助系统",
)

# ============ CORS 中间件（开发阶段允许所有来源）============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 注册路由 ============
app.include_router(api_router)


# ============ 全局异常处理 ============
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "code": 9001,
            "data": None,
            "message": f"内部错误：{str(exc)}",
        },
    )


# ============ 启动事件 ============
@app.on_event("startup")
async def startup():
    """启动时初始化数据库"""
    from app.repositories.sqlite_repo import get_engine
    get_engine()  # 触发建表
    print("数据库初始化完成")
