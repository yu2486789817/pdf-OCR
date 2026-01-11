"""
SmartPDF-OCR 配置文件
"""

import sys
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal, Optional


def is_frozen() -> bool:
    """检测是否运行在 PyInstaller 打包环境中"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_app_data_dir() -> Path:
    """获取应用数据目录 (跨平台)"""
    if sys.platform == "win32":
        # Windows: C:\Users\<User>\AppData\Local\SmartPDF-OCR
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        # macOS: ~/Library/Application Support/SmartPDF-OCR
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux: ~/.local/share/SmartPDF-OCR
        base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    
    app_dir = base / "SmartPDF-OCR"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_base_dir() -> Path:
    """获取基础目录"""
    if is_frozen():
        # PyInstaller 打包后，使用可执行文件所在目录
        return Path(sys.executable).parent
    else:
        # 开发环境，使用项目根目录
        return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置"""
    
    # 项目路径
    BASE_DIR: Path = Field(default_factory=get_base_dir)
    UPLOAD_DIR: Optional[Path] = Field(default=None)
    OUTPUT_DIR: Optional[Path] = Field(default=None)
    
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
    OCR_USE_TENSORRT: bool = True  # 是否使用 TensorRT 加速 (需要 GPU)
    OCR_CONFIDENCE_THRESHOLD: float = 0.5  # 置信度阈值
    OCR_WARMUP: bool = True  # 是否在启动时进行预热
    
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
    API_HOST: str = "127.0.0.1"  # 修改为 localhost，更安全
    API_PORT: int = 8000
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    
    # Gradio 配置
    GRADIO_HOST: str = "0.0.0.0"
    GRADIO_PORT: int = 7860
    GRADIO_SHARE: bool = False
    
    # AI 语义重排配置
    AI_API_URL: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    AI_API_KEY: str = ""  # 通过环境变量或 .env 文件设置
    AI_MODEL: str = "gemini-2.0-flash"
    AI_MAX_CHUNK_CHARS: int = 2000  # 每段最大字符数
    
    def model_post_init(self, __context):
        """初始化后处理"""
        # 选择数据目录：打包模式使用 AppData，开发模式使用项目目录
        if is_frozen():
            data_dir = get_app_data_dir()
        else:
            data_dir = self.BASE_DIR
        
        if self.UPLOAD_DIR is None:
            self.UPLOAD_DIR = data_dir / "uploads"
        if self.OUTPUT_DIR is None:
            self.OUTPUT_DIR = data_dir / "outputs"
        
        # 确保目录存在
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()
