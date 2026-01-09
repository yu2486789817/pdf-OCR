"""
OCR 后处理模块
对 OCR 结果进行文本行合并、段落重建、页眉页脚消除等处理
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import Counter

from app.config import settings
from app.ocr.engine import OCRResult, OCRLine


@dataclass
class Paragraph:
    """段落"""
    text: str
    lines: List[OCRLine]
    
    @property
    def avg_confidence(self) -> float:
        if not self.lines:
            return 0.0
        return sum(line.confidence for line in self.lines) / len(self.lines)


@dataclass
class ProcessedPage:
    """处理后的页面"""
    page_num: int
    paragraphs: List[Paragraph]
    header: Optional[str] = None
    footer: Optional[str] = None
    
    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.paragraphs)
    
    @property
    def avg_confidence(self) -> float:
        if not self.paragraphs:
            return 0.0
        return sum(p.avg_confidence for p in self.paragraphs) / len(self.paragraphs)


class PostProcessor:
    """OCR 后处理器"""
    
    def __init__(
        self,
        line_spacing_threshold: float = None,
        remove_header_footer: bool = None,
        header_footer_repeat_threshold: int = None
    ):
        self.line_spacing_threshold = (
            line_spacing_threshold or 
            settings.PARAGRAPH_LINE_SPACING_THRESHOLD
        )
        self.remove_header_footer = (
            remove_header_footer if remove_header_footer is not None 
            else settings.REMOVE_HEADER_FOOTER
        )
        self.header_footer_repeat_threshold = (
            header_footer_repeat_threshold or 
            settings.HEADER_FOOTER_REPEAT_THRESHOLD
        )
    
    def process(self, ocr_result: OCRResult) -> ProcessedPage:
        """
        处理单页 OCR 结果
        
        Args:
            ocr_result: OCR 结果
            
        Returns:
            处理后的页面
        """
        lines = ocr_result.lines.copy()
        
        # 排序
        lines.sort(key=lambda x: (x.y_min, x.x_min))
        
        # 合并同行文本
        merged_lines = self._merge_same_row_lines(lines)
        
        # 重建段落
        paragraphs = self._rebuild_paragraphs(merged_lines)
        
        return ProcessedPage(
            page_num=ocr_result.page_num,
            paragraphs=paragraphs
        )
    
    def process_batch(
        self, 
        ocr_results: List[OCRResult]
    ) -> List[ProcessedPage]:
        """
        批量处理 OCR 结果
        
        Args:
            ocr_results: OCR 结果列表
            
        Returns:
            处理后的页面列表
        """
        pages = [self.process(result) for result in ocr_results]
        
        # 移除页眉页脚
        if self.remove_header_footer and len(pages) >= self.header_footer_repeat_threshold:
            pages = self._remove_headers_footers(pages)
        
        return pages
    
    def _merge_same_row_lines(self, lines: List[OCRLine]) -> List[OCRLine]:
        """合并同一行的文本块"""
        if not lines:
            return []
        
        merged = []
        current_line = lines[0]
        current_texts = [current_line.text]
        current_boxes = [current_line.box]
        current_confidences = [current_line.confidence]
        
        for line in lines[1:]:
            # 判断是否在同一行（y 坐标重叠）
            overlap = self._calculate_y_overlap(current_line, line)
            
            if overlap > 0.5:  # 重叠超过 50% 认为是同一行
                current_texts.append(line.text)
                current_boxes.append(line.box)
                current_confidences.append(line.confidence)
            else:
                # 保存当前行
                merged.append(self._create_merged_line(
                    current_texts, current_boxes, current_confidences
                ))
                # 开始新行
                current_line = line
                current_texts = [line.text]
                current_boxes = [line.box]
                current_confidences = [line.confidence]
        
        # 保存最后一行
        merged.append(self._create_merged_line(
            current_texts, current_boxes, current_confidences
        ))
        
        return merged
    
    def _calculate_y_overlap(self, line1: OCRLine, line2: OCRLine) -> float:
        """计算两行在 y 轴上的重叠比例"""
        y1_min, y1_max = line1.y_min, line1.y_max
        y2_min, y2_max = line2.y_min, line2.y_max
        
        overlap_start = max(y1_min, y2_min)
        overlap_end = min(y1_max, y2_max)
        
        if overlap_end <= overlap_start:
            return 0.0
        
        overlap_height = overlap_end - overlap_start
        min_height = min(line1.height, line2.height)
        
        if min_height == 0:
            return 0.0
        
        return overlap_height / min_height
    
    def _create_merged_line(
        self,
        texts: List[str],
        boxes: List[List[List[float]]],
        confidences: List[float]
    ) -> OCRLine:
        """创建合并后的行"""
        # 按 x 坐标排序
        items = sorted(zip(texts, boxes, confidences), key=lambda x: x[1][0][0])
        
        # 合并文本
        merged_text = " ".join(t for t, _, _ in items)
        
        # 合并边界框
        all_points = [p for _, box, _ in items for p in box]
        merged_box = [
            [min(p[0] for p in all_points), min(p[1] for p in all_points)],
            [max(p[0] for p in all_points), min(p[1] for p in all_points)],
            [max(p[0] for p in all_points), max(p[1] for p in all_points)],
            [min(p[0] for p in all_points), max(p[1] for p in all_points)]
        ]
        
        # 平均置信度
        avg_confidence = sum(confidences) / len(confidences)
        
        return OCRLine(
            text=merged_text,
            confidence=avg_confidence,
            box=merged_box
        )
    
    def _rebuild_paragraphs(self, lines: List[OCRLine]) -> List[Paragraph]:
        """重建段落"""
        if not lines:
            return []
        
        paragraphs = []
        current_lines = [lines[0]]
        
        # 计算平均行高
        avg_height = sum(line.height for line in lines) / len(lines)
        
        for i in range(1, len(lines)):
            prev_line = lines[i - 1]
            curr_line = lines[i]
            
            # 计算行间距
            line_gap = curr_line.y_min - prev_line.y_max
            
            # 判断是否是新段落
            is_new_paragraph = (
                line_gap > avg_height * self.line_spacing_threshold or
                self._is_paragraph_start(curr_line.text)
            )
            
            if is_new_paragraph:
                # 保存当前段落
                paragraphs.append(self._create_paragraph(current_lines))
                current_lines = [curr_line]
            else:
                current_lines.append(curr_line)
        
        # 保存最后一个段落
        if current_lines:
            paragraphs.append(self._create_paragraph(current_lines))
        
        return paragraphs
    
    def _is_paragraph_start(self, text: str) -> bool:
        """判断是否是段落开头"""
        # 检查是否有缩进（以空格开头）
        if text.startswith("    ") or text.startswith("\t"):
            return True
        
        # 检查是否是列表项
        list_patterns = [
            r"^\d+[.、）)]",  # 1. 1、 1）1)
            r"^[一二三四五六七八九十]+[.、）)]",  # 一、二、
            r"^[（(]\d+[）)]",  # (1) （1）
            r"^[•·▪▸►◆○●■□]",  # 各种符号列表
        ]
        for pattern in list_patterns:
            if re.match(pattern, text.strip()):
                return True
        
        return False
    
    def _create_paragraph(self, lines: List[OCRLine]) -> Paragraph:
        """创建段落"""
        text = "".join(line.text for line in lines)
        return Paragraph(text=text, lines=lines)
    
    def _remove_headers_footers(
        self, 
        pages: List[ProcessedPage]
    ) -> List[ProcessedPage]:
        """移除页眉页脚"""
        if len(pages) < self.header_footer_repeat_threshold:
            return pages
        
        # 收集每页首尾段落
        first_paragraphs = []
        last_paragraphs = []
        
        for page in pages:
            if page.paragraphs:
                first_paragraphs.append(page.paragraphs[0].text.strip())
                last_paragraphs.append(page.paragraphs[-1].text.strip())
        
        # 统计重复内容
        first_counter = Counter(first_paragraphs)
        last_counter = Counter(last_paragraphs)
        
        # 识别页眉页脚
        headers = {
            text for text, count in first_counter.items() 
            if count >= self.header_footer_repeat_threshold
        }
        footers = {
            text for text, count in last_counter.items() 
            if count >= self.header_footer_repeat_threshold
        }
        
        # 移除页眉页脚
        for page in pages:
            if page.paragraphs:
                # 移除页眉
                if page.paragraphs[0].text.strip() in headers:
                    page.header = page.paragraphs[0].text
                    page.paragraphs = page.paragraphs[1:]
                
                # 移除页脚
                if page.paragraphs and page.paragraphs[-1].text.strip() in footers:
                    page.footer = page.paragraphs[-1].text
                    page.paragraphs = page.paragraphs[:-1]
        
        return pages


def merge_lines(lines: List[OCRLine]) -> List[OCRLine]:
    """快捷函数：合并同行文本"""
    processor = PostProcessor()
    return processor._merge_same_row_lines(lines)


def rebuild_paragraphs(lines: List[OCRLine]) -> List[Paragraph]:
    """快捷函数：重建段落"""
    processor = PostProcessor()
    merged = processor._merge_same_row_lines(lines)
    return processor._rebuild_paragraphs(merged)


def format_text(text: str) -> str:
    """
    格式化文本
    - 修正中英文标点
    - 规范化空格
    - 修正常见 OCR 错误
    """
    # 中文标点后不应有空格
    text = re.sub(r'([，。！？；：、])(\s+)', r'\1', text)
    
    # 英文标点后应有空格（如果后面是字母）
    text = re.sub(r'([,.:;!?])([a-zA-Z])', r'\1 \2', text)
    
    # 规范化连续空格
    text = re.sub(r' +', ' ', text)
    
    # 常见 OCR 错误修正
    corrections = {
        '囗': '口',
        '囗': '□',
        '〇': '○',
        '―': '—',
    }
    for wrong, right in corrections.items():
        text = text.replace(wrong, right)
    
    return text.strip()
