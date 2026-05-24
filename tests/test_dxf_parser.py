"""DXF解析模块测试

测试DXF格式验证、几何实体提取、Shoelace面积计算、
弧长/线长计算和定额映射。
"""

import math
import pytest

from src.dxf_parser.geometry import GeometryCalculator


class TestShoelaceArea:
    """Shoelace面积计算测试"""

    def test_unit_square(self):
        """单位正方形面积 = 1.0"""
        vertices = [(0, 0), (1, 0), (1, 1), (0, 1)]
        assert GeometryCalculator.shoelace_area(vertices) == 1.0

    def test_right_triangle_3_4_5(self):
        """3-4-5直角三角形面积 = 6.0"""
        vertices = [(0, 0), (3, 0), (0, 4)]
        assert GeometryCalculator.shoelace_area(vertices) == 6.0

    def test_fewer_than_3_vertices_returns_zero(self):
        """少于3个顶点返回0"""
        assert GeometryCalculator.shoelace_area([]) == 0.0
        assert GeometryCalculator.shoelace_area([(0, 0)]) == 0.0
        assert GeometryCalculator.shoelace_area([(0, 0), (1, 1)]) == 0.0

    def test_always_non_negative(self):
        """无论顶点顺序，面积始终非负"""
        # Clockwise
        cw = [(0, 0), (0, 1), (1, 1), (1, 0)]
        # Counter-clockwise
        ccw = [(0, 0), (1, 0), (1, 1), (0, 1)]
        assert GeometryCalculator.shoelace_area(cw) >= 0
        assert GeometryCalculator.shoelace_area(ccw) >= 0
        assert GeometryCalculator.shoelace_area(cw) == GeometryCalculator.shoelace_area(ccw)


class TestArcLength:
    """弧长计算测试"""

    def test_full_circle(self):
        """完整圆弧长度 = 2*pi*r"""
        r = 5.0
        expected = round(2 * math.pi * r, 2)
        assert GeometryCalculator.arc_length((0, 0), r, 0, 360) == expected

    def test_half_circle(self):
        """半圆弧长 = pi*r"""
        r = 4.0
        expected = round(math.pi * r, 2)
        assert GeometryCalculator.arc_length((0, 0), r, 0, 180) == expected

    def test_wrap_around_angles(self):
        """角度环绕: start_angle > end_angle"""
        r = 1.0
        # 270° to 90° should be 180° span
        length = GeometryCalculator.arc_length((0, 0), r, 270, 90)
        expected = round(math.pi * r, 2)  # 180° arc
        assert length == expected

    def test_zero_radius_returns_zero(self):
        """半径为0返回0"""
        assert GeometryCalculator.arc_length((0, 0), 0, 0, 90) == 0.0


class TestLineLength:
    """线段长度计算测试"""

    def test_horizontal_line(self):
        """水平线段"""
        assert GeometryCalculator.line_length((0, 0), (5, 0)) == 5.0

    def test_vertical_line(self):
        """垂直线段"""
        assert GeometryCalculator.line_length((0, 0), (0, 3)) == 3.0

    def test_diagonal_3_4_5(self):
        """3-4-5三角形斜边 = 5.0"""
        assert GeometryCalculator.line_length((0, 0), (3, 4)) == 5.0

    def test_same_point_returns_zero(self):
        """同一点距离为0"""
        assert GeometryCalculator.line_length((2, 3), (2, 3)) == 0.0


# ============================================================
# DXFParser Tests
# ============================================================
import tempfile
import os
from pathlib import Path

import ezdxf

from src.dxf_parser.parser import DXFParser, GeometryResult
from src.exceptions import DXFFormatError, DXFEmptyError


def _create_dxf_with_closed_polyline(filepath: str, layer: str = "WALL"):
    """Helper: create a valid DXF with a closed LWPOLYLINE (unit square)."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    points = [(0, 0), (10, 0), (10, 10), (0, 10)]
    msp.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
    doc.saveas(filepath)


def _create_dxf_with_line(filepath: str, layer: str = "AXIS"):
    """Helper: create a valid DXF with a LINE entity."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (3, 4), dxfattribs={"layer": layer})
    doc.saveas(filepath)


