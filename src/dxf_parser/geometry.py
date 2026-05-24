"""几何计算模块 - Shoelace面积、弧长、线段长度"""

import math


class GeometryCalculator:
    """几何计算工具类"""

    @staticmethod
    def shoelace_area(vertices: list[tuple[float, float]]) -> float:
        """使用Shoelace公式计算闭合多边形面积
        
        Args:
            vertices: 顶点坐标列表 [(x1,y1), (x2,y2), ...]
            
        Returns:
            面积（平方米），精度0.01，始终非负
        """
        n = len(vertices)
        if n < 3:
            return 0.0
        
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += vertices[i][0] * vertices[j][1]
            area -= vertices[j][0] * vertices[i][1]
        
        result = abs(area) / 2.0
        return round(result, 2)

    @staticmethod
    def arc_length(center: tuple[float, float], radius: float, start_angle: float, end_angle: float) -> float:
        """计算弧长
        
        Args:
            center: 圆心坐标 (x, y) — 用于接口一致性
            radius: 半径（米）
            start_angle: 起始角度（度）
            end_angle: 终止角度（度）
            
        Returns:
            弧长（米），精度0.01
        """
        if radius <= 0:
            return 0.0
        
        # Calculate angle span (handle wrap-around)
        angle_span = end_angle - start_angle
        if angle_span < 0:
            angle_span += 360.0
        
        # Convert to radians and compute arc length
        angle_rad = math.radians(angle_span)
        length = radius * angle_rad
        return round(abs(length), 2)

    @staticmethod
    def line_length(start: tuple[float, float], end: tuple[float, float]) -> float:
        """计算线段长度（欧几里得距离）
        
        Args:
            start: 起点 (x, y)
            end: 终点 (x, y)
            
        Returns:
            长度（米），精度0.01
        """
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.sqrt(dx * dx + dy * dy)
        return round(length, 2)
