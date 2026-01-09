"""
图像二值化模块
将灰度图像转换为黑白二值图像
"""

import numpy as np
import cv2
from typing import Literal, Tuple


def _ensure_grayscale(image: np.ndarray) -> np.ndarray:
    """确保图像是灰度图"""
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def simple_binarize(
    image: np.ndarray,
    threshold: int = 127,
    max_value: int = 255,
    invert: bool = False
) -> np.ndarray:
    """
    简单阈值二值化
    
    Args:
        image: 输入图像
        threshold: 阈值
        max_value: 最大值
        invert: 是否反转（True 时黑白颠倒）
        
    Returns:
        二值化后的图像
    """
    gray = _ensure_grayscale(image)
    
    thresh_type = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    _, binary = cv2.threshold(gray, threshold, max_value, thresh_type)
    
    return binary


def otsu_binarize(
    image: np.ndarray,
    max_value: int = 255,
    invert: bool = False
) -> Tuple[np.ndarray, float]:
    """
    Otsu 自动阈值二值化
    自动计算最佳阈值
    
    Args:
        image: 输入图像
        max_value: 最大值
        invert: 是否反转
        
    Returns:
        (二值化图像, 计算得到的阈值)
    """
    gray = _ensure_grayscale(image)
    
    thresh_type = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    thresh_type |= cv2.THRESH_OTSU
    
    threshold, binary = cv2.threshold(gray, 0, max_value, thresh_type)
    
    return binary, threshold


def adaptive_binarize(
    image: np.ndarray,
    max_value: int = 255,
    method: Literal["mean", "gaussian"] = "gaussian",
    block_size: int = 11,
    c: int = 2,
    invert: bool = False
) -> np.ndarray:
    """
    自适应阈值二值化
    对光照不均匀的图像效果好
    
    Args:
        image: 输入图像
        max_value: 最大值
        method: 阈值计算方法
            - mean: 邻域均值
            - gaussian: 邻域高斯加权平均
        block_size: 邻域大小（必须是奇数）
        c: 从均值或加权均值减去的常数
        invert: 是否反转
        
    Returns:
        二值化后的图像
    """
    gray = _ensure_grayscale(image)
    
    # 确保 block_size 是奇数
    if block_size % 2 == 0:
        block_size += 1
    
    adaptive_method = (
        cv2.ADAPTIVE_THRESH_MEAN_C if method == "mean" 
        else cv2.ADAPTIVE_THRESH_GAUSSIAN_C
    )
    
    thresh_type = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    
    binary = cv2.adaptiveThreshold(
        gray, max_value, adaptive_method, thresh_type, block_size, c
    )
    
    return binary


def sauvola_binarize(
    image: np.ndarray,
    window_size: int = 25,
    k: float = 0.5,
    r: float = 128
) -> np.ndarray:
    """
    Sauvola 二值化
    对文档图像效果较好
    
    Args:
        image: 输入图像
        window_size: 窗口大小
        k: 参数 k
        r: 参数 r（动态范围）
        
    Returns:
        二值化后的图像
    """
    gray = _ensure_grayscale(image).astype(np.float64)
    
    # 计算局部均值和标准差
    mean = cv2.blur(gray, (window_size, window_size))
    mean_sq = cv2.blur(gray * gray, (window_size, window_size))
    std = np.sqrt(mean_sq - mean * mean)
    
    # Sauvola 阈值
    threshold = mean * (1 + k * (std / r - 1))
    
    # 二值化
    binary = np.zeros_like(gray, dtype=np.uint8)
    binary[gray > threshold] = 255
    
    return binary


def binarize(
    image: np.ndarray,
    method: Literal["simple", "otsu", "adaptive", "sauvola"] = "otsu",
    **kwargs
) -> np.ndarray:
    """
    通用二值化函数
    
    Args:
        image: 输入图像
        method: 二值化方法
            - simple: 简单阈值
            - otsu: Otsu 自动阈值
            - adaptive: 自适应阈值
            - sauvola: Sauvola 方法
        **kwargs: 各方法的额外参数
        
    Returns:
        二值化后的图像
    """
    if method == "simple":
        return simple_binarize(image, **kwargs)
    elif method == "otsu":
        result = otsu_binarize(image, **kwargs)
        return result[0] if isinstance(result, tuple) else result
    elif method == "adaptive":
        return adaptive_binarize(image, **kwargs)
    elif method == "sauvola":
        return sauvola_binarize(image, **kwargs)
    else:
        raise ValueError(f"不支持的二值化方法: {method}")