def _create_dxf_with_arc(filepath: str, layer: str = "CURVE"):
    """Helper: create a valid DXF with an ARC entity."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_arc(center=(0, 0), radius=5.0, start_angle=0, end_angle=180,
                dxfattribs={"layer": layer})
    doc.saveas(filepath)


def _create_empty_dxf(filepath: str):
    """Helper: create a DXF with no geometric entities (only metadata)."""
    doc = ezdxf.new("R2010")
    # Don't add any entities to modelspace
    doc.saveas(filepath)


def _create_dxf_with_unclosed_polyline(filepath: str, layer: str = "SKETCH"):
    """Helper: create a DXF with an open (unclosed) polyline."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    points = [(0, 0), (5, 0), (5, 5)]
    msp.add_lwpolyline(points, close=False, dxfattribs={"layer": layer})
    # Add a line so the file isn't "empty" for validation purposes
    msp.add_line((0, 0), (1, 1), dxfattribs={"layer": layer})
    doc.saveas(filepath)


class TestDXFParserValidation:
    """DXF格式验证测试"""

    def test_binary_dxf_raises_format_error(self, tmp_path):
        """Binary DXF should raise DXFFormatError."""
        filepath = str(tmp_path / "binary.dxf")
        with open(filepath, "wb") as f:
            f.write(b"AutoCAD Binary DXF\r\n\x00" + b"\x00" * 100)

        parser = DXFParser()
        with pytest.raises(DXFFormatError):
            parser._validate_dxf(filepath)

    def test_empty_modelspace_raises_empty_error(self, tmp_path):
        """DXF with no entities should raise DXFEmptyError."""
        filepath = str(tmp_path / "empty.dxf")
        _create_empty_dxf(filepath)

        parser = DXFParser()
        with pytest.raises(DXFEmptyError):
            parser._validate_dxf(filepath)

    def test_valid_dxf_passes_validation(self, tmp_path):
        """Valid text DXF with entities passes validation."""
        filepath = str(tmp_path / "valid.dxf")
        _create_dxf_with_closed_polyline(filepath)

        parser = DXFParser()
        # Should not raise
        parser._validate_dxf(filepath)

    def test_nonexistent_file_raises_format_error(self):
        """Non-existent file should raise DXFFormatError."""
        parser = DXFParser()
        with pytest.raises(DXFFormatError):
            parser._validate_dxf("/nonexistent/path.dxf")


