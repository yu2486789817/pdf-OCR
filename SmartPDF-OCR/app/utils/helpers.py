"""
通用工具函数
"""

import time
import functools
from typing import Callable, Any
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SmartPDF-OCR")


def timer(func: Callable) -> Callable:
    """计时装饰器"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.info(f"{func.__name__} 耗时: {elapsed:.2f}s")
        return result
    return wrapper


def ensure_dir(path: Path | str) -> Path:
    """确保目录存在"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_file_size_str(size_bytes: int) -> str:
    """将字节大小转换为可读字符串"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def safe_filename(filename: str) -> str:
    """生成安全的文件名"""
    import re
    # 移除不安全字符
    safe = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 移除开头和结尾的空格和点
    safe = safe.strip(' .')
    # 限制长度
    if len(safe) > 200:
        name, ext = safe.rsplit('.', 1) if '.' in safe else (safe, '')
        safe = name[:200-len(ext)-1] + '.' + ext if ext else name[:200]
    return safe or 'unnamed'


class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self, total: int, description: str = "处理中"):
        self.total = total
        self.current = 0
        self.description = description
        self.callbacks = []
    
    def add_callback(self, callback: Callable[[int, int, str], None]):
        """添加进度回调"""
        self.callbacks.append(callback)
    
    def update(self, step: int = 1, message: str = None):
        """更新进度"""
        self.current += step
        msg = message or self.description
        
        for callback in self.callbacks:
            callback(self.current, self.total, msg)
    
    @property
    def progress(self) -> float:
        """当前进度百分比"""
        if self.total == 0:
            return 0.0
        return self.current / self.total * 100
    
    def reset(self):
        """重置进度"""
        self.current = 0
