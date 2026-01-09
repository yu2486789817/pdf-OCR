"""
TXT 导出模块
将 OCR 结果导出为纯文本文件
"""

from pathlib import Path
from typing import List, Union

from app.ocr.postprocess import ProcessedPage


class TxtExporter:
    """TXT 导出器"""
    
    def __init__(
        self,
        page_separator: str = "\n\n--- 第 {page} 页 ---\n\n",
        paragraph_separator: str = "\n\n",
        include_page_numbers: bool = True,
        encoding: str = "utf-8"
    ):
        """
        初始化 TXT 导出器
        
        Args:
            page_separator: 页面分隔符模板
            paragraph_separator: 段落分隔符
            include_page_numbers: 是否包含页码
            encoding: 文件编码
        """
        self.page_separator = page_separator
        self.paragraph_separator = paragraph_separator
        self.include_page_numbers = include_page_numbers
        self.encoding = encoding
    
    def export(
        self,
        pages: List[ProcessedPage],
        output_path: Union[str, Path]
    ) -> Path:
        """
        导出为 TXT 文件
        
        Args:
            pages: 处理后的页面列表
            output_path: 输出文件路径
            
        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = self._generate_content(pages)
        
        with open(output_path, "w", encoding=self.encoding) as f:
            f.write(content)
        
        return output_path
    
    def _generate_content(self, pages: List[ProcessedPage]) -> str:
        """生成文本内容"""
        parts = []
        
        for i, page in enumerate(pages):
            # 添加页面分隔符
            if i > 0 and self.include_page_numbers:
                separator = self.page_separator.format(page=page.page_num + 1)
                parts.append(separator)
            
            # 添加页面内容
            page_text = self.paragraph_separator.join(
                p.text for p in page.paragraphs
            )
            parts.append(page_text)
        
        return "".join(parts)
    
    def export_simple(
        self,
        pages: List[ProcessedPage],
        output_path: Union[str, Path]
    ) -> Path:
        """
        简单导出（无页码分隔）
        
        Args:
            pages: 处理后的页面列表
            output_path: 输出文件路径
            
        Returns:
            输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 收集所有段落文本
        all_paragraphs = []
        for page in pages:
            for paragraph in page.paragraphs:
                all_paragraphs.append(paragraph.text)
        
        content = self.paragraph_separator.join(all_paragraphs)
        
        with open(output_path, "w", encoding=self.encoding) as f:
            f.write(content)
        
        return output_path


def export_to_txt(
    pages: List[ProcessedPage],
    output_path: Union[str, Path],
    include_page_numbers: bool = True
) -> Path:
    """
    快捷函数：导出为 TXT 文件
    
    Args:
        pages: 处理后的页面列表
        output_path: 输出文件路径
        include_page_numbers: 是否包含页码
        
    Returns:
        输出文件路径
    """
    exporter = TxtExporter(include_page_numbers=include_page_numbers)
    return exporter.export(pages, output_path)
