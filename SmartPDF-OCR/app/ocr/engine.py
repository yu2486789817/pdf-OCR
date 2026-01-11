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
        use_gpu: bool = None,
        use_tensorrt: bool = None
    ):
        """
        初始化 OCR 引擎
        
        Args:
            lang: 语言代码 (ch/en/等)
            use_angle_cls: 是否启用方向分类
            use_gpu: 是否使用 GPU
            use_tensorrt: 是否使用 TensorRT
        """
        if self._ocr is not None:
            return
        
        self.lang = lang or settings.OCR_LANG
        self.use_angle_cls = use_angle_cls if use_angle_cls is not None else settings.OCR_USE_ANGLE_CLS
        self.use_gpu = use_gpu if use_gpu is not None else settings.OCR_USE_GPU
        self.use_tensorrt = use_tensorrt if use_tensorrt is not None else settings.OCR_USE_TENSORRT
        
        self._init_ocr()
    
    def _init_ocr(self):
        """初始化 PaddleOCR"""
        import sys
        import paddle

        # 自动检测 GPU 可用性
        if self.use_gpu:
            if not paddle.device.is_compiled_with_cuda():
                print("警告: 未检测到 CUDA 环境，正在降级到 CPU 模式...")
                self.use_gpu = False
                self.use_tensorrt = False
            else:
                # 尝试获取可用设备
                try:
                    paddle.device.set_device('gpu')
                except Exception as e:
                    print(f"警告: 无法初始化 GPU ({e})，正在降级到 CPU 模式...")
                    self.use_gpu = False
                    self.use_tensorrt = False

        if not self.use_gpu:
            self.use_tensorrt = False

        print(f"OCR 引擎初始化: GPU={self.use_gpu}, TensorRT={self.use_tensorrt}")

        # 捕获日志输出
        self._ocr = PaddleOCR(
            use_angle_cls=self.use_angle_cls,
            lang=self.lang,
            use_gpu=self.use_gpu,
            use_tensorrt=self.use_tensorrt,
            show_log=False
        )

    def warmup(self):
        """引擎预热：执行一次虚拟识别以加载模型和初始化 GPU 环境"""
        if self._ocr is None:
            self._init_ocr()
        
        print("正在预热 OCR 引擎...")
        try:
            # 创建一个 100x100 的纯色图片进行预热
            dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
            self._ocr.ocr(dummy_img, cls=self.use_angle_cls)
            print("OCR 引擎预热完成")
        except Exception as e:
            print(f"OCR 引擎预热失败: {e}")
    
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
