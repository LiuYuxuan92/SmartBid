"""DXF解析主逻辑

负责验证DXF文件格式（拒绝二进制），使用ezdxf提取几何实体
（LWPOLYLINE, POLYLINE, LINE, ARC, CIRCLE），执行几何计算，
并为闭合区域生成 REGION-<layer>-<seq> 标识。
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import ezdxf
from ezdxf.lldxf.const import DXFError as EzdxfDXFError

from src.exceptions import DXFFormatError, DXFEmptyError
from src.pipeline.orchestrator import BaseModule
from src.dxf_parser.geometry import GeometryCalculator

logger = logging.getLogger(__name__)

# Entity types we extract from modelspace
SUPPORTED_ENTITY_TYPES = {"LWPOLYLINE", "POLYLINE", "LINE", "ARC", "CIRCLE"}


@dataclass
class GeometryResult:
    """几何计算结果"""
    region_id: str              # REGION-<layer>-<seq>
    entity_type: str            # LWPOLYLINE, LINE, ARC, etc.
    layer_name: str
    measurement_type: str       # "area" or "length"
    value: float                # sq meters or meters
    quota_code: Optional[str] = None
    unit_price: Optional[float] = None
    subtotal: Optional[float] = None


class DXFParser(BaseModule):
    """DXF文件解析模块
    
    从DXF文件中提取几何实体，计算面积和长度，
    为闭合区域分配REGION标识。
    """

    name = "DXF_Parser"

    def __init__(self, quota_mapper=None):
        self.quota_mapper = quota_mapper

    @property
    def name(self) -> str:
        return "DXF_Parser"

    def validate_input(self, input_data: dict) -> bool:
        """验证输入包含dxf_paths"""
        return "dxf_paths" in input_data and len(input_data["dxf_paths"]) > 0

    def execute(self, input_data: dict, config: dict = None) -> dict:
        """解析DXF文件列表，返回几何计算结果
        
        Args:
            input_data: {"dxf_paths": [str, ...]}
            config: 配置字典（可选）
            
        Returns:
            {
                "results": list[dict],
                "warnings": list[str],
                "total_area": float,
                "total_length": float
            }
        """
        config = config or {}
        dxf_paths = input_data.get("dxf_paths", [])
        
        all_results: list[GeometryResult] = []
        all_warnings: list[str] = []

        for path in dxf_paths:
            try:
                results, warnings = self.parse_file(path)
                all_results.extend(results)
                all_warnings.extend(warnings)
            except (DXFFormatError, DXFEmptyError) as e:
                all_warnings.append(f"File '{path}': {e}")

        total_area = sum(r.value for r in all_results if r.measurement_type == "area")
        total_length = sum(r.value for r in all_results if r.measurement_type == "length")

        return {
            "results": [asdict(r) for r in all_results],
            "warnings": all_warnings,
            "total_area": round(total_area, 2),
            "total_length": round(total_length, 2),
        }

    def parse_file(self, file_path: str) -> tuple[list[GeometryResult], list[str]]:
        """解析单个DXF文件
        
        Args:
            file_path: DXF文件路径
            
        Returns:
            (results, warnings) tuple
            
        Raises:
            DXFFormatError: 二进制格式DXF
            DXFEmptyError: 无几何实体
        """
        self._validate_dxf(file_path)

        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        entities = self._extract_entities(msp)
        results, warnings = self._process_entities(entities)
        return results, warnings

    def _validate_dxf(self, file_path: str) -> None:
        """验证DXF格式
        
        1. 检查是否为文本格式（非二进制）
        2. 检查modelspace是否含有至少一个几何实体
        
        Raises:
            DXFFormatError: 二进制格式
            DXFEmptyError: 无几何实体
        """
        path = Path(file_path)
        
        if not path.exists():
            raise DXFFormatError(f"File not found: {file_path}")

        # Check if binary DXF (binary DXF starts with "AutoCAD Binary DXF")
        try:
            with open(file_path, "rb") as f:
                header = f.read(22)
                if b"AutoCAD Binary DXF" in header:
                    raise DXFFormatError(
                        f"Binary DXF format not supported: {file_path}"
                    )
        except OSError as e:
            raise DXFFormatError(f"Cannot read file: {file_path} - {e}")

        # Check text format indicator — first non-whitespace content should start with "0"
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                first_line = f.readline().strip()
                if first_line != "0":
                    raise DXFFormatError(
                        f"Invalid DXF text format (expected '0' as first group code): {file_path}"
                    )
        except OSError as e:
            raise DXFFormatError(f"Cannot read file: {file_path} - {e}")

        # Validate file can be opened by ezdxf and has geometric entities
        try:
            doc = ezdxf.readfile(file_path)
        except EzdxfDXFError as e:
            raise DXFFormatError(f"ezdxf cannot parse file: {file_path} - {e}")

        msp = doc.modelspace()
        entity_count = sum(
            1 for entity in msp
            if entity.dxftype() in SUPPORTED_ENTITY_TYPES
        )
        
        if entity_count == 0:
            raise DXFEmptyError(
                f"No geometric entities found in modelspace: {file_path}"
            )

    def _extract_entities(self, msp) -> list:
        """从modelspace提取支持的几何实体"""
        entities = []
        for entity in msp:
            if entity.dxftype() in SUPPORTED_ENTITY_TYPES:
                entities.append(entity)
        return entities

    def _process_entities(self, entities: list) -> tuple[list[GeometryResult], list[str]]:
        """处理实体列表，计算几何量并分配REGION标签
        
        Returns:
            (results, warnings)
        """
        results: list[GeometryResult] = []
        warnings: list[str] = []
        # Sequence counter per layer for region labeling
        layer_seq: dict[str, int] = defaultdict(int)

        for entity in entities:
            entity_type = entity.dxftype()
            layer = entity.dxf.layer
            handle = entity.dxf.handle

            try:
                if entity_type in ("LWPOLYLINE", "POLYLINE"):
                    result = self._process_polyline(entity, layer, layer_seq)
                    if result is None:
                        # Not closed — log warning and skip
                        warnings.append(
                            f"Skipped unclosed {entity_type} (handle={handle}, layer={layer})"
                        )
                        logger.warning(
                            "Skipped unclosed %s: handle=%s, layer=%s",
                            entity_type, handle, layer,
                        )
                        continue
                    results.append(result)

                elif entity_type == "LINE":
                    result = self._process_line(entity, layer, layer_seq)
                    results.append(result)

                elif entity_type == "ARC":
                    result = self._process_arc(entity, layer, layer_seq)
                    results.append(result)

                elif entity_type == "CIRCLE":
                    result = self._process_circle(entity, layer, layer_seq)
                    results.append(result)

            except Exception as e:
                warnings.append(
                    f"Invalid geometry {entity_type} (handle={handle}, layer={layer}): {e}"
                )
                logger.warning(
                    "Invalid geometry %s: handle=%s, layer=%s, error=%s",
                    entity_type, handle, layer, e,
                )

        return results, warnings

    def _next_region_id(self, layer: str, layer_seq: dict[str, int]) -> str:
        """Generate next REGION-<layer>-<seq> ID"""
        layer_seq[layer] += 1
        seq = layer_seq[layer]
        return f"REGION-{layer}-{seq:03d}"

    def _process_polyline(
        self, entity, layer: str, layer_seq: dict[str, int]
    ) -> Optional[GeometryResult]:
        """Process LWPOLYLINE or POLYLINE entity.
        
        Only closed polylines are processed (area calculation).
        Returns None for unclosed polylines.
        """
        if not entity.is_closed:
            return None

        # Extract vertices
        if entity.dxftype() == "LWPOLYLINE":
            # LWPOLYLINE vertices are 2D
            vertices = [(v[0], v[1]) for v in entity.get_points(format="xy")]
        else:
            # POLYLINE — get vertices from sub-entities
            vertices = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]

        if len(vertices) < 3:
            return None

        area = GeometryCalculator.shoelace_area(vertices)
        region_id = self._next_region_id(layer, layer_seq)

        return GeometryResult(
            region_id=region_id,
            entity_type=entity.dxftype(),
            layer_name=layer,
            measurement_type="area",
            value=area,
        )

    def _process_line(
        self, entity, layer: str, layer_seq: dict[str, int]
    ) -> GeometryResult:
        """Process LINE entity — calculate length."""
        start = (entity.dxf.start.x, entity.dxf.start.y)
        end = (entity.dxf.end.x, entity.dxf.end.y)
        length = GeometryCalculator.line_length(start, end)
        region_id = self._next_region_id(layer, layer_seq)

        return GeometryResult(
            region_id=region_id,
            entity_type="LINE",
            layer_name=layer,
            measurement_type="length",
            value=length,
        )

    def _process_arc(
        self, entity, layer: str, layer_seq: dict[str, int]
    ) -> GeometryResult:
        """Process ARC entity — calculate arc length."""
        center = (entity.dxf.center.x, entity.dxf.center.y)
        radius = entity.dxf.radius
        start_angle = entity.dxf.start_angle
        end_angle = entity.dxf.end_angle
        length = GeometryCalculator.arc_length(center, radius, start_angle, end_angle)
        region_id = self._next_region_id(layer, layer_seq)

        return GeometryResult(
            region_id=region_id,
            entity_type="ARC",
            layer_name=layer,
            measurement_type="length",
            value=length,
        )

    def _process_circle(
        self, entity, layer: str, layer_seq: dict[str, int]
    ) -> GeometryResult:
        """Process CIRCLE entity — treat as closed region, calculate area."""
        import math
        radius = entity.dxf.radius
        area = round(math.pi * radius * radius, 2)
        region_id = self._next_region_id(layer, layer_seq)

        return GeometryResult(
            region_id=region_id,
            entity_type="CIRCLE",
            layer_name=layer,
            measurement_type="area",
            value=area,
        )
