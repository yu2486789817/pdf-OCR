"""
SmartPDF-OCR 配置文件
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    """应用配置"""
    
    # 项目路径
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = Field(default=None)
    OUTPUT_DIR: Path = Field(default=None)
    
    # PDF 检测配置
    PDF_TEXT_THRESHOLD: int = 50  # 文字型 PDF 判定阈值（字符数）
    
    # PDF 渲染配置
    DEFAULT_DPI: int = 300  # 默认渲染 DPI
    MAX_DPI: int = 600  # 最大 DPI
    MIN_DPI: int = 150  # 最小 DPI
    
    # OCR 配置
    OCR_LANG: str = "ch"  # OCR 语言：ch=中文, en=英文
    OCR_USE_ANGLE_CLS: bool = True  # 是否启用方向检测
    OCR_USE_GPU: bool = True  # 是否使用 GPU
    OCR_CONFIDENCE_THRESHOLD: float = 0.5  # 置信度阈值
    
    # 图像预处理配置
    PREPROCESS_DENOISE: bool = True  # 是否启用去噪
    PREPROCESS_BINARIZE: bool = False  # 是否启用二值化（对扫描件有效）
    PREPROCESS_DESKEW: bool = True  # 是否启用倾斜校正
    BINARIZE_THRESHOLD: int = 127  # 二值化阈值
    
    # 后处理配置
    PARAGRAPH_LINE_SPACING_THRESHOLD: float = 1.5  # 段落行间距阈值倍数
    REMOVE_HEADER_FOOTER: bool = True  # 是否移除页眉页脚
    HEADER_FOOTER_REPEAT_THRESHOLD: int = 3  # 页眉页脚重复次数阈值
    
    # 导出配置
    EXPORT_FORMATS: list = ["txt", "docx", "pdf"]
    SEARCHABLE_PDF_FONT: str = "SimSun"  # 可搜索 PDF 使用的字体
    
    # API 配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    
    # Gradio 配置
    GRADIO_HOST: str = "0.0.0.0"
    GRADIO_PORT: int = 7860
    GRADIO_SHARE: bool = False
    
    def model_post_init(self, __context):
        """初始化后处理"""
        if self.UPLOAD_DIR is None:
            self.UPLOAD_DIR = self.BASE_DIR / "uploads"
        if self.OUTPUT_DIR is None:
            self.OUTPUT_DIR = self.BASE_DIR / "outputs"
        
        # 确保目录存在
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()
