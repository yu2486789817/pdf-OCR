"""
文件管理模块
负责文件上传、校验、缓存和清理
"""

import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple
import hashlib

from app.config import settings


class FileManager:
    """文件管理器"""
    
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.output_dir = settings.OUTPUT_DIR
        self.max_upload_size = settings.MAX_UPLOAD_SIZE
        
        # 确保目录存在
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_task_id(self) -> str:
        """生成唯一任务 ID"""
        return str(uuid.uuid4())
    
    def get_task_upload_dir(self, task_id: str) -> Path:
        """获取任务上传目录"""
        task_dir = self.upload_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir
    
    def get_task_output_dir(self, task_id: str) -> Path:
        """获取任务输出目录"""
        task_dir = self.output_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir
    
    def validate_pdf(self, file_path: Path) -> Tuple[bool, str]:
        """
        校验 PDF 文件
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            (是否有效, 错误信息)
        """
        # 检查文件是否存在
        if not file_path.exists():
            return False, "文件不存在"
        
        # 检查文件扩展名
        if file_path.suffix.lower() != ".pdf":
            return False, "文件格式不正确，请上传 PDF 文件"
        
        # 检查文件大小
        file_size = file_path.stat().st_size
        if file_size > self.max_upload_size:
            max_mb = self.max_upload_size / (1024 * 1024)
            return False, f"文件过大，最大支持 {max_mb:.0f}MB"
        
        if file_size == 0:
            return False, "文件为空"
        
        # 检查 PDF 文件头
        try:
            with open(file_path, "rb") as f:
                header = f.read(8)
                if not header.startswith(b"%PDF"):
                    return False, "无效的 PDF 文件"
        except Exception as e:
            return False, f"读取文件失败: {str(e)}"
        
        return True, ""
    
    def save_upload_file(self, file_content: bytes, filename: str, task_id: str) -> Path:
        """
        保存上传的文件
        
        Args:
            file_content: 文件内容
            filename: 原始文件名
            task_id: 任务 ID
            
        Returns:
            保存的文件路径
        """
        task_dir = self.get_task_upload_dir(task_id)
        
        # 使用原始文件名，但确保安全
        safe_filename = self._sanitize_filename(filename)
        file_path = task_dir / safe_filename
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return file_path
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除不安全字符"""
        # 获取文件名（不含路径）
        filename = os.path.basename(filename)
        
        # 替换不安全字符
        unsafe_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        
        # 如果文件名为空，使用默认名称
        if not filename or filename == ".pdf":
            filename = "document.pdf"
        
        return filename
    
    def get_file_hash(self, file_path: Path) -> str:
        """计算文件 MD5 哈希"""
        md5_hash = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    
    def cleanup_task(self, task_id: str) -> None:
        """清理任务相关文件"""
        # 清理上传目录
        upload_task_dir = self.upload_dir / task_id
        if upload_task_dir.exists():
            shutil.rmtree(upload_task_dir)
        
        # 清理输出目录
        output_task_dir = self.output_dir / task_id
        if output_task_dir.exists():
            shutil.rmtree(output_task_dir)
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """
        清理过期文件
        
        Args:
            max_age_hours: 最大保留时间（小时）
            
        Returns:
            清理的任务数量
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        for directory in [self.upload_dir, self.output_dir]:
            if not directory.exists():
                continue
            
            for task_dir in directory.iterdir():
                if not task_dir.is_dir():
                    continue
                
                # 检查目录修改时间
                mtime = datetime.fromtimestamp(task_dir.stat().st_mtime)
                if mtime < cutoff_time:
                    shutil.rmtree(task_dir)
                    cleaned_count += 1
        
        return cleaned_count
    
    def list_task_files(self, task_id: str) -> dict:
        """列出任务相关的所有文件"""
        result = {
            "uploads": [],
            "outputs": []
        }
        
        upload_dir = self.upload_dir / task_id
        if upload_dir.exists():
            result["uploads"] = [f.name for f in upload_dir.iterdir() if f.is_file()]
        
        output_dir = self.output_dir / task_id
        if output_dir.exists():
            result["outputs"] = [f.name for f in output_dir.iterdir() if f.is_file()]
        
        return result


# 全局文件管理器实例
file_manager = FileManager()