class TestDXFParserExecution:
    """DXFParser execute() 集成测试"""

    def test_closed_polyline_calculates_area(self, tmp_path):
        """Closed LWPOLYLINE should produce area measurement."""
        filepath = str(tmp_path / "poly.dxf")
        _create_dxf_with_closed_polyline(filepath, layer="WALL")

        parser = DXFParser()
        output = parser.execute({"dxf_paths": [filepath]}, {})

        assert len(output["results"]) == 1
        result = output["results"][0]
        assert result["entity_type"] == "LWPOLYLINE"
        assert result["measurement_type"] == "area"
        assert result["value"] == 100.0  # 10x10 square
        assert result["region_id"] == "REGION-WALL-001"
        assert result["layer_name"] == "WALL"

    def test_line_calculates_length(self, tmp_path):
        """LINE entity should produce length measurement."""
        filepath = str(tmp_path / "line.dxf")
        _create_dxf_with_line(filepath, layer="AXIS")

        parser = DXFParser()
        output = parser.execute({"dxf_paths": [filepath]}, {})

        assert len(output["results"]) == 1
        result = output["results"][0]
        assert result["entity_type"] == "LINE"
        assert result["measurement_type"] == "length"
        assert result["value"] == 5.0  # 3-4-5 triangle hypotenuse
        assert result["region_id"] == "REGION-AXIS-001"

    def test_arc_calculates_length(self, tmp_path):
        """ARC entity should produce arc length measurement."""
        filepath = str(tmp_path / "arc.dxf")
        _create_dxf_with_arc(filepath, layer="CURVE")

        parser = DXFParser()
        output = parser.execute({"dxf_paths": [filepath]}, {})

        assert len(output["results"]) == 1
        result = output["results"][0]
        assert result["entity_type"] == "ARC"
        assert result["measurement_type"] == "length"
        # Half circle with r=5: pi*5 = 15.71
        assert result["value"] == 15.71
        assert result["region_id"] == "REGION-CURVE-001"

    def test_unclosed_polyline_generates_warning(self, tmp_path):
        """Unclosed polyline should be skipped with a warning."""
        filepath = str(tmp_path / "open.dxf")
        _create_dxf_with_unclosed_polyline(filepath, layer="SKETCH")

        parser = DXFParser()
        output = parser.execute({"dxf_paths": [filepath]}, {})

        # The unclosed polyline is skipped, but the LINE is processed
        assert len(output["results"]) == 1
        assert output["results"][0]["entity_type"] == "LINE"
        # Warning about unclosed polyline
        assert any("unclosed" in w.lower() or "Skipped" in w for w in output["warnings"])

    def test_region_id_sequence_per_layer(self, tmp_path):
        """Region IDs should sequence per layer."""
        filepath = str(tmp_path / "multi.dxf")
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        # Two closed polylines on same layer
        msp.add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1)], close=True,
                           dxfattribs={"layer": "FLOOR"})
        msp.add_lwpolyline([(2, 2), (4, 2), (4, 4), (2, 4)], close=True,
                           dxfattribs={"layer": "FLOOR"})
        # One on different layer
        msp.add_lwpolyline([(0, 0), (5, 0), (5, 5), (0, 5)], close=True,
                           dxfattribs={"layer": "ROOF"})
        doc.saveas(filepath)

        parser = DXFParser()
        output = parser.execute({"dxf_paths": [filepath]}, {})

        region_ids = [r["region_id"] for r in output["results"]]
        assert "REGION-FLOOR-001" in region_ids
        assert "REGION-FLOOR-002" in region_ids
        assert "REGION-ROOF-001" in region_ids

    def test_total_area_and_length_aggregation(self, tmp_path):
        """Total area and total length should aggregate correctly."""
        filepath = str(tmp_path / "mixed.dxf")
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        # Closed polyline: area = 100
        msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True,
                           dxfattribs={"layer": "WALL"})
        # Line: length = 5 (3-4-5)
        msp.add_line((0, 0), (3, 4), dxfattribs={"layer": "AXIS"})
        doc.saveas(filepath)

        parser = DXFParser()
        output = parser.execute({"dxf_paths": [filepath]}, {})

        assert output["total_area"] == 100.0
        assert output["total_length"] == 5.0

    def test_multiple_files(self, tmp_path):
        """execute() should process multiple DXF files."""
        f1 = str(tmp_path / "f1.dxf")
        f2 = str(tmp_path / "f2.dxf")
        _create_dxf_with_closed_polyline(f1, "WALL")
        _create_dxf_with_line(f2, "AXIS")

        parser = DXFParser()
        output = parser.execute({"dxf_paths": [f1, f2]}, {})

        assert len(output["results"]) == 2
        assert output["total_area"] == 100.0
        assert output["total_length"] == 5.0

    def test_validate_input(self):
        """validate_input should check for dxf_paths key."""
        parser = DXFParser()
        assert parser.validate_input({"dxf_paths": ["a.dxf"]}) is True
        assert parser.validate_input({"dxf_paths": []}) is False
        assert parser.validate_input({}) is False


# ============================================================
# QuotaMapper Tests
# ============================================================
import json

from src.dxf_parser.quota_mapper import QuotaMapper


