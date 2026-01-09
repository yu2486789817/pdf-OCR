"""
PDF 类型检测模块
自动判断 PDF 是文字型还是图片型
"""

from pathlib import Path
from typing import Tuple, Literal
from dataclasses import dataclass
import pdfplumber

from app.config import settings


@dataclass
class PDFInfo:
    """PDF 文件信息"""
    file_path: str
    page_count: int
    pdf_type: Literal["text", "image", "mixed"]
    text_pages: list  # 文字型页面索引
    image_pages: list  # 图片型页面索引
    total_text_chars: int
    avg_chars_per_page: float


class PDFDetector:
    """PDF 类型检测器"""
    
    def __init__(self, threshold: int = None):
        """
        初始化检测器
        
        Args:
            threshold: 文字型 PDF 判定阈值（每页最少字符数）
        """
        self.threshold = threshold or settings.PDF_TEXT_THRESHOLD
    
    def detect(self, pdf_path: str | Path) -> PDFInfo:
        """
        检测 PDF 类型
        
        Args:
            pdf_path: PDF 文件路径
            
        Returns:
            PDFInfo 对象，包含检测结果
        """
        pdf_path = Path(pdf_path)
        
        text_pages = []
        image_pages = []
        total_chars = 0
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    # 提取页面文本
                    text = page.extract_text() or ""
                    char_count = len(text.strip())
                    total_chars += char_count
                    
                    # 判断当前页面类型
                    if char_count >= self.threshold:
                        text_pages.append(i)
                    else:
                        image_pages.append(i)
                
                # 计算平均每页字符数
                avg_chars = total_chars / page_count if page_count > 0 else 0
                
                # 确定整体 PDF 类型
                if len(image_pages) == 0:
                    pdf_type = "text"
                elif len(text_pages) == 0:
                    pdf_type = "image"
                else:
                    pdf_type = "mixed"
                
                return PDFInfo(
                    file_path=str(pdf_path),
                    page_count=page_count,
                    pdf_type=pdf_type,
                    text_pages=text_pages,
                    image_pages=image_pages,
                    total_text_chars=total_chars,
                    avg_chars_per_page=avg_chars
                )
                
        except Exception as e:
            raise ValueError(f"无法解析 PDF 文件: {str(e)}")
    
    def detect_page(self, pdf_path: str | Path, page_num: int) -> Tuple[str, int]:
        """
        检测单个页面类型
        
        Args:
            pdf_path: PDF 文件路径
            page_num: 页码（从 0 开始）
            
        Returns:
            (页面类型, 字符数)
        """
        pdf_path = Path(pdf_path)
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if page_num >= len(pdf.pages):
                    raise ValueError(f"页码 {page_num} 超出范围")
                
                page = pdf.pages[page_num]
                text = page.extract_text() or ""
                char_count = len(text.strip())
                
                page_type = "text" if char_count >= self.threshold else "image"
                return page_type, char_count
                
        except Exception as e:
            raise ValueError(f"无法解析 PDF 页面: {str(e)}")
    
    def extract_text(self, pdf_path: str | Path, page_num: int = None) -> str:
        """
        提取 PDF 文本
        
        Args:
            pdf_path: PDF 文件路径
            page_num: 页码（从 0 开始），None 表示提取所有页面
            
        Returns:
            提取的文本
        """
        pdf_path = Path(pdf_path)
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if page_num is not None:
                    if page_num >= len(pdf.pages):
                        raise ValueError(f"页码 {page_num} 超出范围")
                    text = pdf.pages[page_num].extract_text() or ""
                else:
                    texts = []
                    for page in pdf.pages:
                        page_text = page.extract_text() or ""
                        texts.append(page_text)
                    text = "\n\n".join(texts)
                
                return text
                
        except Exception as e:
            raise ValueError(f"无法提取 PDF 文本: {str(e)}")


def detect_pdf_type(pdf_path: str | Path, threshold: int = None) -> str:
    """
    快捷函数：检测 PDF 类型
    
    Args:
        pdf_path: PDF 文件路径
        threshold: 判定阈值
        
    Returns:
        "text", "image" 或 "mixed"
    """
    detector = PDFDetector(threshold)
    info = detector.detect(pdf_path)
    return info.pdf_type


def get_pdf_info(pdf_path: str | Path) -> PDFInfo:
    """
    快捷函数：获取 PDF 详细信息
    
    Args:
        pdf_path: PDF 文件路径
        
    Returns:
        PDFInfo 对象
    """
    detector = PDFDetector()
    return detector.detect(pdf_path)
