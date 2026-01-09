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
                
                # 如果页数过多（超过 50 页），进行采样检测以加快速度
                sample_indices = range(page_count)
                is_sampled = False
                if page_count > 50:
                    is_sampled = True
                    # 采样：前 15 页，中间 15 页，最后 15 页
                    s1 = list(range(min(15, page_count)))
                    s2 = list(range(max(0, page_count // 2 - 7), min(page_count, page_count // 2 + 8)))
                    s3 = list(range(max(0, page_count - 15), page_count))
                    sample_indices = sorted(list(set(s1 + s2 + s3)))

                for i in range(page_count):
                    # 如果不需要检测所有页面，且不在采样范围内，默认标记为 image (或者根据采样结果推断)
                    # 这里为了保证 page_count 准确，循环还是要跑，但 extract_text 只在采样点做
                    if is_sampled and i not in sample_indices:
                        # 非采样页先假设
                        continue
                        
                    page = pdf.pages[i]
                    text = page.extract_text() or ""
                    char_count = len(text.strip())
                    total_chars += char_count
                    
                    if char_count >= self.threshold:
                        text_pages.append(i)
                    else:
                        image_pages.append(i)
                
                # 处理未采样页面的逻辑（如果是采样模式）
                if is_sampled:
                    # 根据采样比例推算总体类型
                    sample_text_count = len([idx for idx in text_pages if idx in sample_indices])
                    sample_image_count = len([idx for idx in image_pages if idx in sample_indices])
                    
                    if sample_text_count > 0 and sample_image_count > 0:
                        pdf_type = "mixed"
                    elif sample_text_count > 0:
                        pdf_type = "text"
                        # 补充全量索引（虽然不完全准确，但能用）
                        text_pages = list(range(page_count))
                        image_pages = []
                    else:
                        pdf_type = "image"
                        image_pages = list(range(page_count))
                        text_pages = []
                    
                    avg_chars = total_chars / len(sample_indices) if sample_indices else 0
                else:
                    avg_chars = total_chars / page_count if page_count > 0 else 0
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
