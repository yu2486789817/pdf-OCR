"""
图像去噪模块
提供多种去噪算法
"""

import numpy as np
import cv2
from typing import Literal


def gaussian_denoise(
    image: np.ndarray, 
    kernel_size: int = 5,
    sigma: float = 0
) -> np.ndarray:
    """
    高斯去噪
    
    Args:
        image: 输入图像
        kernel_size: 核大小（必须是奇数）
        sigma: 高斯标准差，0 表示自动计算
        
    Returns:
        去噪后的图像
    """
    if kernel_size % 2 == 0:
        kernel_size += 1
    
    return cv2.GaussianBlur(image, (kernel_size, kernel_size), sigma)


def median_denoise(
    image: np.ndarray, 
    kernel_size: int = 5
) -> np.ndarray:
    """
    中值滤波去噪
    对椒盐噪声效果好
    
    Args:
        image: 输入图像
        kernel_size: 核大小（必须是奇数）
        
    Returns:
        去噪后的图像
    """
    if kernel_size % 2 == 0:
        kernel_size += 1
    
    return cv2.medianBlur(image, kernel_size)


def bilateral_denoise(
    image: np.ndarray,
    d: int = 9,
    sigma_color: float = 75,
    sigma_space: float = 75
) -> np.ndarray:
    """
    双边滤波去噪
    保留边缘的同时去除噪声
    
    Args:
        image: 输入图像
        d: 滤波邻域直径
        sigma_color: 颜色空间滤波的 sigma 值
        sigma_space: 坐标空间滤波的 sigma 值
        
    Returns:
        去噪后的图像
    """
    return cv2.bilateralFilter(image, d, sigma_color, sigma_space)


def non_local_means_denoise(
    image: np.ndarray,
    h: float = 10,
    template_window_size: int = 7,
    search_window_size: int = 21
) -> np.ndarray:
    """
    非局部均值去噪
    效果好但速度较慢
    
    Args:
        image: 输入图像
        h: 滤波强度
        template_window_size: 模板窗口大小（奇数）
        search_window_size: 搜索窗口大小（奇数）
        
    Returns:
        去噪后的图像
    """
    if len(image.shape) == 2:
        # 灰度图
        return cv2.fastNlMeansDenoising(
            image, None, h, template_window_size, search_window_size
        )
    else:
        # 彩色图
        return cv2.fastNlMeansDenoisingColored(
            image, None, h, h, template_window_size, search_window_size
        )


def denoise(
    image: np.ndarray,
    method: Literal["gaussian", "median", "bilateral", "nlm"] = "gaussian",
    **kwargs
) -> np.ndarray:
    """
    通用去噪函数
    
    Args:
        image: 输入图像
        method: 去噪方法
            - gaussian: 高斯模糊（快速，通用）
            - median: 中值滤波（对椒盐噪声好）
            - bilateral: 双边滤波（保留边缘）
            - nlm: 非局部均值（效果好但慢）
        **kwargs: 各方法的额外参数
        
    Returns:
        去噪后的图像
    """
    methods = {
        "gaussian": gaussian_denoise,
        "median": median_denoise,
        "bilateral": bilateral_denoise,
        "nlm": non_local_means_denoise
    }
    
    if method not in methods:
        raise ValueError(f"不支持的去噪方法: {method}")
    
    return methods[method](image, **kwargs)
