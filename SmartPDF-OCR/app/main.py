"""
FastAPI 应用入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager
from app.config import settings
from app.api import upload, ocr, export, tasks, history, ai

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期工作：启动时预热 OCR 引擎"""
    if settings.OCR_WARMUP:
        try:
            from app.ocr.engine import OCREngine
            # 初始化并预热
            engine = OCREngine()
            engine.warmup()
        except Exception as e:
            print(f"启动预热失败: {e}")
    yield

app = FastAPI(
    title="SmartPDF-OCR",
    description="面向中文场景的智能 PDF OCR 系统",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件（用于下载导出的文件）
if settings.OUTPUT_DIR and settings.OUTPUT_DIR.exists():
    app.mount("/files", StaticFiles(directory=settings.OUTPUT_DIR), name="files")

# 注册路由
app.include_router(upload.router, prefix="/api")
app.include_router(ocr.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(ai.router, prefix="/api")


@app.get("/")
async def root():
    """健康检查"""
    return {
        "app": "SmartPDF-OCR",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
