"""
OCR ?? API
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

router = APIRouter(prefix="/ocr", tags=["OCR"])

# ??????????????????? Redis?
task_status: Dict[str, Dict[str, Any]] = {}


class OCRRequest(BaseModel):
    """OCR ????"""
    preprocess: bool = True  # ?????
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
    """OCR ??"""
    task_id: str
    status: str
    message: str


class OCRStatusResponse(BaseModel):
    """OCR ????"""
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
        raise ValueError(f"??????: {invalid}")
    return [p - 1 for p in sorted(set(pages))]


def process_ocr_task(
    task_id: str,
    pdf_path: Path,
    options: OCRRequest
):
    """?? OCR ????"""
    try:
        # ????
        task_status[task_id] = {
            "status": "processing",
            "progress": 0,
            "current_page": 0,
            "total_pages": 0,
            "message": "?????...",
            "result": None
        }

        # ?? PDF ??
        detector = PDFDetector()
        pdf_info = detector.detect(pdf_path)

        # ???????1-based?
        target_pages = _normalize_pages(options.pages, pdf_info.page_count)

        task_status[task_id]["total_pages"] = len(target_pages)
        task_status[task_id]["message"] = f"PDF ??: {pdf_info.pdf_type}"
        write_task_meta(
            task_id,
            {
                "status": "processing",
                "pdf_type": pdf_info.pdf_type,
                "page_count": pdf_info.page_count,
                "pages_selected": [p + 1 for p in target_pages]
            }
        )

        # ?????
        renderer = PDFRenderer(dpi=options.dpi)
        ocr_engine = OCREngine()
        post_processor = PostProcessor()
        
        # 应用边距过滤设置
        post_processor.ignore_top = options.ignore_top
        post_processor.ignore_bottom = options.ignore_bottom
        post_processor.ignore_left = options.ignore_left
        post_processor.ignore_right = options.ignore_right

        ocr_results = []
        processed_pages = [] # 记录处理后的页面对象，用于批量后处理

        # ??? PDF ??????????????
        if pdf_info.pdf_type == "text":
            task_status[task_id]["message"] = "??? PDF???????..."
            for idx, page_num in enumerate(target_pages):
                task_status[task_id]["current_page"] = idx + 1
                task_status[task_id]["message"] = f"????? {idx + 1}/{len(target_pages)} ?..."
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
            task_status[task_id]["message"] = "OCR ????"
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

        # ???/??? PDF ?? OCR
        for idx, page_num in enumerate(target_pages):
            task_status[task_id]["current_page"] = idx + 1
            task_status[task_id]["message"] = f"????? {idx + 1}/{len(target_pages)} ?..."
            task_status[task_id]["progress"] = (idx / max(len(target_pages), 1)) * 100

            # ?????? OCR
            need_ocr = page_num in pdf_info.image_pages

            if not need_ocr:
                # ???????
                text = detector.extract_text(pdf_path, page_num)
                ocr_results.append(
                    {
                        "page": page_num,
                        "text": text,
                        "confidence": 1.0,
                        "method": "extract"
                    }
                )
                continue

            # ????
            rendered = renderer.render_page(pdf_path, page_num)
            image = rendered.image

            # ???
            if options.preprocess:
                if options.denoise:
                    image = denoise(image, method="gaussian")
                if options.deskew:
                    image, angle = deskew(image)
                if options.binarize:
                    image = binarize(image, method="otsu")

            # OCR ??
            ocr_result = ocr_engine.recognize(image, page_num)

            # ???
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
        if settings.REMOVE_HEADER_FOOTER:
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

        # ????
        output_dir = file_manager.get_task_output_dir(task_id)
        result_file = output_dir / "ocr_result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(ocr_results, f, ensure_ascii=False, indent=2)

        # ????
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["progress"] = 100
        task_status[task_id]["message"] = "OCR ????"
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
        task_status[task_id]["message"] = f"????: {str(e)}"
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
    ?? OCR ??
    """
    # ????
    files = file_manager.list_task_files(task_id)
    if not files["uploads"]:
        raise HTTPException(status_code=404, detail="?????")

    # ?? PDF ????
    pdf_filename = files["uploads"][0]
    pdf_path = file_manager.get_task_upload_dir(task_id) / pdf_filename

    # ????????
    if task_id in task_status and task_status[task_id]["status"] == "processing":
        raise HTTPException(status_code=400, detail="???????")

    # ??????
    background_tasks.add_task(process_ocr_task, task_id, pdf_path, options)

    return OCRResponse(
        task_id=task_id,
        status="pending",
        message="OCR ?????"
    )


@router.get("/{task_id}/status", response_model=OCRStatusResponse)
async def get_ocr_status(task_id: str):
    """
    ?? OCR ????
    """
    if task_id not in task_status:
        # ????????
        files = file_manager.list_task_files(task_id)
        if not files["uploads"]:
            raise HTTPException(status_code=404, detail="?????")

        return OCRStatusResponse(
            task_id=task_id,
            status="pending",
            progress=0,
            current_page=0,
            total_pages=0,
            message="??????"
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
    """?? OCR ??"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="?????")

    status = task_status[task_id]

    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="OCR ?????")

    return status["result"]
