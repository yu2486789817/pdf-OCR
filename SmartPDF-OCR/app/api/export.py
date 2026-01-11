"""
导出 API
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Literal, Optional
from pathlib import Path
import json

from app.core.file_manager import file_manager
from app.export.txt_export import TxtExporter
from app.export.docx_export import DocxExporter
from app.export.searchable_pdf import SearchablePDFCreator
from app.ocr.postprocess import ProcessedPage, Paragraph
from app.ocr.engine import OCRResult, OCRLine

router = APIRouter(prefix="/export", tags=["导出"])


class ExportRequest(BaseModel):
    """导出请求"""
    format: Literal["txt", "docx", "pdf", "md"] = "txt"
    include_page_numbers: bool = True
    title: Optional[str] = None
    use_ai_formatted: bool = False  # 是否使用 AI 增强后的文本


class ExportResponse(BaseModel):
    """导出响应"""
    task_id: str
    format: str
    filename: str
    message: str


def load_ocr_result(task_id: str) -> list:
    """加载 OCR 结果"""
    output_dir = file_manager.get_task_output_dir(task_id)
    result_file = output_dir / "ocr_result.json"
    
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="OCR 结果不存在")
    
    with open(result_file, "r", encoding="utf-8") as f:
        return json.load(f)


def convert_to_processed_pages(ocr_data: list, use_ai_formatted: bool = False) -> list:
    """将 OCR 数据转换为 ProcessedPage 对象"""
    pages = []
    for item in ocr_data:
        paragraphs = []
        
        # 如果启用 AI 增强且有 AI 结果，使用 AI 结果
        if use_ai_formatted and item.get("ai_formatted"):
            text = item.get("ai_formatted", "")
            paragraphs.append(Paragraph(text=text, lines=[]))
        elif "paragraphs" in item:
            for text in item["paragraphs"]:
                paragraphs.append(Paragraph(text=text, lines=[]))
        else:
            paragraphs.append(Paragraph(text=item.get("text", ""), lines=[]))
        
        page = ProcessedPage(
            page_num=item["page"],
            paragraphs=paragraphs
        )
        pages.append(page)
    
    return pages


@router.post("/{task_id}", response_model=ExportResponse)
async def export_result(task_id: str, request: ExportRequest):
    """
    导出 OCR 结果
    """
    # 检查任务
    files = file_manager.list_task_files(task_id)
    if not files["uploads"]:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 加载 OCR 结果
    ocr_data = load_ocr_result(task_id)
    pages = convert_to_processed_pages(ocr_data, use_ai_formatted=request.use_ai_formatted)
    
    # 准备输出目录
    output_dir = file_manager.get_task_output_dir(task_id)
    
    # 获取原始文件名
    original_name = Path(files["uploads"][0]).stem
    
    # 导出
    if request.format == "txt":
        output_file = output_dir / f"{original_name}_ocr.txt"
        exporter = TxtExporter(include_page_numbers=request.include_page_numbers)
        exporter.export(pages, output_file)
        
    elif request.format == "md":
        output_file = output_dir / f"{original_name}_ocr.md"
        # 直接使用 TxtExporter 导出内容，Markdown 格式主要体现在内容本身（如果是 AI 处理过的）
        # 如果需要更精细的 Markdown 结构（如页码作为二级标题），可以在这里定制
        with open(output_file, "w", encoding="utf-8") as f:
            if request.title:
                f.write(f"# {request.title}\n\n")
            
            for page in pages:
                if request.include_page_numbers:
                    f.write(f"\n## 第 {page.page_num} 页\n\n")
                
                for para in page.paragraphs:
                    f.write(f"{para.text}\n\n")
                    
    elif request.format == "docx":
        output_file = output_dir / f"{original_name}_ocr.docx"
        exporter = DocxExporter()
        exporter.export(
            pages, 
            output_file, 
            title=request.title,
            is_markdown=request.use_ai_formatted
        )
        
    elif request.format == "pdf":
        output_file = output_dir / f"{original_name}_searchable.pdf"
        
        # 获取原始 PDF 路径
        pdf_path = file_manager.get_task_upload_dir(task_id) / files["uploads"][0]
        
        # 创建 OCRResult 对象
        ocr_results = []
        for item in ocr_data:
            lines = []
            # 简化处理，创建空的 OCRLine
            result = OCRResult(page_num=item["page"], lines=lines)
            ocr_results.append(result)
        
        creator = SearchablePDFCreator()
        creator.create(pdf_path, ocr_results, output_file)
    
    else:
        raise HTTPException(status_code=400, detail="不支持的导出格式")
    
    return ExportResponse(
        task_id=task_id,
        format=request.format,
        filename=output_file.name,
        message="导出成功"
    )


@router.get("/{task_id}/download/{filename}")
async def download_file(task_id: str, filename: str):
    """
    下载导出文件
    """
    output_dir = file_manager.get_task_output_dir(task_id)
    file_path = output_dir / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 确定 MIME 类型
    suffix = file_path.suffix.lower()
    media_types = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf"
    }
    media_type = media_types.get(suffix, "application/octet-stream")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    )


@router.get("/{task_id}/files")
async def list_export_files(task_id: str):
    """
    列出所有导出文件
    """
    files = file_manager.list_task_files(task_id)
    return {
        "task_id": task_id,
        "files": files["outputs"]
    }
