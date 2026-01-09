"""
PDF 渲染模块
将 PDF 页面渲染为高分辨率图片
"""

from pathlib import Path
from typing import List, Optional, Generator
from dataclasses import dataclass
import numpy as np
import fitz  # PyMuPDF

from app.config import settings


@dataclass
class RenderedPage:
    """渲染后的页面"""
    page_num: int
    image: np.ndarray
    width: int
    height: int
    dpi: int


class PDFRenderer:
    """PDF 渲染器"""
    
    def __init__(self, dpi: int = None):
        """
        初始化渲染器
        
        Args:
            dpi: 渲染 DPI，默认使用配置值
        """
        self.dpi = dpi or settings.DEFAULT_DPI
        self._validate_dpi()
    
    def _validate_dpi(self):
        """验证 DPI 值"""
        if self.dpi < settings.MIN_DPI:
            self.dpi = settings.MIN_DPI
        elif self.dpi > settings.MAX_DPI:
            self.dpi = settings.MAX_DPI
    
    def render_page(self, pdf_path: str | Path, page_num: int) -> RenderedPage:
        """
        渲染单个页面
        
        Args:
            pdf_path: PDF 文件路径
            page_num: 页码（从 0 开始）
            
        Returns:
            RenderedPage 对象
        """
        pdf_path = Path(pdf_path)
        
        try:
            doc = fitz.open(pdf_path)
            
            if page_num >= len(doc):
                doc.close()
                raise ValueError(f"页码 {page_num} 超出范围，共 {len(doc)} 页")
            
            page = doc[page_num]
            
            # 计算缩放比例
            zoom = self.dpi / 72  # PDF 默认 72 DPI
            matrix = fitz.Matrix(zoom, zoom)
            
            # 渲染页面为图片
            pixmap = page.get_pixmap(matrix=matrix)
            
            # 转换为 numpy 数组
            image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                pixmap.height, pixmap.width, pixmap.n
            )
            
            # 如果是 RGBA，转换为 RGB
            if pixmap.n == 4:
                image = image[:, :, :3]
            
            result = RenderedPage(
                page_num=page_num,
                image=image.copy(),
                width=pixmap.width,
                height=pixmap.height,
                dpi=self.dpi
            )
            
            doc.close()
            return result
            
        except Exception as e:
            raise ValueError(f"渲染 PDF 页面失败: {str(e)}")
    
    def render_all(self, pdf_path: str | Path) -> List[RenderedPage]:
        """
        渲染所有页面
        
        Args:
            pdf_path: PDF 文件路径
            
        Returns:
            RenderedPage 对象列表
        """
        pdf_path = Path(pdf_path)
        pages = []
        
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            
            for i in range(page_count):
                page = self.render_page(pdf_path, i)
                pages.append(page)
            
            return pages
            
        except Exception as e:
            raise ValueError(f"渲染 PDF 失败: {str(e)}")
    
    def render_pages(
        self, 
        pdf_path: str | Path, 
        page_nums: List[int]
    ) -> List[RenderedPage]:
        """
        渲染指定页面
        
        Args:
            pdf_path: PDF 文件路径
            page_nums: 页码列表
            
        Returns:
            RenderedPage 对象列表
        """
        pages = []
        for page_num in page_nums:
            page = self.render_page(pdf_path, page_num)
            pages.append(page)
        return pages
    
    def render_generator(
        self, 
        pdf_path: str | Path
    ) -> Generator[RenderedPage, None, None]:
        """
        生成器方式渲染页面（节省内存）
        
        Args:
            pdf_path: PDF 文件路径
            
        Yields:
            RenderedPage 对象
        """
        pdf_path = Path(pdf_path)
        
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            
            for i in range(page_count):
                page = doc[i]
                
                # 计算缩放比例
                zoom = self.dpi / 72
                matrix = fitz.Matrix(zoom, zoom)
                
                # 渲染页面
                pixmap = page.get_pixmap(matrix=matrix)
                
                # 转换为 numpy 数组
                image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, pixmap.n
                )
                
                if pixmap.n == 4:
                    image = image[:, :, :3]
                
                yield RenderedPage(
                    page_num=i,
                    image=image.copy(),
                    width=pixmap.width,
                    height=pixmap.height,
                    dpi=self.dpi
                )
            
            doc.close()
            
        except Exception as e:
            raise ValueError(f"渲染 PDF 失败: {str(e)}")
    
    def get_page_count(self, pdf_path: str | Path) -> int:
        """获取 PDF 页数"""
        try:
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            return count
        except Exception as e:
            raise ValueError(f"无法获取 PDF 页数: {str(e)}")
    
    def get_page_size(self, pdf_path: str | Path, page_num: int = 0) -> tuple:
        """
        获取页面原始尺寸
        
        Returns:
            (width, height) 单位为点
        """
        try:
            doc = fitz.open(pdf_path)
            if page_num >= len(doc):
                doc.close()
                raise ValueError(f"页码 {page_num} 超出范围")
            
            page = doc[page_num]
            rect = page.rect
            doc.close()
            
            return (rect.width, rect.height)
            
        except Exception as e:
            raise ValueError(f"无法获取页面尺寸: {str(e)}")


def render_pdf_to_images(
    pdf_path: str | Path, 
    dpi: int = None
) -> List[np.ndarray]:
    """
    快捷函数：将 PDF 渲染为图片列表
    
    Args:
        pdf_path: PDF 文件路径
        dpi: 渲染 DPI
        
    Returns:
        图片列表（numpy 数组格式）
    """
    renderer = PDFRenderer(dpi)
    pages = renderer.render_all(pdf_path)
    return [page.image for page in pages]


def render_pdf_page(
    pdf_path: str | Path, 
    page_num: int,
    dpi: int = None
) -> np.ndarray:
    """
    快捷函数：渲染单个 PDF 页面
    
    Args:
        pdf_path: PDF 文件路径
        page_num: 页码
        dpi: 渲染 DPI
        
    Returns:
        图片（numpy 数组格式）
    """
    renderer = PDFRenderer(dpi)
    page = renderer.render_page(pdf_path, page_num)
    return page.image
