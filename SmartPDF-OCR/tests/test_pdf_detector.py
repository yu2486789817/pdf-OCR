"""
PDF 检测测试模块
"""

import unittest
from app.core.pdf_detector import PDFDetector

class TestPDFDetector(unittest.TestCase):
    def test_detector_init(self):
        detector = PDFDetector(threshold=100)
        self.assertEqual(detector.threshold, 100)

if __name__ == '__main__':
    unittest.main()
