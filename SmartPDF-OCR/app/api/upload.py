"""
文件上传 API
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.file_manager import file_manager
from app.core.pdf_detector import get_pdf_info, PDFInfo
from app.core.history_index import write_task_meta

router = APIRouter(prefix="/upload", tags=["上传"])


class UploadResponse(BaseModel):
    """上传响应"""
    task_id: str
    filename: str
    file_size: int
    pdf_type: str
    page_count: int
    message: str


@router.post("", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    上传 PDF 文件
    
    - 自动生成任务 ID
    - 校验文件格式
    - 检测 PDF 类型
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
    
    # 检测 PDF 类型
    try:
        pdf_info = get_pdf_info(file_path)
    except Exception as e:
        file_manager.cleanup_task(task_id)
        raise HTTPException(status_code=400, detail=f"PDF 解析失败: {str(e)}")
    
    write_task_meta(
        task_id,
        {
            "filename": file.filename,
            "file_size": len(content),
            "pdf_type": pdf_info.pdf_type,
            "page_count": pdf_info.page_count,
            "status": "uploaded",
            "created_at": datetime.utcnow().isoformat()
        }
    )

    return UploadResponse(
        task_id=task_id,
        filename=file.filename,
        file_size=len(content),
        pdf_type=pdf_info.pdf_type,
        page_count=pdf_info.page_count,
        message="上传成功"
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
