"""
AI 增强 API
提供 OCR 结果的 AI 语义重排接口
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import asyncio

from app.ai.reformatter import AIReformatter
from app.config import settings
from app.core.file_manager import file_manager
from app.core.history_index import read_task_meta, write_task_meta

router = APIRouter(prefix="/ai", tags=["AI增强"])


class AIEnhanceRequest(BaseModel):
    """AI 增强请求"""
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    max_chunk_chars: Optional[int] = None


class AIEnhanceResponse(BaseModel):
    """AI 增强响应"""
    task_id: str
    status: str
    message: str


class AIStatusResponse(BaseModel):
    """AI 处理状态"""
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: float
    chunks_total: int
    chunks_processed: int
    message: str


# AI 处理状态存储
ai_status = {}


@router.post("/{task_id}/enhance", response_model=AIEnhanceResponse)
async def start_ai_enhance(task_id: str, options: AIEnhanceRequest):
    """
    启动 AI 语义重排
    
    需要先完成 OCR 识别
    """
    import json
    
    # 检查 OCR 结果是否存在
    output_dir = file_manager.get_task_output_dir(task_id)
    result_file = output_dir / "ocr_result.json"
    
    if not result_file.exists():
        raise HTTPException(status_code=400, detail="请先完成 OCR 识别")
    
    # 检查是否已在处理中
    if task_id in ai_status and ai_status[task_id]["status"] == "processing":
        raise HTTPException(status_code=400, detail="AI 增强正在处理中")
    
    # 读取 OCR 结果
    with open(result_file, "r", encoding="utf-8") as f:
        ocr_results = json.load(f)
    
    # 初始化状态
    ai_status[task_id] = {
        "status": "processing",
        "progress": 0,
        "chunks_total": 0,
        "chunks_processed": 0,
        "message": "正在启动 AI 增强..."
    }
    
    # 启动异步处理
    asyncio.create_task(_process_ai_enhance(
        task_id, 
        ocr_results, 
        options,
        result_file
    ))
    
    return AIEnhanceResponse(
        task_id=task_id,
        status="processing",
        message="AI 增强已启动"
    )


async def _process_ai_enhance(
    task_id: str, 
    ocr_results: List[dict], 
    options: AIEnhanceRequest,
    result_file
):
    """异步处理 AI 增强"""
    import json
    
    try:
        reformatter = AIReformatter(
            api_url=options.api_url or settings.AI_API_URL,
            api_key=options.api_key or settings.AI_API_KEY,
            model=options.model or settings.AI_MODEL,
            max_chunk_chars=options.max_chunk_chars or settings.AI_MAX_CHUNK_CHARS
        )
        
        # 统计总块数
        total_text = "\n\n".join([p.get("text", "") for p in ocr_results])
        chunks = reformatter._split_into_chunks(total_text)
        total_chunks = len(chunks)
        
        ai_status[task_id]["chunks_total"] = total_chunks
        ai_status[task_id]["message"] = f"正在处理 {total_chunks} 个文本块..."
        
        # 并行处理所有页面
        enhanced_results = await reformatter.reformat_pages(ocr_results)
        
        # 更新结果并统计成功/失败
        success_count = 0
        error_messages = []
        for i, result in enumerate(enhanced_results):
            ocr_results[i]["ai_formatted"] = result.get("ai_formatted", "")
            ocr_results[i]["ai_success"] = result.get("ai_success", False)
            if result.get("ai_success"):
                success_count += 1
            else:
                # 检查是否有错误信息
                if result.get("ai_errors"):
                    error_messages.extend(result.get("ai_errors", []))
        
        # 保存增强后的结果
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(ocr_results, f, ensure_ascii=False, indent=2)
        
        # 根据成功率决定状态
        if success_count == 0:
            # 全部失败
            error_msg = error_messages[0] if error_messages else "所有请求均失败，请检查 API 配置"
            ai_status[task_id] = {
                "status": "failed",
                "progress": 0,
                "chunks_total": total_chunks,
                "chunks_processed": 0,
                "message": f"AI 增强失败: {error_msg}"
            }
        elif success_count < len(enhanced_results):
            # 部分成功
            ai_status[task_id] = {
                "status": "completed",
                "progress": 100,
                "chunks_total": total_chunks,
                "chunks_processed": success_count,
                "message": f"部分完成 ({success_count}/{len(enhanced_results)} 页成功)"
            }
            write_task_meta(task_id, {"ai_enhanced": True})
        else:
            # 全部成功
            ai_status[task_id] = {
                "status": "completed",
                "progress": 100,
                "chunks_total": total_chunks,
                "chunks_processed": total_chunks,
                "message": "AI 增强完成"
            }
            write_task_meta(task_id, {"ai_enhanced": True})
        
    except Exception as e:
        ai_status[task_id] = {
            "status": "failed",
            "progress": 0,
            "chunks_total": 0,
            "chunks_processed": 0,
            "message": f"AI 增强失败: {str(e)}"
        }


@router.get("/{task_id}/status", response_model=AIStatusResponse)
async def get_ai_status(task_id: str):
    """获取 AI 增强状态"""
    if task_id not in ai_status:
        # 检查是否已完成
        meta = read_task_meta(task_id)
        if meta and meta.get("ai_enhanced"):
            return AIStatusResponse(
                task_id=task_id,
                status="completed",
                progress=100,
                chunks_total=0,
                chunks_processed=0,
                message="AI 增强已完成"
            )
        return AIStatusResponse(
            task_id=task_id,
            status="pending",
            progress=0,
            chunks_total=0,
            chunks_processed=0,
            message="未启动 AI 增强"
        )
    
    status = ai_status[task_id]
    return AIStatusResponse(
        task_id=task_id,
        status=status["status"],
        progress=status["progress"],
        chunks_total=status["chunks_total"],
        chunks_processed=status["chunks_processed"],
        message=status["message"]
    )


@router.get("/{task_id}/result")
async def get_ai_result(task_id: str):
    """获取 AI 增强后的结果"""
    import json
    
    output_dir = file_manager.get_task_output_dir(task_id)
    result_file = output_dir / "ocr_result.json"
    
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="结果不存在")
    
    with open(result_file, "r", encoding="utf-8") as f:
        results = json.load(f)
    
    # 返回增强后的文本
    enhanced_pages = []
    for page in results:
        enhanced_pages.append({
            "page": page.get("page"),
            "original": page.get("text", ""),
            "formatted": page.get("ai_formatted", page.get("text", "")),
            "ai_success": page.get("ai_success", False)
        })
    
    return {
        "task_id": task_id,
        "pages": enhanced_pages
    }
