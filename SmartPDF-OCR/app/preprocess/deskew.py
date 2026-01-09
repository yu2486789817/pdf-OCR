"""
图像倾斜校正模块
检测并校正文档图像的倾斜角度
"""

import numpy as np
import cv2
from typing import Tuple, Optional


def _ensure_grayscale(image: np.ndarray) -> np.ndarray:
    """确保图像是灰度图"""
    if len(image.shape) == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def detect_skew_angle_hough(
    image: np.ndarray,
    angle_range: Tuple[float, float] = (-15, 15),
    threshold: int = 100,
    min_line_length: int = 100,
    max_line_gap: int = 10
) -> float:
    """
    使用霍夫变换检测倾斜角度
    
    Args:
        image: 输入图像
        angle_range: 检测的角度范围
        threshold: 霍夫变换阈值
        min_line_length: 最小线段长度
        max_line_gap: 最大线段间隔
        
    Returns:
        检测到的倾斜角度（度）
    """
    gray = _ensure_grayscale(image)
    
    # 边缘检测
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # 霍夫变换检测直线
    lines = cv2.HoughLinesP(
        edges, 
        rho=1, 
        theta=np.pi / 180,
        threshold=threshold,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap
    )
    
    if lines is None or len(lines) == 0:
        return 0.0
    
    # 计算所有线段的角度
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 - x1 == 0:
            continue
        
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        
        # 只保留在指定范围内的角度
        if angle_range[0] <= angle <= angle_range[1]:
            angles.append(angle)
    
    if len(angles) == 0:
        return 0.0
    
    # 返回中位数角度
    return float(np.median(angles))


def detect_skew_angle_projection(
    image: np.ndarray,
    angle_range: Tuple[float, float] = (-15, 15),
    angle_step: float = 0.5
) -> float:
    """
    使用投影分析检测倾斜角度
    通过评估不同旋转角度下的水平投影方差来确定最佳角度
    
    Args:
        image: 输入图像
        angle_range: 检测的角度范围
        angle_step: 角度步长
        
    Returns:
        检测到的倾斜角度（度）
    """
    gray = _ensure_grayscale(image)
    
    # 二值化
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 测试不同角度
    angles = np.arange(angle_range[0], angle_range[1] + angle_step, angle_step)
    best_angle = 0.0
    max_variance = 0.0
    
    h, w = binary.shape
    center = (w // 2, h // 2)
    
    for angle in angles:
        # 旋转图像
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(binary, matrix, (w, h), flags=cv2.INTER_NEAREST)
        
        # 计算水平投影
        projection = np.sum(rotated, axis=1)
        
        # 计算投影方差
        variance = np.var(projection)
        
        if variance > max_variance:
            max_variance = variance
            best_angle = angle
    
    return best_angle


def detect_skew_angle_minarea(image: np.ndarray) -> float:
    """
    使用最小外接矩形检测倾斜角度
    
    Args:
        image: 输入图像
        
    Returns:
        检测到的倾斜角度（度）
    """
    gray = _ensure_grayscale(image)
    
    # 二值化
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 查找轮廓
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    if len(contours) == 0:
        return 0.0
    
    # 合并所有轮廓点
    all_points = np.vstack(contours)
    
    # 计算最小外接矩形
    rect = cv2.minAreaRect(all_points)
    angle = rect[-1]
    
    # 调整角度范围
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90
    
    return angle


def detect_skew_angle(
    image: np.ndarray,
    method: str = "hough",
    **kwargs
) -> float:
    """
    检测图像倾斜角度
    
    Args:
        image: 输入图像
        method: 检测方法
            - hough: 霍夫变换（推荐）
            - projection: 投影分析
            - minarea: 最小外接矩形
        **kwargs: 各方法的额外参数
        
    Returns:
        倾斜角度（度）
    """
    methods = {
        "hough": detect_skew_angle_hough,
        "projection": detect_skew_angle_projection,
        "minarea": detect_skew_angle_minarea
    }
    
    if method not in methods:
        raise ValueError(f"不支持的检测方法: {method}")
    
    return methods[method](image, **kwargs)


def rotate_image(
    image: np.ndarray,
    angle: float,
    background_color: Tuple[int, int, int] = (255, 255, 255)
) -> np.ndarray:
    """
    旋转图像
    
    Args:
        image: 输入图像
        angle: 旋转角度（度，逆时针为正）
        background_color: 背景填充颜色
        
    Returns:
        旋转后的图像
    """
    if abs(angle) < 0.1:
        return image
    
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    
    # 计算旋转矩阵
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # 计算新的边界尺寸
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    
    # 调整旋转矩阵
    matrix[0, 2] += (new_w - w) / 2
    matrix[1, 2] += (new_h - h) / 2
    
    # 旋转图像
    rotated = cv2.warpAffine(
        image, 
        matrix, 
        (new_w, new_h),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=background_color
    )
    
    return rotated


def deskew(
    image: np.ndarray,
    method: str = "hough",
    background_color: Tuple[int, int, int] = (255, 255, 255),
    **kwargs
) -> Tuple[np.ndarray, float]:
    """
    自动检测并校正图像倾斜
    
    Args:
        image: 输入图像
        method: 检测方法
        background_color: 背景填充颜色
        **kwargs: 检测方法的额外参数
        
    Returns:
        (校正后的图像, 检测到的倾斜角度)
    """
    angle = detect_skew_angle(image, method, **kwargs)
    
    if abs(angle) < 0.1:
        return image, 0.0
    
    corrected = rotate_image(image, angle, background_color)
    
    return corrected, angle
