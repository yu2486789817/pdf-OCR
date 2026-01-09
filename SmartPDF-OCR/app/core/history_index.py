"""
历史记录索引
维护每个任务的 meta.json，便于前端拉取历史列表
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from app.core.file_manager import file_manager


def _meta_path(task_id: str) -> Path:
    output_dir = file_manager.get_task_output_dir(task_id)
    return output_dir / "meta.json"


def read_task_meta(task_id: str) -> Optional[Dict[str, Any]]:
    path = _meta_path(task_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_task_meta(task_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    path = _meta_path(task_id)
    meta: Dict[str, Any] = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    meta.update(data)
    meta["task_id"] = task_id
    now = datetime.utcnow().isoformat()
    meta["updated_at"] = now
    if "created_at" not in meta:
        meta["created_at"] = now
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta
