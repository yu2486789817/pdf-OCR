"""
OCR 识别 API
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
from datetime import datetime

from app.core.file_manager import file_manager
from app.core.pdf_detector import PDFDetector
from app.core.pdf_renderer import PDFRenderer
from app.ocr.engine import OCREngine
from app.ocr.postprocess import PostProcessor
from app.preprocess import denoise, binarize, deskew
from app.core.history_index import write_task_meta
from app.config import settings

router = APIRouter(prefix="/ocr", tags=["OCR"])

# 任务状态存储（生产环境建议使用 Redis）
task_status: Dict[str, Dict[str, Any]] = {}


class OCRRequest(BaseModel):
    """OCR 请求参数"""
    preprocess: bool = True  # 是否预处理
    denoise: bool = True
    binarize: bool = False
    deskew: bool = True
    dpi: int = 300
    pages: Optional[List[int]] = None  # 1-based 指定页码
    ignore_top: int = 0      # 忽略顶部百分比 (0-100)
    ignore_bottom: int = 0   # 忽略底部百分比
    ignore_left: int = 0     # 忽略左侧百分比
    ignore_right: int = 0    # 忽略右侧百分比


class OCRResponse(BaseModel):
    """OCR 响应"""
    task_id: str
    status: str
    message: str


class OCRStatusResponse(BaseModel):
    """OCR 状态响应"""
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: float
    current_page: int
    total_pages: int
    message: str
    result: Optional[Dict] = None


def _normalize_pages(pages: Optional[List[int]], page_count: int) -> List[int]:
    if not pages:
        return list(range(page_count))
    invalid = [p for p in pages if p < 1 or p > page_count]
    if invalid:
        raise ValueError(f"无效页码: {invalid}")
    return [p - 1 for p in sorted(set(pages))]


def process_ocr_task(
    task_id: str,
    pdf_path: Path,
    options: OCRRequest
):
    """执行 OCR 后台任务"""
    try:
        # 初始化状态
        task_status[task_id] = {
            "status": "processing",
            "progress": 0,
            "current_page": 0,
            "total_pages": 0,
            "message": "正在初始化...",
            "result": None
        }

        # 检测 PDF 类型
        detector = PDFDetector()
        pdf_info = detector.detect(pdf_path)

        # 标准化页码（1-based）
        target_pages = _normalize_pages(options.pages, pdf_info.page_count)

        task_status[task_id]["total_pages"] = len(target_pages)
        task_status[task_id]["message"] = f"PDF 类型: {pdf_info.pdf_type}"
        write_task_meta(
            task_id,
            {
                "status": "processing",
                "pdf_type": pdf_info.pdf_type,
                "page_count": pdf_info.page_count,
                "pages_selected": [p + 1 for p in target_pages]
            }
        )

        # 初始化处理器
        renderer = PDFRenderer(dpi=options.dpi)
        ocr_engine = OCREngine()
        post_processor = PostProcessor()
        
        # 应用边距过滤设置
        post_processor.ignore_top = options.ignore_top
        post_processor.ignore_bottom = options.ignore_bottom
        post_processor.ignore_left = options.ignore_left
        post_processor.ignore_right = options.ignore_right

        ocr_results = []
        processed_pages = []  # 记录处理后的页面对象，用于批量后处理

        # 纯文字 PDF 直接提取文本，无需 OCR
        if pdf_info.pdf_type == "text":
            task_status[task_id]["message"] = "纯文字 PDF，直接提取文本..."
            for idx, page_num in enumerate(target_pages):
                task_status[task_id]["current_page"] = idx + 1
                task_status[task_id]["message"] = f"正在提取第 {idx + 1}/{len(target_pages)} 页..."
                task_status[task_id]["progress"] = (idx / max(len(target_pages), 1)) * 100
                text = detector.extract_text(pdf_path, page_num)
                ocr_results.append(
                    {
                        "page": page_num,
                        "text": text,
                        "confidence": 1.0,
                        "method": "extract"
                    }
                )

            output_dir = file_manager.get_task_output_dir(task_id)
            result_file = output_dir / "ocr_result.json"
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(ocr_results, f, ensure_ascii=False, indent=2)

            combined = "\n\n".join([item.get("text", "") for item in ocr_results])
            task_status[task_id]["status"] = "completed"
            task_status[task_id]["progress"] = 100
            task_status[task_id]["message"] = "OCR 处理完成"
            task_status[task_id]["result"] = {
                "type": "text",
                "content": combined,
                "pages": [
                    {"page": item["page"], "text": item["text"], "confidence": 1.0}
                    for item in ocr_results
                ]
            }
            write_task_meta(
                task_id,
                {
                    "status": "completed",
                    "result_type": "text",
                    "pages_processed": len(ocr_results),
                    "updated_at": datetime.utcnow().isoformat()
                }
            )
            return

        # 图片型/混合型 PDF 需要 OCR
        # 图片型/混合型 PDF 需要 OCR
        
        from concurrent.futures import ThreadPoolExecutor
        import queue

        # 定义预处理函数 (CPU 密集型)
        def preprocess_page(p_num):
            try:
                # 渲染
                rend = renderer.render_page(pdf_path, p_num)
                img = rend.image
                # 预处理
                if options.preprocess:
                    if options.denoise:
                        img = denoise(img, method="gaussian")
                    if options.deskew:
                        img, _ = deskew(img)
                    if options.binarize:
                        img = binarize(img, method="otsu")
                return p_num, img, None
            except Exception as ex:
                return p_num, None, ex

        # 使用线程池进行预取 (Pre-fetching)
        # 限制最大并发数为 3，避免内存爆炸
        max_workers = 3
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 初始化任务队列
            future_dict = {}
            # 先提交前几个任务
            for i in range(min(max_workers, len(target_pages))):
                p_num = target_pages[i]
                future_dict[p_num] = executor.submit(preprocess_page, p_num)
            
            next_submit_idx = max_workers

            for idx, page_num in enumerate(target_pages):
                task_status[task_id]["current_page"] = idx + 1
                task_status[task_id]["message"] = f"正在识别第 {idx + 1}/{len(target_pages)} 页..."
                task_status[task_id]["progress"] = (idx / max(len(target_pages), 1)) * 100

                # 判断不需要 OCR 的情况
                need_ocr = page_num in pdf_info.image_pages
                if not need_ocr:
                    # 纯文本页直接提取
                    text = detector.extract_text(pdf_path, page_num)
                    ocr_results.append({
                        "page": page_num,
                        "text": text,
                        "confidence": 1.0,
                        "method": "extract"
                    })
                    # 如果该页原本在任务队列里（虽然不太可能，逻辑上分开的），需要清理
                    if page_num in future_dict:
                        future_dict[page_num].cancel()
                        del future_dict[page_num]
                    
                    # 提交下一个任务以保持流水线满载
                    if next_submit_idx < len(target_pages):
                        next_p = target_pages[next_submit_idx]
                        future_dict[next_p] = executor.submit(preprocess_page, next_p)
                        next_submit_idx += 1
                    continue

                # 获取预处理结果
                if page_num not in future_dict:
                     # 如果还没提交（逻辑上不应发生，除非 worker 极少），现在提交
                     future_dict[page_num] = executor.submit(preprocess_page, page_num)
                
                # 等待当前页的预处理完成
                _, image, error = future_dict[page_num].result()
                del future_dict[page_num] # 释放引用
                
                # 立即提交下一个任务，保持 pipeline 流动
                if next_submit_idx < len(target_pages):
                    next_p = target_pages[next_submit_idx]
                    future_dict[next_p] = executor.submit(preprocess_page, next_p)
                    next_submit_idx += 1

                if error:
                    print(f"预处理失败 (Page {page_num}): {error}")
                    # 降级处理或者跳过
                    ocr_results.append({
                        "page": page_num,
                        "text": "",
                        "confidence": 0.0,
                        "error": str(error)
                    })
                    continue

                # OCR 识别 (GPU Bound - Main Thread)
                ocr_result = ocr_engine.recognize(image, page_num)

                # 后处理 (CPU Bound - 可以异步但这里简单的先串行)
                processed = post_processor.process(ocr_result)
                processed_pages.append(processed)

                ocr_results.append(
                    {
                        "page": page_num,
                        "text": processed.text,
                        "confidence": ocr_result.avg_confidence,
                        "paragraphs": [p.text for p in processed.paragraphs],
                        "method": "ocr"
                    }
                )

        # 批量后处理：移除重复的页眉页脚
        if settings.REMOVE_HEADER_FOOTER and processed_pages:
            final_pages = post_processor._remove_headers_footers(processed_pages)
            # 同步回 ocr_results
            for idx, page in enumerate(final_pages):
                if idx < len(ocr_results):
                    ocr_results[idx]["text"] = page.text
                    ocr_results[idx]["paragraphs"] = [p.text for p in page.paragraphs]
                    if page.header:
                        ocr_results[idx]["header"] = page.header
                    if page.footer:
                        ocr_results[idx]["footer"] = page.footer

        # 保存结果
        output_dir = file_manager.get_task_output_dir(task_id)
        result_file = output_dir / "ocr_result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(ocr_results, f, ensure_ascii=False, indent=2)

        # 更新状态
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["progress"] = 100
        task_status[task_id]["message"] = "OCR 处理完成"
        task_status[task_id]["result"] = {
            "type": "ocr",
            "pages": ocr_results
        }
        write_task_meta(
            task_id,
            {
                "status": "completed",
                "result_type": "ocr",
                "pages_processed": len(ocr_results),
                "updated_at": datetime.utcnow().isoformat()
            }
        )

    except Exception as e:
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["message"] = f"处理失败: {str(e)}"
        write_task_meta(
            task_id,
            {
                "status": "failed",
                "error": str(e),
                "updated_at": datetime.utcnow().isoformat()
            }
        )


@router.post("/{task_id}", response_model=OCRResponse)
async def start_ocr(
    task_id: str,
    options: OCRRequest,
    background_tasks: BackgroundTasks
):
    """
    启动 OCR 任务
    """
    # 检查任务是否存在
    files = file_manager.list_task_files(task_id)
    if not files["uploads"]:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 获取 PDF 文件路径
    pdf_filename = files["uploads"][0]
    pdf_path = file_manager.get_task_upload_dir(task_id) / pdf_filename

    # 检查是否正在处理中
    if task_id in task_status and task_status[task_id]["status"] == "processing":
        raise HTTPException(status_code=400, detail="任务正在处理中")

    # 添加后台任务
    background_tasks.add_task(process_ocr_task, task_id, pdf_path, options)

    return OCRResponse(
        task_id=task_id,
        status="pending",
        message="OCR 任务已启动"
    )


@router.get("/{task_id}/status", response_model=OCRStatusResponse)
async def get_ocr_status(task_id: str):
    """
    查询 OCR 任务状态
    """
    if task_id not in task_status:
        # 检查任务是否存在
        files = file_manager.list_task_files(task_id)
        if not files["uploads"]:
            raise HTTPException(status_code=404, detail="任务不存在")

        return OCRStatusResponse(
            task_id=task_id,
            status="pending",
            progress=0,
            current_page=0,
            total_pages=0,
            message="等待处理"
        )

    status = task_status[task_id]
    return OCRStatusResponse(
        task_id=task_id,
        status=status["status"],
        progress=status["progress"],
        current_page=status["current_page"],
        total_pages=status["total_pages"],
        message=status["message"],
        result=status.get("result")
    )


@router.get("/{task_id}/result")
async def get_ocr_result(task_id: str):
    """获取 OCR 结果"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")

    status = task_status[task_id]

    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="OCR 尚未完成")

    return status["result"]