class TestQuotaMapperMap:
    """QuotaMapper.map() 测试"""

    def test_map_returns_correct_quota_item_for_known_layer(self, tmp_path):
        """已知图层返回正确的定额项"""
        db_file = tmp_path / "quota.json"
        db_file.write_text(json.dumps({
            "WALL": {"code": "A-001", "unit_price": 350.0, "unit": "m2", "description": "墙体工程"}
        }), encoding="utf-8")

        mapper = QuotaMapper(str(db_file))
        result = mapper.map("WALL")

        assert result is not None
        assert result["code"] == "A-001"
        assert result["unit_price"] == 350.0
        assert result["unit"] == "m2"
        assert result["description"] == "墙体工程"

    def test_map_returns_none_for_unknown_layer(self, tmp_path):
        """未知图层返回None"""
        db_file = tmp_path / "quota.json"
        db_file.write_text(json.dumps({
            "WALL": {"code": "A-001", "unit_price": 350.0, "unit": "m2", "description": "墙体工程"}
        }), encoding="utf-8")

        mapper = QuotaMapper(str(db_file))
        result = mapper.map("UNKNOWN_LAYER")

        assert result is None


class TestQuotaMapperEnrichResults:
    """QuotaMapper.enrich_results() 测试"""

    def test_enrich_adds_quota_info_for_matched_layer(self, tmp_path):
        """匹配到定额时填入quota_code, unit_price, subtotal"""
        db_file = tmp_path / "quota.json"
        db_file.write_text(json.dumps({
            "WALL": {"code": "A-001", "unit_price": 350.0, "unit": "m2", "description": "墙体工程"}
        }), encoding="utf-8")

        mapper = QuotaMapper(str(db_file))
        results = [{"layer_name": "WALL", "value": 100.0}]
        enriched = mapper.enrich_results(results)

        assert len(enriched) == 1
        assert enriched[0]["quota_code"] == "A-001"
        assert enriched[0]["unit_price"] == 350.0
        assert enriched[0]["subtotal"] == 35000.0

    def test_enrich_marks_unmatched_layer(self, tmp_path):
        """未匹配图层标记为'未匹配'"""
        db_file = tmp_path / "quota.json"
        db_file.write_text(json.dumps({
            "WALL": {"code": "A-001", "unit_price": 350.0, "unit": "m2", "description": "墙体工程"}
        }), encoding="utf-8")

        mapper = QuotaMapper(str(db_file))
        results = [{"layer_name": "UNKNOWN", "value": 50.0}]
        enriched = mapper.enrich_results(results)

        assert len(enriched) == 1
        assert enriched[0]["quota_code"] == "未匹配"
        assert enriched[0]["unit_price"] is None
        assert enriched[0]["subtotal"] is None

    def test_empty_quota_db_marks_everything_unmatched(self, tmp_path):
        """空定额数据库所有项标记为'未匹配'"""
        db_file = tmp_path / "quota.json"
        db_file.write_text("{}", encoding="utf-8")

        mapper = QuotaMapper(str(db_file))
        results = [
            {"layer_name": "WALL", "value": 100.0},
            {"layer_name": "FLOOR", "value": 50.0},
        ]
        enriched = mapper.enrich_results(results)

        for item in enriched:
            assert item["quota_code"] == "未匹配"
            assert item["unit_price"] is None
            assert item["subtotal"] is None

    def test_subtotal_equals_value_times_unit_price(self, tmp_path):
        """subtotal = value * unit_price"""
        db_file = tmp_path / "quota.json"
        db_file.write_text(json.dumps({
            "FLOOR": {"code": "A-002", "unit_price": 280.0, "unit": "m2", "description": "地面工程"}
        }), encoding="utf-8")

        mapper = QuotaMapper(str(db_file))
        results = [{"layer_name": "FLOOR", "value": 25.5}]
        enriched = mapper.enrich_results(results)

        assert enriched[0]["subtotal"] == round(25.5 * 280.0, 2)
        assert enriched[0]["subtotal"] == 7140.0

    def test_nonexistent_db_file_creates_empty_mapper(self):
        """不存在的数据库文件创建空映射器"""
        mapper = QuotaMapper("/nonexistent/path/quota.json")
        assert mapper.map("WALL") is None
