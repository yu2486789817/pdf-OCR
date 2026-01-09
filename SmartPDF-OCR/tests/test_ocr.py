"""
OCR 测试模块
"""

import unittest
from pathlib import Path
import numpy as np

from app.core.pdf_detector import PDFDetector
from app.ocr.engine import OCREngine, OCRLine
from app.ocr.postprocess import merge_lines, rebuild_paragraphs

class TestOCR(unittest.TestCase):
    def test_line_merge(self):
        """测试文本行合并"""
        # 模拟同一行的两段文本
        line1 = OCRLine(
            text="Hello", 
            confidence=0.9, 
            box=[[10, 10], [50, 10], [50, 30], [10, 30]]
        )
        line2 = OCRLine(
            text="World", 
            confidence=0.9, 
            box=[[60, 12], [100, 12], [100, 32], [60, 32]]
        )
        
        merged = merge_lines([line1, line2])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].text, "Hello World")
    
    def test_paragraph_rebuild(self):
        """测试段落重建"""
        # 模拟两行文本，行间距较小（同一段落）
        line1 = OCRLine(
            text="This is line 1.", 
            confidence=0.9, 
            box=[[10, 10], [100, 10], [100, 30], [10, 30]]
        )
        line2 = OCRLine(
            text="This is line 2.", 
            confidence=0.9, 
            box=[[10, 35], [100, 35], [100, 55], [10, 55]]
        )
        
        paragraphs = rebuild_paragraphs([line1, line2])
        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(paragraphs[0].text, "This is line 1.This is line 2.")

if __name__ == '__main__':
    unittest.main()
