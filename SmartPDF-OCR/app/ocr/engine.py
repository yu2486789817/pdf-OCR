"""
OCR 引擎模块
封装 PaddleOCR 提供统一的 OCR 接口
"""

import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from paddleocr import PaddleOCR

from app.config import settings


@dataclass
class OCRLine:
    """OCR 识别的单行文本"""
    text: str
    confidence: float
    box: List[List[float]]  # 四个角点坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    
    @property
    def x_min(self) -> float:
        return min(p[0] for p in self.box)
    
    @property
    def x_max(self) -> float:
        return max(p[0] for p in self.box)
    
    @property
    def y_min(self) -> float:
        return min(p[1] for p in self.box)
    
    @property
    def y_max(self) -> float:
        return max(p[1] for p in self.box)
    
    @property
    def height(self) -> float:
        return self.y_max - self.y_min
    
    @property
    def width(self) -> float:
        return self.x_max - self.x_min
    
    @property
    def center_y(self) -> float:
        return (self.y_min + self.y_max) / 2


@dataclass
class OCRResult:
    """单页 OCR 结果"""
    page_num: int
    lines: List[OCRLine] = field(default_factory=list)
    img_width: int = 0
    img_height: int = 0
    
    @property
    def text(self) -> str:
        """获取所有文本（按行拼接）"""
        return "\n".join(line.text for line in self.lines)
    
    @property
    def avg_confidence(self) -> float:
        """平均置信度"""
        if not self.lines:
            return 0.0
        return sum(line.confidence for line in self.lines) / len(self.lines)
    
    @property
    def low_confidence_lines(self) -> List[OCRLine]:
        """低置信度行"""
        threshold = settings.OCR_CONFIDENCE_THRESHOLD
        return [line for line in self.lines if line.confidence < threshold]
    
    def sort_by_position(self) -> None:
        """按位置排序（从上到下，从左到右）"""
        self.lines.sort(key=lambda line: (line.y_min, line.x_min))


class OCREngine:
    """OCR 引擎"""
    
    _instance: Optional['OCREngine'] = None
    _ocr: Optional[PaddleOCR] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        lang: str = None,
        use_angle_cls: bool = None,
        use_gpu: bool = None
    ):
        """
        初始化 OCR 引擎
        
        Args:
            lang: 语言代码 (ch/en/等)
            use_angle_cls: 是否启用方向分类
            use_gpu: 是否使用 GPU
        """
        if self._ocr is not None:
            return
        
        self.lang = lang or settings.OCR_LANG
        self.use_angle_cls = use_angle_cls if use_angle_cls is not None else settings.OCR_USE_ANGLE_CLS
        self.use_gpu = use_gpu if use_gpu is not None else settings.OCR_USE_GPU
        
        self._init_ocr()
    
    def _init_ocr(self):
        """初始化 PaddleOCR"""
        self._ocr = PaddleOCR(
            use_angle_cls=self.use_angle_cls,
            lang=self.lang,
            use_gpu=self.use_gpu,
            show_log=False
        )
    
    def recognize(self, image: np.ndarray, page_num: int = 0) -> OCRResult:
        """
        识别图片中的文字
        
        Args:
            image: 输入图像 (numpy 数组)
            page_num: 页码
            
        Returns:
            OCRResult 对象
        """
        if self._ocr is None:
            self._init_ocr()
        
        # 执行 OCR
        result = self._ocr.ocr(image, cls=self.use_angle_cls)
        
        # 解析结果
        lines = []
        if result and result[0]:
            for item in result[0]:
                box = item[0]  # 四个角点坐标
                text = item[1][0]  # 识别的文字
                confidence = item[1][1]  # 置信度
                
                line = OCRLine(
                    text=text,
                    confidence=confidence,
                    box=box
                )
                lines.append(line)
        
        ocr_result = OCRResult(
            page_num=page_num, 
            lines=lines,
            img_width=image.shape[1],
            img_height=image.shape[0]
        )
        ocr_result.sort_by_position()
        
        return ocr_result
    
    def recognize_batch(
        self, 
        images: List[np.ndarray],
        start_page: int = 0
    ) -> List[OCRResult]:
        """
        批量识别多张图片
        
        Args:
            images: 图片列表
            start_page: 起始页码
            
        Returns:
            OCRResult 对象列表
        """
        results = []
        for i, image in enumerate(images):
            result = self.recognize(image, page_num=start_page + i)
            results.append(result)
        return results
    
    def get_text_only(self, image: np.ndarray) -> str:
        """
        只获取识别的文本
        
        Args:
            image: 输入图像
            
        Returns:
            识别的文本
        """
        result = self.recognize(image)
        return result.text


def recognize_image(image: np.ndarray) -> OCRResult:
    """
    快捷函数：识别图片
    
    Args:
        image: 输入图像
        
    Returns:
        OCRResult 对象
    """
    engine = OCREngine()
    return engine.recognize(image)


def get_text(image: np.ndarray) -> str:
    """
    快捷函数：获取图片中的文本
    
    Args:
        image: 输入图像
        
    Returns:
        识别的文本
    """
    engine = OCREngine()
    return engine.get_text_only(image)
