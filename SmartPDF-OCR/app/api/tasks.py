"""
任务管理 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.core.file_manager import file_manager

router = APIRouter(prefix="/tasks", tags=["任务管理"])


class TaskInfo(BaseModel):
    """任务信息"""
    task_id: str
    uploads: List[str]
    outputs: List[str]


class CleanupResponse(BaseModel):
    """清理响应"""
    cleaned_count: int
    message: str


@router.get("/{task_id}", response_model=TaskInfo)
async def get_task_info(task_id: str):
    """
    获取任务信息
    """
    files = file_manager.list_task_files(task_id)
    
    if not files["uploads"] and not files["outputs"]:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return TaskInfo(
        task_id=task_id,
        uploads=files["uploads"],
        outputs=files["outputs"]
    )


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """
    删除任务
    """
    files = file_manager.list_task_files(task_id)
    
    if not files["uploads"] and not files["outputs"]:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    file_manager.cleanup_task(task_id)
    
    return {"message": "任务已删除", "task_id": task_id}


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_old_tasks(max_age_hours: int = 24):
    """
    清理过期任务
    """
    if max_age_hours < 1:
        raise HTTPException(status_code=400, detail="max_age_hours 必须大于 0")
    
    cleaned = file_manager.cleanup_old_files(max_age_hours)
    
    return CleanupResponse(
        cleaned_count=cleaned,
        message=f"已清理 {cleaned} 个过期任务"
    )
