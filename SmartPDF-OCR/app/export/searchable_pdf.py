"""
可搜索 PDF 生成模块
在原 PDF 上叠加透明文本层，使其可搜索
"""

from pathlib import Path
from typing import List, Union, Optional
import fitz  # PyMuPDF

from app.ocr.engine import OCRResult, OCRLine
from app.config import settings


class SearchablePDFCreator:
    """可搜索 PDF 生成器"""
    
    def __init__(
        self,
        font_name: str = None,
        text_opacity: float = 0.0  # 透明文本
    ):
        """
        初始化生成器
        
        Args:
            font_name: 字体名称
            text_opacity: 文本不透明度 (0=完全透明, 1=完全不透明)
        """
        self.font_name = font_name or settings.SEARCHABLE_PDF_FONT
        self.text_opacity = text_opacity
    
    def create(
        self,
        pdf_path: Union[str, Path],
        ocr_results: List[OCRResult],
        output_path: Union[str, Path]
    ) -> Path:
        """
        创建可搜索 PDF
        
        Args:
            pdf_path: 原始 PDF 路径
            ocr_results: OCR 结果列表
            output_path: 输出文件路径
            
        Returns:
            输出文件路径
        """
        pdf_path = Path(pdf_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 打开原始 PDF
        doc = fitz.open(pdf_path)
        
        # 为每页添加文本层
        for ocr_result in ocr_results:
            page_num = ocr_result.page_num
            
            if page_num >= len(doc):
                continue
            
            page = doc[page_num]
            self._add_text_layer(page, ocr_result)
        
        # 保存
        doc.save(str(output_path))
        doc.close()
        
        return output_path
    
    def _add_text_layer(self, page: fitz.Page, ocr_result: OCRResult) -> None:
        """为页面添加文本层"""
        # 获取页面尺寸
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        
        # 获取渲染时的 DPI（假设为 300）
        render_dpi = settings.DEFAULT_DPI
        scale_factor = 72 / render_dpi  # PDF 默认 72 DPI
        
        for line in ocr_result.lines:
            try:
                # 计算文本位置（需要从图像坐标转换为 PDF 坐标）
                x = line.x_min * scale_factor
                y = line.y_min * scale_factor
                
                # 计算字体大小
                font_size = line.height * scale_factor * 0.8
                if font_size < 1:
                    font_size = 8
                
                # 创建文本插入点
                point = fitz.Point(x, y + font_size)
                
                # 插入透明文本
                page.insert_text(
                    point,
                    line.text,
                    fontsize=font_size,
                    fontname="china-s",  # 使用内置中文字体
                    color=(0, 0, 0),
                    render_mode=3  # 不可见但可搜索
                )
            except Exception as e:
                # 跳过无法插入的文本
                continue
    
    def create_from_images(
        self,
        images: List,
        ocr_results: List[OCRResult],
        output_path: Union[str, Path],
        dpi: int = None
    ) -> Path:
        """
        从图像创建可搜索 PDF
        
        Args:
            images: 图像列表
            ocr_results: OCR 结果列表
            output_path: 输出文件路径
            dpi: 图像 DPI
            
        Returns:
            输出文件路径
        """
        import numpy as np
        from PIL import Image
        import io
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        dpi = dpi or settings.DEFAULT_DPI
        
        # 创建新 PDF
        doc = fitz.open()
        
        for i, image in enumerate(images):
            # 转换图像格式
            if isinstance(image, np.ndarray):
                pil_image = Image.fromarray(image)
            else:
                pil_image = image
            
            # 将图像转换为字节
            img_bytes = io.BytesIO()
            pil_image.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            
            # 计算页面尺寸（点）
            width_pt = pil_image.width * 72 / dpi
            height_pt = pil_image.height * 72 / dpi
            
            # 创建新页面
            page = doc.new_page(width=width_pt, height=height_pt)
            
            # 插入图像
            rect = page.rect
            page.insert_image(rect, stream=img_bytes.getvalue())
            
            # 添加文本层
            if i < len(ocr_results):
                self._add_text_layer_for_image(
                    page, ocr_results[i], pil_image.width, pil_image.height, dpi
                )
        
        doc.save(str(output_path))
        doc.close()
        
        return output_path
    
    def _add_text_layer_for_image(
        self,
        page: fitz.Page,
        ocr_result: OCRResult,
        image_width: int,
        image_height: int,
        dpi: int
    ) -> None:
        """为图像页面添加文本层"""
        scale_x = page.rect.width / image_width
        scale_y = page.rect.height / image_height
        
        for line in ocr_result.lines:
            try:
                # 转换坐标
                x = line.x_min * scale_x
                y = line.y_min * scale_y
                
                # 计算字体大小
                font_size = line.height * scale_y * 0.8
                if font_size < 1:
                    font_size = 8
                
                point = fitz.Point(x, y + font_size)
                
                page.insert_text(
                    point,
                    line.text,
                    fontsize=font_size,
                    fontname="china-s",
                    color=(0, 0, 0),
                    render_mode=3
                )
            except Exception:
                continue


def create_searchable_pdf(
    pdf_path: Union[str, Path],
    ocr_results: List[OCRResult],
    output_path: Union[str, Path]
) -> Path:
    """
    快捷函数：创建可搜索 PDF
    
    Args:
        pdf_path: 原始 PDF 路径
        ocr_results: OCR 结果列表
        output_path: 输出文件路径
        
    Returns:
        输出文件路径
    """
    creator = SearchablePDFCreator()
    return creator.create(pdf_path, ocr_results, output_path)
