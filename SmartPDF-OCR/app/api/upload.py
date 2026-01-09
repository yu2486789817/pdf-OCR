"""
文件上传 API
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import threading

from app.core.file_manager import file_manager
from app.core.pdf_detector import get_pdf_info, PDFInfo
from app.core.history_index import write_task_meta

router = APIRouter(prefix="/upload", tags=["上传"])

# 解析状态存储
parse_status: Dict[str, Dict[str, Any]] = {}


class UploadResponse(BaseModel):
    """上传响应"""
    task_id: str
    filename: str
    file_size: int
    message: str
    status: str  # uploaded, parsing, ready, failed


class ParseStatusResponse(BaseModel):
    """解析状态响应"""
    task_id: str
    status: str  # parsing, ready, failed
    pdf_type: Optional[str] = None
    page_count: Optional[int] = None
    message: str
    progress: float = 0


def _parse_pdf_background(task_id: str, file_path: str, filename: str, file_size: int):
    """后台解析 PDF（在线程池中执行）"""
    try:
        parse_status[task_id] = {
            "status": "parsing",
            "message": "正在分析 PDF 结构...",
            "progress": 10
        }
        
        pdf_info = get_pdf_info(file_path)
        
        parse_status[task_id] = {
            "status": "ready",
            "message": "解析完成",
            "progress": 100,
            "pdf_type": pdf_info.pdf_type,
            "page_count": pdf_info.page_count
        }
        
        write_task_meta(
            task_id,
            {
                "filename": filename,
                "file_size": file_size,
                "pdf_type": pdf_info.pdf_type,
                "page_count": pdf_info.page_count,
                "status": "ready",
                "created_at": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        parse_status[task_id] = {
            "status": "failed",
            "message": f"解析失败: {str(e)}",
            "progress": 0
        }
        write_task_meta(
            task_id,
            {
                "status": "failed",
                "error": str(e)
            }
        )


@router.post("", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    上传 PDF 文件（异步模式）
    
    - 上传后立即返回任务 ID
    - PDF 解析在后台执行
    - 通过 /upload/{task_id}/parse-status 轮询解析状态
    """
    # 检查文件类型
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")
    
    # 生成任务 ID
    task_id = file_manager.generate_task_id()
    
    # 读取文件内容
    content = await file.read()
    
    # 检查文件大小
    if len(content) > file_manager.max_upload_size:
        max_mb = file_manager.max_upload_size / (1024 * 1024)
        raise HTTPException(
            status_code=400, 
            detail=f"文件过大，最大支持 {max_mb:.0f}MB"
        )
    
    # 保存文件
    file_path = file_manager.save_upload_file(content, file.filename, task_id)
    
    # 校验 PDF
    is_valid, error = file_manager.validate_pdf(file_path)
    if not is_valid:
        file_manager.cleanup_task(task_id)
        raise HTTPException(status_code=400, detail=error)
    
    # 初始化解析状态
    parse_status[task_id] = {
        "status": "parsing",
        "message": "已接收文件，正在排队解析...",
        "progress": 0
    }
    
    # 后台线程解析 PDF
    thread = threading.Thread(
        target=_parse_pdf_background,
        args=(task_id, str(file_path), file.filename, len(content))
    )
    thread.start()
    
    return UploadResponse(
        task_id=task_id,
        filename=file.filename,
        file_size=len(content),
        message="文件已上传，正在解析中...",
        status="parsing"
    )


@router.get("/{task_id}/parse-status", response_model=ParseStatusResponse)
async def get_parse_status(task_id: str):
    """获取 PDF 解析状态"""
    if task_id not in parse_status:
        # 尝试从 meta 文件读取
        from app.core.history_index import read_task_meta
        meta = read_task_meta(task_id)
        if meta and meta.get("status") == "ready":
            return ParseStatusResponse(
                task_id=task_id,
                status="ready",
                pdf_type=meta.get("pdf_type"),
                page_count=meta.get("page_count"),
                message="解析完成",
                progress=100
            )
        elif meta and meta.get("status") == "failed":
            return ParseStatusResponse(
                task_id=task_id,
                status="failed",
                message=meta.get("error", "解析失败"),
                progress=0
            )
        raise HTTPException(status_code=404, detail="任务不存在")
    
    status = parse_status[task_id]
    return ParseStatusResponse(
        task_id=task_id,
        status=status["status"],
        pdf_type=status.get("pdf_type"),
        page_count=status.get("page_count"),
        message=status["message"],
        progress=status.get("progress", 0)
    )


@router.get("/{task_id}/info")
async def get_upload_info(task_id: str):
    """获取上传文件信息"""
    files = file_manager.list_task_files(task_id)
    
    if not files["uploads"]:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {
        "task_id": task_id,
        "files": files
    }
