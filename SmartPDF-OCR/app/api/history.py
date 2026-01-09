"""
历史记录 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import json

from app.core.file_manager import file_manager
from app.core.history_index import read_task_meta

router = APIRouter(prefix="/history", tags=["历史"])


class HistoryItem(BaseModel):
    task_id: str
    filename: Optional[str] = None
    pdf_type: Optional[str] = None
    page_count: Optional[int] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    has_result: bool = False
    outputs: List[str] = []


@router.get("", response_model=List[HistoryItem])
async def list_history():
    task_ids = set()
    if file_manager.upload_dir.exists():
        task_ids.update([p.name for p in file_manager.upload_dir.iterdir() if p.is_dir()])
    if file_manager.output_dir.exists():
        task_ids.update([p.name for p in file_manager.output_dir.iterdir() if p.is_dir()])

    items: List[HistoryItem] = []
    for task_id in task_ids:
        files = file_manager.list_task_files(task_id)
        outputs = files["outputs"]
        has_result = "ocr_result.json" in outputs
        meta = read_task_meta(task_id) or {}
        filename = meta.get("filename") or (files["uploads"][0] if files["uploads"] else None)
        updated_at = meta.get("updated_at")

        if not updated_at:
            output_dir = file_manager.output_dir / task_id
            if output_dir.exists():
                updated_at = datetime.fromtimestamp(output_dir.stat().st_mtime).isoformat()

        items.append(
            HistoryItem(
                task_id=task_id,
                filename=filename,
                pdf_type=meta.get("pdf_type"),
                page_count=meta.get("page_count"),
                status=meta.get("status"),
                created_at=meta.get("created_at"),
                updated_at=updated_at,
                has_result=has_result,
                outputs=outputs
            )
        )

    items.sort(key=lambda x: x.updated_at or "", reverse=True)
    return items


@router.get("/{task_id}/result")
async def get_history_result(task_id: str):
    output_dir = file_manager.get_task_output_dir(task_id)
    result_file = output_dir / "ocr_result.json"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="OCR 结果不存在")
    with open(result_file, "r", encoding="utf-8") as f:
        return json.load(f)
